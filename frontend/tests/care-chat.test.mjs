import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/features/chat/chat-session.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { ChatSession, retryAfterDelay } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

const tick = () => new Promise(resolve => setImmediate(resolve));
const response = value => new Response(JSON.stringify(value), { status: 200 });
const conversation = (id = "room-a", last_seq = 1) => ({ id, owner_id: "me", title: id, last_seq, last_message_at: `2026-10-02T00:00:${String(last_seq).padStart(2, "0")}`, created_at: "2026-10-01", source_type: "direct" });
const message = (seq, overrides = {}) => ({ id: `message-${seq}`, conversation_id: "room-a", sender_id: "peer", seq, body: `消息${seq}`, client_message_id: null, created_at: `2026-10-02T00:00:${String(seq).padStart(2, "0")}`, ...overrides });
const page = (items, sync = "cursor-1", overrides = {}) => ({ conversation_id: "room-a", items, sync_cursor: sync, older_cursor: "older-1", has_more: false, ...overrides });

function harness(handler) {
  const calls = [], timers = new Map(), states = [];
  let serial = 0, time = 10000;
  const session = new ChatSession({
    accountId: "me", changed: state => states.push(state), uuid: () => `intent-${++serial}`, now: () => time,
    schedule: (callback, delay) => { const id = ++serial; timers.set(id, { callback, delay }); return id; },
    cancel: id => timers.delete(id),
    fetch: async (path, init) => {
      calls.push({ path, init });
      const handled = handler?.(path, init);
      if (handled !== undefined) return handled;
      if (path.startsWith("/api/v2/conversations?")) return response({ items: [conversation()], next_cursor: null, has_more: false });
      return response(page(path.includes("after=") ? [] : [message(1)]));
    }
  });
  return { session, calls, timers, states, advance: ms => { time += ms; },
    runTimer: async () => { const [id, timer] = timers.entries().next().value; timers.delete(id); timer.callback(); await tick(); } };
}

test("send ACK does not skip a peer message and merges a later GET without duplicates", async () => {
  let intent;
  const h = harness((path, init) => {
    if (init.method === "POST") {
      intent = JSON.parse(init.body).client_message_id;
      return response(message(3, { sender_id: "me", client_message_id: intent }));
    }
    if (path.includes("after=cursor-1")) return response(page([message(2), message(3, { sender_id: "me", client_message_id: intent })], "cursor-3"));
  });
  await h.session.loadConversations(); await tick();
  assert.equal(h.session.send("你好"), true);
  assert.equal(h.session.send("你好"), false);
  await tick();
  assert.deepEqual(h.session.state.messages.map(item => item.seq), [1, 2, 3]);
  assert.equal(h.session.state.pending.length, 0);
  assert.equal(h.calls.filter(call => call.init.method === "POST").length, 1);
  assert.equal(h.calls.filter(call => call.path.startsWith("/api/v2/conversations?")).length, 1);
  assert.ok(h.calls.some(call => call.path.endsWith("after=cursor-1")));
  h.session.dispose();
});

test("a lost POST response keeps the same intent and body on retry", async () => {
  const posted = [];
  const h = harness((path, init) => {
    if (init.method !== "POST") return;
    const payload = JSON.parse(init.body); posted.push(payload);
    if (posted.length === 1) return Promise.reject(new Error("连接中断"));
    return response(message(2, { sender_id: "me", client_message_id: payload.client_message_id }));
  });
  await h.session.loadConversations(); await tick();
  h.session.send("需要确认的内容"); await tick();
  const failed = h.session.state.pending[0];
  assert.equal(failed.status, "failed");
  h.session.retry(failed.client_message_id);
  h.session.retry(failed.client_message_id);
  await tick();
  assert.equal(posted.length, 2);
  assert.deepEqual(posted[0], posted[1]);
  assert.equal(h.session.state.pending.length, 0);
  h.session.dispose();
});

test("a GET confirmation wins over a delayed POST failure", async () => {
  let rejectPost, intent;
  const h = harness((path, init) => {
    if (init.method === "POST") {
      intent = JSON.parse(init.body).client_message_id;
      return new Promise((resolve, reject) => { rejectPost = reject; });
    }
    if (path.includes("after=")) return response(page([message(2, { sender_id: "me", client_message_id: intent })], "cursor-2"));
  });
  await h.session.loadConversations(); await tick();
  h.session.send("已被服务器接收"); await tick();
  await h.session.sync();
  rejectPost(new Error("响应丢失")); await tick();
  assert.equal(h.session.state.pending.length, 0);
  assert.deepEqual(h.session.state.messages.map(item => item.seq), [1, 2]);
  h.session.dispose();
});

test("a peer using the same client ID cannot confirm this account's pending message", async () => {
  let resolvePost, intent;
  const h = harness((path, init) => {
    if (init.method === "POST") {
      intent = JSON.parse(init.body).client_message_id;
      return new Promise(resolve => { resolvePost = resolve; });
    }
    if (path.includes("after=")) return response(page([message(2, { client_message_id: intent })], "cursor-2"));
  });
  await h.session.loadConversations(); await tick();
  h.session.send("本人待确认的消息"); await tick();
  await h.session.sync();
  assert.equal(h.session.state.pending.length, 1);
  resolvePost(response(message(3, { sender_id: "me", client_message_id: intent })));
  await tick();
  assert.equal(h.session.state.pending.length, 0);
  h.session.dispose();
});

