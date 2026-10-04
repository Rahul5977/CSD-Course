#!/usr/bin/env node
'use strict';
// ============================================================================
// server.js — messaging app backend v2 (Assignment 5).
//
// A clean rebuild of the Assignment-4 "ChatFat" backend, keeping its security
// model intact while becoming horizontally scalable behind a load balancer:
//
//   · Auth: register/login with scrypt password hashing (Node crypto.scrypt),
//     per-user random salt, constant-time compare, HttpOnly session cookie,
//     login rate limiting. (Assignment 4's better-auth needed Node>=22; the
//     lab machines run Node 18 — this zero-dependency implementation restores
//     the original scrypt design and fixes that incompatibility.)
//   · E2E room encryption: EXACTLY the Assignment-4 scheme. The server only
//     validates envelope *shape* ({alg:'A256GCM', kid, n, iv(12B), ct, aadv})
//     and size; it stores and relays ciphertext it cannot read.
//   · Shared state: users/sessions/rooms/messages live in the state service
//     (STATE_URL), so every backend instance serves identical data. New
//     messages arrive via the state service's WS firehose and are pushed to
//     this instance's connected clients (cross-instance delivery).
//   · LB support: X-Backend-Id on every response, /health, /metrics, /whoami,
//     graceful SIGTERM drain.
//
// Sends go over HTTP POST (never retried by the LB — safe); receives go over
// a WebSocket that the LB pins to one backend.
//
// ENV: BACKEND_ID, PORT, STATE_URL, HOST, LOG_LEVEL — no hardcoded hosts.
// ============================================================================

const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { WebSocketServer, WebSocket } = require(path.join(__dirname, 'vendor', 'ws'));

const PORT = parseInt(process.env.PORT || '3270', 10);
const HOST = process.env.HOST || '0.0.0.0';
const BACKEND_ID = process.env.BACKEND_ID || 'local';
const STATE_URL = process.env.STATE_URL || 'http://127.0.0.1:5269';
const STATIC_DIR = path.join(__dirname, 'static');
const SESSION_TTL_MS = 12 * 60 * 60 * 1000;   // 12 h sessions
const SESSION_CACHE_MS = 30 * 1000;           // local session cache TTL
const MAX_CIPHERTEXT = 12288;                 // same cap as Assignment 4
const LOGIN_MAX_PER_MIN = 10;                 // per-IP login attempts

const started = Date.now();

// ── Metrics ─────────────────────────────────────────────────────────────────
const metrics = {
  requests_total: 0, errors_total: 0, in_flight: 0,
  messages_sent: 0, messages_delivered: 0, ws_connections: 0,
  latency_ms: [],                            // ring buffer of last 5000 request latencies
};
function recordLatency(ms) {
  metrics.latency_ms.push(ms);
  if (metrics.latency_ms.length > 5000) metrics.latency_ms.shift();
}
function pct(arr, p) {
  if (!arr.length) return 0;
  const s = [...arr].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(p / 100 * s.length))];
}

// ── State-service client ────────────────────────────────────────────────────
// One silent retry for idempotent verbs: a pooled keep-alive connection the
// state service just closed surfaces as "fetch failed / other side closed".
// POST /messages is NOT retried (an append must never be duplicated).
async function state(method, pathName, body) {
  const attempt = async () => {
    const res = await fetch(STATE_URL + pathName, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`state ${method} ${pathName} -> ${res.status}`);
    return res.json();
  };
  try {
    return await attempt();
  } catch (e) {
    if (method === 'POST') throw e;
    return attempt();
  }
}

// Safety net: a stray rejection must never take the whole backend down.
process.on('unhandledRejection', err => {
  metrics.errors_total++;
  log('unhandledRejection (survived):', err && err.message);
});

