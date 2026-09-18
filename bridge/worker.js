/* Jarvis phone-link bridge.
 *
 * Machine-to-machine HTTPS for the Windows Jarvis PC client and the phone
 * dashboard. The hosted Jarvis web app only exposes typed actions behind a
 * browser-minted credential, which a headless PC client cannot obtain --
 * this worker is the narrow public bridge the phone panel anticipates.
 *
 * Protocol (matches jarvis/phonelink.py):
 *   POST /link/heartbeat  {"secret","pc_name","at"} -> {ok:true}
 *   GET  /link/commands?secret=...                  -> {commands:[{id,type}]}
 *   POST /link/ack        {"secret","id"}           -> {ok:true}
 *
 * Phone dashboard helpers:
 *   POST /link/pair                   -> {secret}            (one-time show)
 *   POST /link/claim  {"secret"}      -> {ok,paired,online,pc_name,last_seen}
 *   GET  /link/status?secret=...      -> {ok,online,last_seen,pc_name,pending,activity}
 *   POST /link/lock   {"secret"}      -> {ok:true,id}
 *   POST /link/unpair {"secret"}      -> {ok:true}
 *
 * Auth: the raw pairing secret travels in each request; the worker stores
 * only its SHA-256 hex digest as the KV key. Unknown digests get 401.
 * Only these link routes exist -- there is no general action dispatcher.
 */

const SECRET_MIN = 16;
const SECRET_MAX = 512;
const ONLINE_AFTER_MS = 75 * 1000; // PC heartbeats every 20s
const RATE_PER_MIN = 240;
const MAX_COMMANDS = 20;
const MAX_ACTIVITY = 50;

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "content-type",
  "access-control-allow-methods": "GET,POST,OPTIONS",
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", ...CORS },
  });
}
const bad = (status, error) => json({ ok: false, error }, status);
const nowIso = () => new Date().toISOString();
const newId = () =>
  globalThis.crypto.randomUUID
    ? crypto.randomUUID()
    : [...crypto.getRandomValues(new Uint8Array(16))]
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");

async function sha256Hex(s) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function cleanSecret(s) {
  if (typeof s !== "string") return null;
  s = s.trim();
  return s.length >= SECRET_MIN && s.length <= SECRET_MAX ? s : null;
}

function newSecret() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function readJson(req) {
  try {
    return await req.json();
  } catch {
    return {};
  }
}

// -- state ---------------------------------------------------------------
async function getState(env, hash) {
  return (await env.LINK_KV.get("link:" + hash, "json")) || null;
}
async function putState(env, hash, st) {
  await env.LINK_KV.put("link:" + hash, JSON.stringify(st));
}
function pushActivity(st, text) {
  st.activity.push({ t: nowIso(), text: String(text).slice(0, 200) });
  if (st.activity.length > MAX_ACTIVITY) st.activity = st.activity.slice(-MAX_ACTIVITY);
}

async function checkRate(env, hash) {
  const key = "rl:" + hash;
  const n = (parseInt((await env.LINK_KV.get(key)) || "0", 10) || 0) + 1;
  await env.LINK_KV.put(key, String(n), { expirationTtl: 60 });
  return n <= RATE_PER_MIN;
}

// Returns {hash} or {err:Response}. When createOk is true a missing record
// is fine (heartbeat creates it); otherwise unknown hash -> 401.
async function auth(env, secret, createOk = false) {
  const s = cleanSecret(secret);
  if (!s) return { err: bad(401, "bad secret") };
  const hash = await sha256Hex(s);
  if (!(await checkRate(env, hash))) return { err: bad(429, "rate limited") };
  const st = await getState(env, hash);
  if (!st && !createOk) return { err: bad(401, "unknown pairing") };
  return { hash, st };
}

function isOnline(st) {
  if (!st || !st.last_seen) return false;
  return Date.now() - Date.parse(st.last_seen) < ONLINE_AFTER_MS;
}

// -- handlers -------------------------------------------------------------
async function handlePair() {
  return json({ ok: true, secret: newSecret() });
}

