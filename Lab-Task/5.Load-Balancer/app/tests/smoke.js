#!/usr/bin/env node
'use strict';
// ============================================================================
// smoke.js — end-to-end test against real processes:
//   1. spawn state service + TWO backend instances (different BACKEND_IDs)
//   2. register → login → create room → send plain → fetch  (backend 1)
//   3. lock room (client-side key derivation, Assignment-4 scheme in Node
//      webcrypto) → send ciphertext → fetch → decrypt → verify round-trip
//   4. prove the store holds ciphertext only (no plaintext on disk)
//   5. CROSS-INSTANCE: WS subscribed on backend 1 receives a message that was
//      POSTed to backend 2 — the make-or-break test for load balancing.
// Exit code 0 = all pass.
// ============================================================================
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { webcrypto } = require('crypto');
const subtle = webcrypto.subtle;
const { WebSocket } = require(path.join(__dirname, '..', 'vendor', 'ws'));

const APP = path.join(__dirname, '..');
const DATA = fs.mkdtempSync(path.join(os.tmpdir(), 'chat-smoke-'));
const SPORT = 15290, B1 = 18091, B2 = 18093;   // own ports — never clash with a dev cluster
const procs = [];
let failures = 0;

function ok(name, cond) {
  console.log((cond ? '  ✓ ' : '  ✗ ') + name);
  if (!cond) failures++;
}
function boot(script, env) {
  const p = spawn('node', [path.join(APP, script)], { env: Object.assign({}, process.env, env), stdio: ['ignore', 'pipe', 'pipe'] });
  p.stderr.on('data', d => process.stderr.write(`[${env.BACKEND_ID || 'state'}] ${d}`));
  procs.push(p);
  return p;
}
async function waitHealthy(url, tries = 50) {
  for (let i = 0; i < tries; i++) {
    try { const r = await fetch(url); if (r.ok) return true; } catch (e) {}
    await new Promise(r => setTimeout(r, 100));
  }
  throw new Error('never became healthy: ' + url);
}
// Minimal cookie jar (per simulated browser).
function jar() {
  let cookie = '';
  return {
    async api(base, method, p, body) {
      const res = await fetch(base + p, {
        method, headers: Object.assign(body ? { 'Content-Type': 'application/json' } : {}, cookie ? { Cookie: cookie } : {}),
        body: body ? JSON.stringify(body) : undefined,
      });
      const sc = res.headers.get('set-cookie');
      if (sc) cookie = sc.split(';')[0];
      const data = await res.json();
      return { status: res.status, data, backend: res.headers.get('x-backend-id') };
    },
    get cookie() { return cookie; },
  };
}

