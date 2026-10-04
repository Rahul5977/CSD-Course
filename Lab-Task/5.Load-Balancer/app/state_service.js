#!/usr/bin/env node
'use strict';
// ============================================================================
// state_service.js — shared state for the load-balanced messaging app.
//
// All three backends (sys2/sys3/sys4) talk to this one service so that users,
// sessions, rooms and messages look identical no matter which backend the
// load balancer picked. It is deliberately tiny: an HTTP key-value + message
// log API, plus a WebSocket firehose so every backend hears about new
// messages immediately (cross-instance delivery).
//
// Zero external dependencies except the vendored `ws` package.
// Persistence: append-only JSONL for messages, debounced JSON snapshot for KV.
//
// ENV: PORT (default 5269), DATA_DIR (default ./data), LOG_LEVEL
// ============================================================================

const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer } = require(path.join(__dirname, 'vendor', 'ws'));

const PORT = parseInt(process.env.PORT || '5269', 10);
const HOST = process.env.HOST || '0.0.0.0';
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, 'data');
const MSG_FILE = path.join(DATA_DIR, 'messages.jsonl');
const KV_FILE = path.join(DATA_DIR, 'kv.json');

const started = Date.now();
fs.mkdirSync(DATA_DIR, { recursive: true });

// ── In-memory state, rebuilt from disk at boot ──────────────────────────────
// kv: { users: {name: rec}, sessions: {token: rec}, rooms: {id: rec} }
let kv = { users: {}, sessions: {}, rooms: {} };
const messages = new Map(); // room -> [{seq, ...entry}]
let stats = { requests: 0, appended: 0 };

try { kv = Object.assign(kv, JSON.parse(fs.readFileSync(KV_FILE, 'utf8'))); } catch (e) {}
try {
  for (const line of fs.readFileSync(MSG_FILE, 'utf8').split('\n')) {
    if (!line.trim()) continue;
    const m = JSON.parse(line);
    if (!messages.has(m.room)) messages.set(m.room, []);
    messages.get(m.room).push(m);
  }
} catch (e) {}

// Debounced KV snapshot — at most one disk write per second.
let kvDirty = false;
function saveKV() { kvDirty = true; }
setInterval(() => {
  if (!kvDirty) return;
  kvDirty = false;
  fs.writeFile(KV_FILE, JSON.stringify(kv), () => {});
}, 1000).unref();

const msgStream = fs.createWriteStream(MSG_FILE, { flags: 'a' });

// ── Pub/sub: backends subscribe over WS and get every new message event ─────
const subscribers = new Set();
function broadcast(event) {
  const data = JSON.stringify(event);
  for (const ws of subscribers) {
    if (ws.readyState === ws.OPEN) ws.send(data);
  }
}

// ── HTTP helpers ────────────────────────────────────────────────────────────
function json(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) });
  res.end(body);
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', c => { size += c.length; if (size > 65536) { reject(new Error('too large')); req.destroy(); } else chunks.push(c); });
    req.on('end', () => { try { resolve(chunks.length ? JSON.parse(Buffer.concat(chunks)) : {}); } catch (e) { reject(e); } });
    req.on('error', reject);
  });
}

// ── Routes ──────────────────────────────────────────────────────────────────
const server = http.createServer(async (req, res) => {
  stats.requests++;
  const u = new URL(req.url, 'http://x');
  const parts = u.pathname.split('/').filter(Boolean);
  try {
    // /kv/<ns>/<key>  GET | PUT | DELETE     ns ∈ users|sessions|rooms
    if (parts[0] === 'kv' && parts.length === 3 && kv[parts[1]]) {
      const ns = kv[parts[1]], key = decodeURIComponent(parts[2]);
      if (req.method === 'GET') return ns[key] ? json(res, 200, ns[key]) : json(res, 404, { error: 'not found' });
      if (req.method === 'PUT') { ns[key] = await readBody(req); saveKV(); return json(res, 200, { ok: true }); }
      if (req.method === 'DELETE') { delete ns[key]; saveKV(); return json(res, 200, { ok: true }); }
    }
    // GET /rooms — full room directory
    if (u.pathname === '/rooms' && req.method === 'GET') {
      return json(res, 200, { rooms: Object.values(kv.rooms) });
    }
    // POST /messages {room, entry} — append, assign seq, fan out
    if (u.pathname === '/messages' && req.method === 'POST') {
      const { room, entry } = await readBody(req);
      if (!room || !entry) return json(res, 400, { error: 'room and entry required' });
      if (!messages.has(room)) messages.set(room, []);
      const list = messages.get(room);
      const rec = Object.assign({ seq: list.length + 1, room }, entry);
      list.push(rec);
      msgStream.write(JSON.stringify(rec) + '\n');
      stats.appended++;
      broadcast({ type: 'msg', room, entry: rec });
      return json(res, 200, { ok: true, seq: rec.seq });
    }
    // GET /messages?room=&since=&limit=
    if (u.pathname === '/messages' && req.method === 'GET') {
      const room = u.searchParams.get('room');
      const since = parseInt(u.searchParams.get('since') || '0', 10);
      const limit = Math.min(parseInt(u.searchParams.get('limit') || '100', 10), 500);
      const list = (messages.get(room) || []).filter(m => m.seq > since).slice(-limit);
      return json(res, 200, { messages: list, last: list.length ? list[list.length - 1].seq : since });
    }
    if (u.pathname === '/health') {
      return json(res, 200, { status: 'ok', service: 'state', uptime: Math.round((Date.now() - started) / 1000), subscribers: subscribers.size, rooms: messages.size, requests: stats.requests });
    }
    json(res, 404, { error: 'no route' });
  } catch (e) {
    json(res, 500, { error: String(e.message || e) });
  }
});

// WS /subscribe — event firehose for backends
const wss = new WebSocketServer({ server, path: '/subscribe' });
wss.on('connection', ws => {
  subscribers.add(ws);
  ws.on('close', () => subscribers.delete(ws));
  ws.on('error', () => subscribers.delete(ws));
});

// Long keep-alive: the default 5 s races with the backends' pooled fetch
// connections ("other side closed" mid-request under load).
server.keepAliveTimeout = 65000;
server.headersTimeout = 70000;
server.listen(PORT, HOST, () => console.log(`[state] listening on ${HOST}:${PORT}, data in ${DATA_DIR}`));

process.on('SIGTERM', shutdown); process.on('SIGINT', shutdown);
function shutdown() {
  console.log('[state] shutting down');
  for (const ws of subscribers) ws.close(1001, 'server going away');
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 2000).unref();
}