// ── Auth: scrypt hashing (restores Assignment 4's original design) ──────────
function hashPassword(password) {
  return new Promise((resolve, reject) => {
    const salt = crypto.randomBytes(16);
    crypto.scrypt(password, salt, 64, (err, key) => {
      if (err) return reject(err);
      resolve(`scrypt:${salt.toString('base64')}:${key.toString('base64')}`);
    });
  });
}
function verifyPassword(password, stored) {
  return new Promise((resolve) => {
    const [scheme, saltB64, keyB64] = String(stored || '').split(':');
    if (scheme !== 'scrypt') return resolve(false);
    const salt = Buffer.from(saltB64, 'base64');
    const expect = Buffer.from(keyB64, 'base64');
    crypto.scrypt(password, salt, expect.length, (err, key) => {
      if (err) return resolve(false);
      resolve(crypto.timingSafeEqual(key, expect));   // constant-time compare
    });
  });
}

// Local session cache so a hot LB run does not hammer the state service.
const sessionCache = new Map(); // token -> {rec, cachedAt}
async function sessionFor(req) {
  const cookies = Object.fromEntries((req.headers.cookie || '').split(';')
    .map(c => c.trim().split('=').map(decodeURIComponent)).filter(p => p.length === 2));
  const token = cookies.session;
  if (!token || !/^[a-f0-9]{48}$/.test(token)) return null;
  const hit = sessionCache.get(token);
  if (hit && Date.now() - hit.cachedAt < SESSION_CACHE_MS) return hit.rec;
  const rec = await state('GET', '/kv/sessions/' + token);
  if (!rec || rec.expires < Date.now()) { sessionCache.delete(token); return null; }
  sessionCache.set(token, { rec, cachedAt: Date.now() });
  return rec;
}

// Login rate limiting: sliding window per client IP, counting FAILED
// sign-ins only (Assignment-4 semantics: AUTH_MAX_ATTEMPTS = failed
// sign-ins per minute per IP). Successful logins never throttle.
const loginAttempts = new Map(); // ip -> [timestamps of failures]
function loginBlocked(ip) {
  const now = Date.now();
  const arr = (loginAttempts.get(ip) || []).filter(t => now - t < 60000);
  loginAttempts.set(ip, arr);
  return arr.length >= LOGIN_MAX_PER_MIN;
}
function loginFailed(ip) {
  if (!loginAttempts.has(ip)) loginAttempts.set(ip, []);
  loginAttempts.get(ip).push(Date.now());
}
setInterval(() => { for (const [ip, arr] of loginAttempts) if (arr.every(t => Date.now() - t > 60000)) loginAttempts.delete(ip); }, 60000).unref();

// ── E2E envelope validation — shape and size ONLY (Assignment-4 semantics) ──
function b64len(s) { try { return Buffer.from(s, 'base64').length; } catch (e) { return -1; } }
function validEnvelope(env) {
  return env && typeof env === 'object' && !Array.isArray(env)
    && env.alg === 'A256GCM' && env.aadv === 1
    && Number.isInteger(env.kid) && env.kid >= 1
    && typeof env.n === 'string' && b64len(env.n) === 16
    && typeof env.iv === 'string' && b64len(env.iv) === 12
    && typeof env.ct === 'string' && b64len(env.ct) > 0 && b64len(env.ct) <= MAX_CIPHERTEXT;
}

// ── Local WS clients + subscription to the state firehose ───────────────────
// room -> Set<ws> of clients on THIS instance
const roomClients = new Map();
function deliverLocal(room, rec) {
  const set = roomClients.get(room);
  if (!set) return;
  const frame = JSON.stringify({ type: 'msg', room, entry: rec, via: BACKEND_ID });
  for (const ws of set) if (ws.readyState === ws.OPEN) { ws.send(frame); metrics.messages_delivered++; }
}