// ── Assignment-4 room crypto, reimplemented independently in Node ───────────
const enc = new TextEncoder(), dec = new TextDecoder();
const b64 = buf => Buffer.from(buf).toString('base64');
const unb64 = s => new Uint8Array(Buffer.from(s, 'base64'));
async function makeRoomKey(passphrase, roomId, epoch) {
  const salt = await subtle.digest('SHA-256', enc.encode('ChatFat-room-v1|' + roomId));
  const base = await subtle.importKey('raw', enc.encode(passphrase), 'PBKDF2', false, ['deriveBits']);
  const raw = await subtle.deriveBits({ name: 'PBKDF2', salt, iterations: 250000, hash: 'SHA-256' }, base, 256);
  const key = await subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
  const hmacKey = await subtle.importKey('raw', raw, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const verifier = b64(await subtle.sign('HMAC', hmacKey, enc.encode('ChatFat-room-verify|' + roomId + '|' + epoch)));
  return { key, raw, epoch, verifier };
}
const aadFor = (roomId, n, kid) => enc.encode(roomId + '|' + n + '|' + kid);
async function encryptRoom(entry, roomId, payload) {
  const iv = webcrypto.getRandomValues(new Uint8Array(12));
  const n = b64(webcrypto.getRandomValues(new Uint8Array(16)));
  const ct = await subtle.encrypt({ name: 'AES-GCM', iv, additionalData: aadFor(roomId, n, entry.epoch) }, entry.key, enc.encode(JSON.stringify(payload)));
  return { alg: 'A256GCM', kid: entry.epoch, n, iv: b64(iv), ct: b64(ct), aadv: 1 };
}
async function decryptRoom(entry, roomId, env) {
  const pt = await subtle.decrypt({ name: 'AES-GCM', iv: unb64(env.iv), additionalData: aadFor(roomId, env.n, env.kid) }, entry.key, unb64(env.ct));
  return JSON.parse(dec.decode(pt));
}

(async function main() {
  console.log('smoke: booting state + 2 backends (data in ' + DATA + ')');
  boot('state_service.js', { PORT: String(SPORT), DATA_DIR: DATA, HOST: '127.0.0.1' });
  await waitHealthy(`http://127.0.0.1:${SPORT}/health`);
  boot('server.js', { PORT: String(B1), BACKEND_ID: 'test-b1', STATE_URL: `http://127.0.0.1:${SPORT}`, HOST: '127.0.0.1', LOG_LEVEL: 'silent' });
  boot('server.js', { PORT: String(B2), BACKEND_ID: 'test-b2', STATE_URL: `http://127.0.0.1:${SPORT}`, HOST: '127.0.0.1', LOG_LEVEL: 'silent' });
  await waitHealthy(`http://127.0.0.1:${B1}/health`);
  await waitHealthy(`http://127.0.0.1:${B2}/health`);
  const base1 = `http://127.0.0.1:${B1}`, base2 = `http://127.0.0.1:${B2}`;

  console.log('— auth —');
  const alice = jar(), bob = jar();
  let r = await alice.api(base1, 'POST', '/api/register', { username: 'alice', password: 'correct-horse-9' });
  ok('register alice → 200 + cookie', r.status === 200 && alice.cookie.startsWith('session='));
  ok('X-Backend-Id header present', r.backend === 'test-b1');
  r = await alice.api(base1, 'POST', '/api/register', { username: 'alice', password: 'correct-horse-9' });
  ok('duplicate register → 409', r.status === 409);
  r = await bob.api(base2, 'POST', '/api/register', { username: 'bob', password: 'hunter2hunter2' });
  ok('register bob on backend 2', r.status === 200);
  r = await jar().api(base1, 'POST', '/api/login', { username: 'alice', password: 'wrong-password' });
  ok('wrong password → 401', r.status === 401);
  const alice2 = jar();
  r = await alice2.api(base2, 'POST', '/api/login', { username: 'alice', password: 'correct-horse-9' });
  ok('session created on b1 works via login on b2 (shared users)', r.status === 200);
  r = await bob.api(base1, 'GET', '/api/me');
  ok('bob session made on b2 is valid on b1 (shared sessions)', r.status === 200 && r.data.username === 'bob');

  console.log('— plaintext room —');
  r = await alice.api(base1, 'POST', '/api/rooms', { id: 'lobby' });
  ok('create room lobby', r.status === 200 && r.data.id === 'lobby');
  r = await alice.api(base1, 'POST', '/api/messages', { room: 'lobby', text: 'hello world' });
  ok('send plain message', r.status === 200 && r.data.seq === 1);
  r = await bob.api(base2, 'GET', '/api/messages?room=lobby&since=0');
  ok('bob fetches it from backend 2 (shared messages)', r.status === 200 && r.data.messages.length === 1 && r.data.messages[0].text === 'hello world');

  console.log('— locked room (Assignment-4 E2E scheme) —');
  await alice.api(base1, 'POST', '/api/rooms', { id: 'vault' });
  const keyA = await makeRoomKey('a very strong passphrase', 'vault', 1);
  r = await alice.api(base1, 'POST', '/api/rooms/vault/lock', { epoch: 1, verifier: keyA.verifier });
  ok('lock room', r.status === 200 && r.data.locked === true && r.data.epoch === 1);
  const secret = 'the launch code is 0000';
  const env = await encryptRoom(keyA, 'vault', { text: secret });
  r = await alice.api(base1, 'POST', '/api/messages', { room: 'vault', env });
  ok('send encrypted message', r.status === 200);
  r = await alice.api(base1, 'POST', '/api/messages', { room: 'vault', text: 'plaintext should be refused' });
  ok('plaintext into locked room → 400', r.status === 400);
  r = await alice.api(base1, 'POST', '/api/messages', { room: 'vault', env: Object.assign({}, env, { iv: b64(new Uint8Array(5)) }) });
  ok('malformed envelope (bad IV) → 400', r.status === 400);
  r = await bob.api(base2, 'GET', '/api/messages?room=vault&since=0');
  const encMsg = r.data.messages.find(m => m.kind === 'enc');
  ok('fetch returns ciphertext envelope', !!encMsg && encMsg.env.alg === 'A256GCM');
  const keyB = await makeRoomKey('a very strong passphrase', 'vault', 1);   // bob derives independently
  ok('bob derives same verifier from passphrase', keyB.verifier === keyA.verifier);
  const payload = await decryptRoom(keyB, 'vault', encMsg.env);
  ok('decrypt round-trip matches', payload.text === secret);

  console.log('— ciphertext-only store proof —');
  const disk = fs.readFileSync(path.join(DATA, 'messages.jsonl'), 'utf8');
  ok('plaintext secret NOT on disk', !disk.includes('launch code'));
  ok('ciphertext IS on disk', disk.includes(env.ct.slice(0, 24)));

  console.log('— cross-instance delivery (WS on b1, POST on b2) —');
  const received = new Promise((resolve, reject) => {
    const sock = new WebSocket(`ws://127.0.0.1:${B1}/ws`, { headers: { Cookie: alice.cookie } });
    const timer = setTimeout(() => reject(new Error('timeout waiting for WS delivery')), 5000);
    sock.on('message', d => {
      const m = JSON.parse(d);
      if (m.type === 'hello') sock.send(JSON.stringify({ type: 'join', room: 'lobby' }));
      if (m.type === 'joined') bob.api(base2, 'POST', '/api/messages', { room: 'lobby', text: 'crossing instances' });
      if (m.type === 'msg' && m.entry.text === 'crossing instances') { clearTimeout(timer); sock.close(); resolve(m); }
    });
    sock.on('error', reject);
  });
  try {
    const m = await received;
    ok('message POSTed to b2 arrived over WS on b1', true);
    ok('delivery tagged with serving backend', m.via === 'test-b1');
  } catch (e) { ok('cross-instance WS delivery (' + e.message + ')', false); }

  console.log('— health/metrics —');
  r = await fetch(`${base1}/health`).then(x => x.json());
  ok('/health ok + firehose up', r.status === 'ok' && r.state_firehose === true);
  r = await fetch(`${base2}/metrics`).then(x => x.json());
  ok('/metrics has counters', r.requests_total > 0 && typeof r.latency_ms.p95 === 'number');

  console.log(failures === 0 ? '\nALL TESTS PASSED' : `\n${failures} FAILURES`);
  cleanup();
  process.exit(failures === 0 ? 0 : 1);
})().catch(e => { console.error('smoke crashed:', e); cleanup(); process.exit(1); });

function cleanup() { for (const p of procs) try { p.kill('SIGTERM'); } catch (e) {} }