async function handleClaim(env, req) {
  const { secret } = await readJson(req);
  const a = await auth(env, secret, true);
  if (a.err) return a.err;
  const st = a.st;
  return json({
    ok: true,
    paired: !!st,
    online: isOnline(st),
    pc_name: st ? st.pc_name : null,
    last_seen: st ? st.last_seen : null,
  });
}

async function handleHeartbeat(env, req) {
  const { secret, pc_name, at } = await readJson(req);
  const a = await auth(env, secret, true);
  if (a.err) return a.err;
  let st = a.st;
  const stamp = nowIso();
  if (!st) {
    st = {
      pc_name: String(pc_name || "My PC").slice(0, 80),
      created_at: stamp,
      last_seen: stamp,
      commands: [],
      activity: [],
    };
    pushActivity(st, "PC paired");
  } else {
    if (pc_name) st.pc_name = String(pc_name).slice(0, 80);
    st.last_seen = stamp; // heartbeat re-enables / marks online
  }
  await putState(env, a.hash, st);
  return json({ ok: true });
}

async function handleCommands(env, req) {
  const url = new URL(req.url);
  const a = await auth(env, url.searchParams.get("secret"));
  if (a.err) return a.err;
  const pending = a.st.commands.filter((c) => !c.acked);
  return json({ commands: pending.map((c) => ({ id: c.id, type: c.type })) });
}

async function handleAck(env, req) {
  const { secret, id } = await readJson(req);
  const a = await auth(env, secret);
  if (a.err) return a.err;
  const cmd = a.st.commands.find((c) => c.id === id && !c.acked);
  if (!cmd) return bad(404, "unknown command");
  cmd.acked = true;
  cmd.acked_at = nowIso();
  pushActivity(a.st, `${a.st.pc_name} ran ${cmd.type}`);
  await putState(env, a.hash, a.st);
  return json({ ok: true });
}

async function handleStatus(env, req) {
  const url = new URL(req.url);
  const a = await auth(env, url.searchParams.get("secret"));
  if (a.err) return a.err;
  const pending = a.st.commands.filter((c) => !c.acked);
  return json({
    ok: true,
    online: isOnline(a.st),
    last_seen: a.st.last_seen,
    pc_name: a.st.pc_name,
    pending: pending.length,
    activity: a.st.activity.slice(-20).reverse(),
  });
}

async function handleLock(env, req) {
  const { secret } = await readJson(req);
  const a = await auth(env, secret);
  if (a.err) return a.err;
  const pending = a.st.commands.filter((c) => !c.acked);
  if (pending.length >= MAX_COMMANDS) return bad(429, "command queue full");
  const cmd = { id: newId(), type: "lock", queued_at: nowIso(), acked: false };
  a.st.commands.push(cmd);
  pushActivity(a.st, "lock queued from phone");
  await putState(env, a.hash, a.st);
  return json({ ok: true, id: cmd.id });
}

async function handleUnpair(env, req) {
  const { secret } = await readJson(req);
  const a = await auth(env, secret);
  if (a.err) return a.err;
  await env.LINK_KV.delete("link:" + a.hash);
  await env.LINK_KV.delete("rl:" + a.hash);
  return json({ ok: true });
}

// -- router ---------------------------------------------------------------
export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    const path = new URL(req.url).pathname;
    try {
      if (req.method === "POST" && path === "/link/pair") return await handlePair();
      if (req.method === "POST" && path === "/link/claim") return await handleClaim(env, req);
      if (req.method === "POST" && path === "/link/heartbeat") return await handleHeartbeat(env, req);
      if (req.method === "GET" && path === "/link/commands") return await handleCommands(env, req);
      if (req.method === "POST" && path === "/link/ack") return await handleAck(env, req);
      if (req.method === "GET" && path === "/link/status") return await handleStatus(env, req);
      if (req.method === "POST" && path === "/link/lock") return await handleLock(env, req);
      if (req.method === "POST" && path === "/link/unpair") return await handleUnpair(env, req);
      if (req.method === "GET" && path === "/") return json({ ok: true, service: "jarvis-link-bridge" });
      return bad(404, "not found");
    } catch (e) {
      return bad(500, "bridge error");
    }
  },
};