let stateWS = null, stateWSUp = false;
function connectFirehose() {
  const wsUrl = STATE_URL.replace(/^http/, 'ws') + '/subscribe';
  stateWS = new WebSocket(wsUrl);
  stateWS.on('open', () => { stateWSUp = true; log('firehose connected'); });
  stateWS.on('message', data => {
    try {
      const ev = JSON.parse(data);
      if (ev.type === 'msg') deliverLocal(ev.room, ev.entry);
      if (ev.type === 'room') broadcastAll({ type: 'room', room: ev.room });
    } catch (e) {}
  });
  const retry = () => { stateWSUp = false; setTimeout(connectFirehose, 2000); };
  stateWS.on('close', retry);
  stateWS.on('error', () => stateWS.close());
}
function broadcastAll(obj) {
  const frame = JSON.stringify(obj);
  for (const set of roomClients.values()) for (const ws of set) if (ws.readyState === ws.OPEN) ws.send(frame);
}

function log(...args) { if (process.env.LOG_LEVEL !== 'silent') console.log(`[${BACKEND_ID}]`, ...args); }

// ── HTTP plumbing ───────────────────────────────────────────────────────────
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon' };
function json(res, code, obj, extra) {
  const body = JSON.stringify(obj);
  res.writeHead(code, Object.assign({ 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }, extra || {}));
  res.end(body);
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', c => { size += c.length; if (size > 65536) { reject(new Error('body too large')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => { try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks)) : {}); } catch (e) { reject(new Error('bad json')); } });
    req.on('error', reject);
  });
}
const NAME_RE = /^[a-zA-Z0-9_.-]{2,24}$/;
const ROOM_RE = /^[a-z0-9-]{1,32}$/;

