// ============================================================================
// app.js — chat client. Sends over HTTP POST, receives over a WebSocket that
// the load balancer pins to one backend. Locked rooms encrypt/decrypt in the
// browser via RoomCrypto (Assignment-4 scheme) — the server never sees text.
// ============================================================================
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var me = null, currentRoom = null, roomRec = null, roomKey = null;
  var lastSeq = 0, ws = null, wsBackend = '—', pollTimer = null;

  // ── tiny fetch wrapper ────────────────────────────────────────────────────
  async function api(method, path, body) {
    var res = await fetch(path, {
      method: method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
      credentials: 'same-origin',
    });
    var backend = res.headers.get('X-Backend-Id');
    if (backend) setBadge(backend);
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) throw new Error(data.error || (res.status + ''));
    return data;
  }
  function setBadge(b) { $('backend-badge').textContent = b; }

  // ── auth ──────────────────────────────────────────────────────────────────
  function showApp() {
    $('auth').hidden = true; $('app').hidden = false;
    $('me').textContent = me;
    loadRooms(); connectWS();
  }
  async function tryResume() {
    try { var r = await api('GET', '/api/me'); me = r.username; showApp(); }
    catch (e) { /* not signed in — stay on auth screen */ }
  }
  $('auth-form').addEventListener('submit', function (ev) { ev.preventDefault(); auth('/api/login'); });
  $('btn-register').addEventListener('click', function () { auth('/api/register'); });
  async function auth(path) {
    $('auth-error').hidden = true;
    try {
      var r = await api('POST', path, { username: $('auth-user').value.trim(), password: $('auth-pass').value });
      me = r.username; showApp();
    } catch (e) {
      $('auth-error').textContent = e.message; $('auth-error').hidden = false;
    }
  }
  $('btn-logout').addEventListener('click', async function () {
    try { await api('POST', '/api/logout'); } catch (e) {}
    location.reload();
  });

  // ── rooms ─────────────────────────────────────────────────────────────────
  async function loadRooms() {
    try {
      var r = await api('GET', '/api/rooms');
      var nav = $('rooms'); nav.innerHTML = '';
      r.rooms.sort(function (a, b) { return a.id < b.id ? -1 : 1; }).forEach(function (room) {
        var b = document.createElement('button');
        b.textContent = room.id;
        if (room.locked) {
          var lock = document.createElement('span'); lock.textContent = '🔒'; b.appendChild(lock);
        }
        if (currentRoom === room.id) b.classList.add('active');
        b.addEventListener('click', function () { enterRoom(room.id); });
        nav.appendChild(b);
      });
    } catch (e) {}
  }
  $('btn-new-room').addEventListener('click', createRoom);
  $('new-room-name').addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { ev.preventDefault(); createRoom(); } });
  async function createRoom() {
    var id = $('new-room-name').value.trim().toLowerCase();
    if (!id) return;
    try { await api('POST', '/api/rooms', { id: id }); $('new-room-name').value = ''; await loadRooms(); enterRoom(id); }
    catch (e) { alert(e.message); }
  }

  async function enterRoom(id) {
    currentRoom = id; lastSeq = 0; roomKey = null;
    $('messages').innerHTML = '';
    $('composer').hidden = false;
    try { roomRec = await api('POST', '/api/rooms', { id: id }); } catch (e) { return; }
    updateRoomHead();
    if (roomRec.locked) {
      roomKey = await RoomCrypto.recall(id, roomRec.epoch);
      if (!roomKey) askPassphrase('unlock');
      else updateRoomHead();
    }
    if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: 'join', room: id }));
    await loadHistory();
    loadRooms();
  }
  function updateRoomHead() {
    $('room-title').textContent = currentRoom || 'Pick a room';
    var lockInfo = '';
    if (roomRec && roomRec.locked) {
      lockInfo = roomKey ? ('🔒 encrypted · key ' + roomKey.fingerprint) : '🔒 encrypted · key needed';
    }
    $('room-lock').textContent = lockInfo;
    $('btn-lock').hidden = !roomRec || roomRec.locked;
  }

  // ── lock / unlock ─────────────────────────────────────────────────────────
  var modalMode = 'unlock';
  $('btn-lock').addEventListener('click', function () { askPassphrase('lock'); });
  function askPassphrase(mode) {
    modalMode = mode;
    $('key-title').textContent = mode === 'lock' ? 'Lock this room' : 'Unlock room';
    $('key-hint').textContent = mode === 'lock'
      ? 'Pick a shared passphrase (≥ 10 chars). Members need it to read this room. Locking is permanent.'
      : 'This room is end-to-end encrypted. Enter the shared passphrase.';
    $('key-ok').textContent = mode === 'lock' ? 'Lock' : 'Unlock';
    $('key-error').hidden = true; $('key-pass').value = '';
    $('key-modal').showModal();
  }
  $('key-cancel').addEventListener('click', function () { $('key-modal').close(); });
  $('key-form').addEventListener('submit', async function (ev) {
    ev.preventDefault();
    var pass = $('key-pass').value;
    try {
      if (modalMode === 'lock') {
        var epoch = roomRec.epoch + 1;
        var entry = await RoomCrypto.makeRoomKey(pass, currentRoom, epoch);
        roomRec = await api('POST', '/api/rooms/' + currentRoom + '/lock', { epoch: epoch, verifier: entry.verifier });
        roomKey = entry;
      } else {
        var entry2 = await RoomCrypto.makeRoomKey(pass, currentRoom, roomRec.epoch);
        if (entry2.verifier !== roomRec.verifier) { throw new Error('Wrong passphrase for this room.'); }
        roomKey = entry2;
      }
      RoomCrypto.remember(currentRoom, roomKey.epoch, roomKey.raw);
      $('key-modal').close();
      updateRoomHead();
      $('messages').innerHTML = ''; lastSeq = 0; await loadHistory();
    } catch (e) {
      $('key-error').textContent = e.message; $('key-error').hidden = false;
    }
  });

  // ── messages ──────────────────────────────────────────────────────────────
  async function loadHistory() {
    try {
      var r = await api('GET', '/api/messages?room=' + currentRoom + '&since=' + lastSeq);
      for (var i = 0; i < r.messages.length; i++) await renderMessage(r.messages[i]);
      scrollDown();
    } catch (e) {}
  }
  async function renderMessage(m) {
    if (m.seq && m.seq <= lastSeq) return;         // dedupe WS vs poll
    if (m.seq) lastSeq = Math.max(lastSeq, m.seq);
    if (m.roomMeta) { roomRec = m.roomMeta; updateRoomHead(); }
    var wrap = document.createElement('div');
    var mine = m.from === me;
    wrap.className = 'msg' + (mine ? ' mine' : '') + (m.kind === 'system' ? ' system' : '');
    var meta = document.createElement('div'); meta.className = 'meta';
    meta.textContent = (m.kind === 'system' ? '' : (m.from + ' · ')) + new Date(m.ts).toLocaleTimeString();
    var bubble = document.createElement('div'); bubble.className = 'bubble';
    if (m.kind === 'enc') {
      var out = roomKey ? await RoomCrypto.decryptRoom(roomKey, m.room || currentRoom, m.env) : { ok: false, reason: 'no-key' };
      if (out.ok) bubble.textContent = out.payload.text;
      else { bubble.textContent = out.reason === 'integrity' ? '⚠ integrity check failed' : '🔒 encrypted (no key)'; bubble.classList.add('undecryptable'); }
    } else {
      bubble.textContent = m.text;
    }
    if (m.kind !== 'system') wrap.appendChild(meta);
    wrap.appendChild(bubble);
    var box = $('messages');
    var empty = box.querySelector('.empty'); if (empty) empty.remove();
    box.appendChild(wrap);
  }
  function scrollDown() { var box = $('messages'); box.scrollTop = box.scrollHeight; }

  $('composer').addEventListener('submit', async function (ev) {
    ev.preventDefault();
    var text = $('msg-input').value.trim();
    if (!text || !currentRoom) return;
    $('msg-input').value = '';
    try {
      if (roomRec && roomRec.locked) {
        if (!roomKey) { askPassphrase('unlock'); return; }
        var env = await RoomCrypto.encryptRoom(roomKey, currentRoom, { text: text });
        await api('POST', '/api/messages', { room: currentRoom, env: env });
      } else {
        await api('POST', '/api/messages', { room: currentRoom, text: text });
      }
    } catch (e) { alert('Send failed: ' + e.message); }
  });

  // ── live delivery: WS primary, polling fallback ───────────────────────────
  function setConn(on, label) {
    var el = $('conn');
    el.className = 'conn ' + (on ? 'on' : 'off');
    el.textContent = label;
  }
  function connectWS() {
    var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
    ws = new WebSocket(proto + location.host + '/ws');
    ws.onopen = function () { setConn(true, 'Connected'); stopPolling(); if (currentRoom) ws.send(JSON.stringify({ type: 'join', room: currentRoom })); };
    ws.onmessage = async function (ev) {
      var m = JSON.parse(ev.data);
      if (m.type === 'hello' || m.type === 'joined') { wsBackend = m.backend; setBadge(m.backend); }
      if (m.type === 'msg' && m.room === currentRoom) { await renderMessage(m.entry); scrollDown(); }
      if (m.type === 'room') loadRooms();
    };
    ws.onclose = function () { setConn(false, 'Reconnecting…'); startPolling(); setTimeout(connectWS, 2000); };
    ws.onerror = function () { ws.close(); };
  }
  function startPolling() { if (!pollTimer) pollTimer = setInterval(function () { if (currentRoom) loadHistory(); }, 3000); }
  function stopPolling() { clearInterval(pollTimer); pollTimer = null; }

  tryResume();
})();