test("switching conversations aborts requests and rejects stale message results", async () => {
  let resolveOld, oldSignal;
  const h = harness((path, init) => {
    if (path.includes("/room-a/messages")) {
      oldSignal = init.signal;
      return new Promise(resolve => { resolveOld = resolve; });
    }
    if (path.includes("/room-b/messages")) return response(page([message(9, { conversation_id: "room-b" })], "cursor-b"));
  });
  h.session.select("room-a");
  h.session.select("room-b"); await tick();
  resolveOld(response(page([message(1)]))); await tick();
  assert.equal(oldSignal.aborted, true);
  assert.equal(h.session.state.selectedId, "room-b");
  assert.deepEqual(h.session.state.messages.map(item => item.seq), [9]);
  h.session.dispose();
});

test("polling never overlaps, stops while hidden, and resumes on visibility", async () => {
  let resolvePending, pendingSignal;
  const h = harness((path, init) => {
    if (!path.includes("after=")) return;
    pendingSignal = init.signal;
    return new Promise(resolve => { resolvePending = resolve; });
  });
  await h.session.loadConversations(); await tick();
  const inflight = h.session.sync();
  void h.session.sync(); void h.session.sync();
  assert.equal(h.calls.filter(call => call.path.includes("after=")).length, 1);
  h.session.setVisible(false);
  assert.equal(pendingSignal.aborted, true);
  resolvePending(response(page([message(2)]))); await inflight;
  assert.equal(h.timers.size, 0);
  assert.deepEqual(h.session.state.messages.map(item => item.seq), [1]);
  h.session.setVisible(true);
  assert.equal(h.calls.filter(call => call.path.includes("after=")).length, 2);
  resolvePending(response(page([message(2)], "cursor-2"))); await tick();
  h.session.dispose();
});

test("incremental pages deliver 1000 messages without duplicates or skips", async () => {
  const h = harness(path => {
    if (!path.includes("/messages")) return;
    const after = Number(new URL(path, "https://care.test").searchParams.get("after") || 0);
    const end = Math.min(after + 50, 1000);
    const items = Array.from({ length: end - after }, (_, offset) => message(after + offset + 1));
    return response(page(items, String(end), { has_more: after > 0 && end < 1000 }));
  });
  await h.session.loadConversations(); await tick();
  await h.session.sync();
  while (h.session.state.messages.length < 1000) await h.runTimer();
  assert.deepEqual(h.session.state.messages.map(item => item.seq), Array.from({ length: 1000 }, (_, i) => i + 1));
  assert.equal(h.calls.filter(call => call.path.includes("/messages")).length, 20);
  h.session.dispose();
});

test("history pagination does not move the incremental cursor backwards", async () => {
  const h = harness(path => {
    if (path.includes("before=")) return response(page([message(1)], "cursor-1"));
    if (path.includes("/messages") && !path.includes("after=")) return response(page([message(50)], "cursor-50", { has_more: true, older_cursor: "older-50" }));
  });
  await h.session.loadConversations(); await tick();
  await h.session.loadOlder();
  await h.session.sync();
  assert.ok(h.calls.at(-1).path.endsWith("after=cursor-50"));
  assert.deepEqual(h.session.state.messages.map(item => item.seq), [1, 50]);
  h.session.dispose();
});

test("conversation pagination deduplicates rooms and retains newer locally acknowledged ordering", async () => {
  let listCalls = 0;
  const h = harness(path => {
    if (!path.startsWith("/api/v2/conversations?")) return;
    listCalls++;
    return response(listCalls === 1
      ? { items: [conversation("room-a", 9)], next_cursor: "page-two", has_more: true }
      : { items: [conversation("room-a", 2), conversation("room-b", 3)], next_cursor: null, has_more: false });
  });
  await h.session.loadConversations(); await tick();
  await h.session.loadConversations(true);
  assert.equal(h.session.state.conversations.length, 2);
  assert.equal(h.session.state.conversations[0].id, "room-a");
  assert.equal(h.session.state.conversations[0].last_seq, 9);
  assert.ok(h.calls.some(call => call.path.endsWith("cursor=page-two")));
  h.session.dispose();
});

test("Retry-After blocks both polling and manual retry until the server's deadline", async () => {
  let messageCalls = 0;
  const h = harness(path => {
    if (!path.includes("/messages")) return;
    messageCalls++;
    if (messageCalls === 1) return new Response(JSON.stringify({ detail: "请求过多" }), { status: 429, headers: { "Retry-After": "7" } });
    return response(page([message(1)]));
  });
  await h.session.loadConversations(); await tick();
  assert.ok([...h.timers.values()][0].delay >= 7000);
  await h.session.sync();
  assert.equal(messageCalls, 1);
  h.advance(7000);
  await h.session.sync();
  assert.equal(messageCalls, 2);
  assert.equal(h.session.state.ready, true);
  assert.equal(retryAfterDelay("Thu, 01 Oct 2026 00:00:10 GMT", Date.parse("2026-10-01T00:00:00Z")), 10000);
  h.session.dispose();
});

test("disposing an account aborts pending calls and publishes no stale data", async () => {
  let resolveRequest, signal;
  const h = harness((path, init) => {
    signal = init.signal;
    return new Promise(resolve => { resolveRequest = resolve; });
  });
  const loading = h.session.loadConversations();
  const count = h.states.length;
  h.session.dispose();
  resolveRequest(response({ items: [conversation()], next_cursor: null, has_more: false }));
  await loading;
  assert.equal(signal.aborted, true);
  assert.equal(h.states.length, count);
  assert.equal(h.session.state.messages.length, 0);
  assert.equal(h.session.state.conversations.length, 0);
  assert.equal(h.timers.size, 0);
});