const server = http.createServer(async (req, res) => {
  const t0 = Date.now();
  metrics.requests_total++; metrics.in_flight++;
  res.setHeader('X-Backend-Id', BACKEND_ID);
  res.on('finish', () => { metrics.in_flight--; recordLatency(Date.now() - t0); if (res.statusCode >= 500) metrics.errors_total++; });
  const u = new URL(req.url, 'http://x');
  // Behind the LB every socket has the LB's address; trust its X-Real-IP.
  const ip = req.headers['x-real-ip'] || req.socket.remoteAddress || '?';
  try {
    // ---- infra endpoints -------------------------------------------------
    if (u.pathname === '/health') {
      return json(res, 200, { status: 'ok', backend: BACKEND_ID, uptime: Math.round((Date.now() - started) / 1000), connections: metrics.ws_connections, state_firehose: stateWSUp });
    }
    if (u.pathname === '/metrics') {
      const l = metrics.latency_ms;
      return json(res, 200, {
        backend: BACKEND_ID, requests_total: metrics.requests_total, errors_total: metrics.errors_total,
        in_flight: metrics.in_flight, ws_connections: metrics.ws_connections,
        messages_sent: metrics.messages_sent, messages_delivered: metrics.messages_delivered,
        latency_ms: { mean: l.length ? Math.round(l.reduce((a, b) => a + b, 0) / l.length * 10) / 10 : 0, p50: pct(l, 50), p95: pct(l, 95), p99: pct(l, 99) },
        uptime: Math.round((Date.now() - started) / 1000),
      });
    }
    if (u.pathname === '/whoami') return json(res, 200, { backend: BACKEND_ID });

    // ---- auth ------------------------------------------------------------
    if (u.pathname === '/api/register' && req.method === 'POST') {
      const { username, password } = await readBody(req);
      if (!NAME_RE.test(username || '')) return json(res, 400, { error: 'Username: 2-24 chars, letters/digits/._-' });
      if (typeof password !== 'string' || password.length < 8) return json(res, 400, { error: 'Password: at least 8 characters.' });
      if (await state('GET', '/kv/users/' + encodeURIComponent(username))) return json(res, 409, { error: 'That username is taken.' });
      await state('PUT', '/kv/users/' + encodeURIComponent(username), { username, hash: await hashPassword(password), created: Date.now() });
      return await createSession(res, username);   // await, or a rejection escapes the catch
    }
    if (u.pathname === '/api/login' && req.method === 'POST') {
      if (loginBlocked(ip)) return json(res, 429, { error: 'Too many attempts. Wait a minute.' });
      const { username, password } = await readBody(req);
      const user = await state('GET', '/kv/users/' + encodeURIComponent(username || ''));
      if (!user || !(await verifyPassword(password || '', user.hash))) {
        loginFailed(ip);
        return json(res, 401, { error: 'Wrong username or password.' });
      }
      return await createSession(res, username);
    }
    if (u.pathname === '/api/logout' && req.method === 'POST') {
      const sess = await sessionFor(req);
      if (sess) { await state('DELETE', '/kv/sessions/' + sess.token); sessionCache.delete(sess.token); }
      return json(res, 200, { ok: true }, { 'Set-Cookie': 'session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict' });
    }
    if (u.pathname === '/api/me') {
      const sess = await sessionFor(req);
      return sess ? json(res, 200, { username: sess.username, backend: BACKEND_ID }) : json(res, 401, { error: 'Not signed in.' });
    }

    // ---- everything below requires a session -----------------------------
    if (u.pathname.startsWith('/api/')) {
      const sess = await sessionFor(req);
      if (!sess) return json(res, 401, { error: 'Not signed in.' });

      if (u.pathname === '/api/rooms' && req.method === 'GET') {
        const dir = await state('GET', '/rooms');
        return json(res, 200, dir || { rooms: [] });
      }
      if (u.pathname === '/api/rooms' && req.method === 'POST') {
        const { id } = await readBody(req);
        if (!ROOM_RE.test(id || '')) return json(res, 400, { error: 'Room id: 1-32 chars, a-z 0-9 -' });
        if (!(await state('GET', '/kv/rooms/' + id))) {
          await state('PUT', '/kv/rooms/' + id, { id, locked: false, epoch: 0, verifier: null, created: Date.now(), by: sess.username });
        }
        return json(res, 200, await state('GET', '/kv/rooms/' + id));
      }
      // Lock a room: client derived the key locally and sends only the epoch +
      // HMAC verifier. Locking is forward-only — never back to plaintext
      // (Assignment-4 rule: no downgrade attack).
      if (u.pathname.match(/^\/api\/rooms\/[a-z0-9-]+\/lock$/) && req.method === 'POST') {
        const id = u.pathname.split('/')[3];
        const room = await state('GET', '/kv/rooms/' + id);
        if (!room) return json(res, 404, { error: 'No such room.' });
        const { epoch, verifier } = await readBody(req);
        if (!Number.isInteger(epoch) || epoch !== room.epoch + 1 || typeof verifier !== 'string') {
          return json(res, 400, { error: 'Bad lock request.' });
        }
        Object.assign(room, { locked: true, epoch, verifier });
        await state('PUT', '/kv/rooms/' + id, room);
        await state('POST', '/messages', { room: id, entry: { id: crypto.randomUUID(), from: sess.username, ts: Date.now(), kind: 'system', text: `${sess.username} locked the room (epoch ${epoch}).`, roomMeta: room } });
        return json(res, 200, room);
      }
      if (u.pathname === '/api/messages' && req.method === 'GET') {
        const room = u.searchParams.get('room') || '';
        if (!ROOM_RE.test(room)) return json(res, 400, { error: 'bad room' });
        const out = await state('GET', `/messages?room=${room}&since=${parseInt(u.searchParams.get('since') || '0', 10) || 0}&limit=100`);
        return json(res, 200, out);
      }
      if (u.pathname === '/api/messages' && req.method === 'POST') {
        const { room, text, env } = await readBody(req);
        if (!ROOM_RE.test(room || '')) return json(res, 400, { error: 'bad room' });
        const roomRec = await state('GET', '/kv/rooms/' + room);
        if (!roomRec) return json(res, 404, { error: 'No such room.' });
        const entry = { id: crypto.randomUUID(), from: sess.username, ts: Date.now(), via: BACKEND_ID };
        if (roomRec.locked) {
          // Locked room: ciphertext only. The server can check the shape but
          // has no key — it cannot read what it relays. (E2E, Assignment 4.)
          if (!validEnvelope(env)) return json(res, 400, { error: 'Malformed ciphertext envelope.' });
          entry.kind = 'enc';
          entry.env = { alg: 'A256GCM', kid: env.kid, n: env.n, iv: env.iv, ct: env.ct, aadv: 1 };
        } else {
          if (typeof text !== 'string' || !text.trim() || text.length > 2000) return json(res, 400, { error: 'Message must be 1-2000 chars.' });
          entry.kind = 'plain';
          entry.text = text.trim();
        }
        const r = await state('POST', '/messages', { room, entry });
        metrics.messages_sent++;
        return json(res, 200, { ok: true, seq: r.seq, id: entry.id });
      }
      return json(res, 404, { error: 'no route' });
    }

    // ---- static files ----------------------------------------------------
    let file = u.pathname === '/' ? '/index.html' : u.pathname;
    file = path.normalize(file).replace(/^(\.\.[\/\\])+/, '');
    const full = path.join(STATIC_DIR, file);
    if (!full.startsWith(STATIC_DIR)) return json(res, 403, { error: 'no' });
    fs.readFile(full, (err, data) => {
      if (err) return json(res, 404, { error: 'not found' });
      res.writeHead(200, { 'Content-Type': MIME[path.extname(full)] || 'application/octet-stream', 'Content-Length': data.length, 'Cache-Control': 'no-cache' });
      res.end(data);
    });
  } catch (e) {
    metrics.errors_total++;
    json(res, 500, { error: String(e.message || e) });
  }
});

