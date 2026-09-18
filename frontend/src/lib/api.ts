import { clearCurrentSession, loadCurrentSession, sessionExpiredEvent } from "./session";

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const original = input instanceof Request ? input : undefined;
  const url = new URL(original?.url ?? String(input), window.location.origin);
  if (url.origin !== window.location.origin || !url.pathname.startsWith("/api/v1/")) {
    throw new Error("接口地址必须属于当前站点。");
  }
  const headers = new Headers(init?.headers ?? original?.headers);
  const token = loadCurrentSession()?.access_token;
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const controller = new AbortController();
  const incomingSignal = init?.signal ?? original?.signal;
  const signal = incomingSignal
    ? AbortSignal.any([controller.signal, incomingSignal]) : controller.signal;
  const timeout = window.setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await window.fetch(input, {
      ...init, headers, signal, redirect: "error", cache: "no-store"
    });
    if (response.status === 401 && token && loadCurrentSession()?.access_token === token) {
      clearCurrentSession();
      window.dispatchEvent(new Event(sessionExpiredEvent));
    }
    return response;
  } finally {
    // Once response headers arrive, SSE controls the lifetime of its readable body.
    window.clearTimeout(timeout);
  }
}
