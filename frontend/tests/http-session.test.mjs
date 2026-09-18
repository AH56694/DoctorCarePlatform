import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

function compiledModule(path, replacements = {}) {
  let source = readFileSync(new URL(path, import.meta.url), "utf8");
  for (const [before, after] of Object.entries(replacements)) source = source.replace(before, after);
  const result = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext }
  });
  return `data:text/javascript;base64,${Buffer.from(result.outputText).toString("base64")}`;
}

const sessionUrl = compiledModule("../src/lib/session.ts");
const session = await import(sessionUrl);
const { apiFetch } = await import(compiledModule("../src/lib/api.ts", { '"./session"': JSON.stringify(sessionUrl) }));
const key = "doctor-care-platform-current-session";
const account = {
  id: "user-1", phone: "13800000000", display_name: "User", status: "active",
  active_role: "patient", roles: [], certifications: [], caregiver_profile: null,
  patient_profile: { basic_info: { medical_history: "private condition" } }
};

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key)
  };
}

function setup() {
  globalThis.localStorage = storage();
  globalThis.sessionStorage = storage();
  const events = [];
  globalThis.window = {
    location: { origin: "https://care.test" }, setTimeout, clearTimeout,
    dispatchEvent: (event) => events.push(event.type)
  };
  return events;
}

test("session storage excludes clinical data and clears old persistent tokens", () => {
  setup();
  localStorage.setItem(key, "legacy-token-and-clinical-data");
  session.saveCurrentSession(account, "token-1");
  assert.equal(session.loadCurrentSession().access_token, "token-1");
  assert.equal(localStorage.getItem(key), null);
  assert.equal(sessionStorage.getItem(key).includes("private condition"), false);
  session.clearCurrentSession();
  assert.equal(session.loadCurrentSession(), null);
});

test("API credentials are restricted to this site's API and redirects fail", async () => {
  setup();
  session.saveCurrentSession(account, "token-1");
  let calls = 0;
  window.fetch = async (input, options) => {
    calls++;
    assert.equal(options.headers.get("Authorization"), "Bearer token-1");
    assert.equal(options.redirect, "error");
    return new Response("{}", { status: 200 });
  };
  await assert.rejects(apiFetch("https://other.test/api/v1/accounts"));
  await assert.rejects(apiFetch("/other-page"));
  assert.equal(calls, 0);
  await apiFetch("/api/v1/ai/sessions");
  assert.equal(calls, 1);
});

test("expired token clears UI session; old responses cannot clear a new login", async () => {
  const events = setup();
  session.saveCurrentSession(account, "token-1");
  window.fetch = async () => new Response("{}", { status: 401 });
  await apiFetch("/api/v1/ai/sessions");
  assert.equal(session.loadCurrentSession(), null);
  assert.deepEqual(events, [session.sessionExpiredEvent]);
  session.saveCurrentSession(account, "token-1");
  window.fetch = async () => {
    session.saveCurrentSession(account, "token-2");
    return new Response("{}", { status: 401 });
  };
  await apiFetch("/api/v1/ai/sessions");
  assert.equal(session.loadCurrentSession().access_token, "token-2");
});

test("caller cancellation stays connected after SSE response headers", async () => {
  setup();
  let signal;
  window.fetch = async (input, options) => {
    signal = options.signal;
    return new Response("data: {}\n\n", { status: 200 });
  };
  const controller = new AbortController();
  await apiFetch("/api/v1/ai/chat/stream", { signal: controller.signal });
  assert.equal(signal.aborted, false);
  controller.abort();
  assert.equal(signal.aborted, true);
});