async function createSession(res, username) {
  const token = crypto.randomBytes(24).toString('hex'); // 48 hex chars
  await state('PUT', '/kv/sessions/' + token, { token, username, created: Date.now(), expires: Date.now() + SESSION_TTL_MS });
  return json(res, 200, { ok: true, username, backend: BACKEND_ID },
    { 'Set-Cookie': `session=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${SESSION_TTL_MS / 1000}` });
}

// ── Client WebSocket: receive-only event stream, pinned by the LB ───────────
const wss = new WebSocketServer({ server, path: '/ws' });
wss.on('connection', async (ws, req) => {
  const sess = await sessionFor(req).catch(() => null);
  if (!sess) { ws.close(4401, 'not signed in'); return; }
  metrics.ws_connections++;
  ws.isAlive = true; ws.rooms = new Set();
  ws.on('pong', () => { ws.isAlive = true; });
  ws.send(JSON.stringify({ type: 'hello', backend: BACKEND_ID, username: sess.username }));
  ws.on('message', data => {
    try {
      const m = JSON.parse(data);
      if (m.type === 'join' && ROOM_RE.test(m.room || '')) {
        for (const r of ws.rooms) roomClients.get(r)?.delete(ws);   // one room at a time
        ws.rooms.clear(); ws.rooms.add(m.room);
        if (!roomClients.has(m.room)) roomClients.set(m.room, new Set());
        roomClients.get(m.room).add(ws);
        ws.send(JSON.stringify({ type: 'joined', room: m.room, backend: BACKEND_ID }));
      }
      if (m.type === 'ping') ws.send(JSON.stringify({ type: 'pong', t: m.t, backend: BACKEND_ID }));
    } catch (e) {}
  });
  ws.on('close', () => {
    metrics.ws_connections--;
    for (const r of ws.rooms) roomClients.get(r)?.delete(ws);
  });
});
// Heartbeat reaper (same 15 s cadence as Assignment 4).
setInterval(() => {
  for (const ws of wss.clients) {
    if (!ws.isAlive) { ws.terminate(); continue; }
    ws.isAlive = false; ws.ping();
  }
}, 15000).unref();

server.listen(PORT, HOST, () => log(`backend listening on ${HOST}:${PORT}, state=${STATE_URL}`));
connectFirehose();

// Graceful drain: finish in-flight requests, tell WS clients we are leaving.
let shuttingDown = false;
function shutdown() {
  if (shuttingDown) return; shuttingDown = true;
  log('SIGTERM: draining');
  for (const ws of wss.clients) ws.close(1001, 'server going away');
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 5000).unref();
}
process.on('SIGTERM', shutdown); process.on('SIGINT', shutdown);
