import type { CareConversation, CareMessage } from "../../types";

export type ConversationPage = { items: CareConversation[]; next_cursor: string | null; has_more: boolean };
export type MessagePage = {
  conversation_id: string;
  items: CareMessage[];
  older_cursor: string | null;
  sync_cursor: string;
  has_more: boolean;
};
export type PendingMessage = {
  client_message_id: string;
  conversation_id: string;
  body: string;
  status: "sending" | "failed";
  error?: string;
};
export type ChatState = {
  conversations: CareConversation[];
  nextConversationCursor: string | null;
  selectedId: string;
  messages: CareMessage[];
  pending: PendingMessage[];
  olderCursor: string | null;
  hasOlder: boolean;
  ready: boolean;
  loadingList: boolean;
  loadingOlder: boolean;
  syncing: boolean;
  notice: string;
};
export const emptyChatState = (): ChatState => ({
  conversations: [], nextConversationCursor: null, selectedId: "", messages: [], pending: [],
  olderCursor: null, hasOlder: false, ready: false, loadingList: false,
  loadingOlder: false, syncing: false, notice: ""
});

export function mergeMessages(current: CareMessage[], incoming: CareMessage[]): CareMessage[] {
  const messages = new Map(current.map(message => [message.id, message]));
  incoming.forEach(message => messages.set(message.id, message));
  return [...messages.values()].sort((a, b) => a.seq - b.seq || a.id.localeCompare(b.id));
}

function mergeConversations(current: CareConversation[], incoming: CareConversation[]): CareConversation[] {
  const conversations = new Map(current.map(conversation => [conversation.id, conversation]));
  incoming.forEach(conversation => {
    const previous = conversations.get(conversation.id);
    // A delayed list response must not undo the ordering learned from a newer message.
    if (!previous || previous.last_seq <= conversation.last_seq) conversations.set(conversation.id, conversation);
  });
  return [...conversations.values()].sort((a, b) =>
    (b.last_message_at || b.created_at || "").localeCompare(a.last_message_at || a.created_at || "") || b.id.localeCompare(a.id));
}

class ChatRequestError extends Error {
  constructor(message: string, readonly retryAt = 0) { super(message); }
}

export function retryAfterDelay(value: string | null, now: number): number {
  if (!value) return 1000;
  const seconds = Number(value);
  return Number.isFinite(seconds) ? Math.max(0, seconds * 1000) : Math.max(0, Date.parse(value) - now) || 1000;
}

type Dependencies = {
  accountId: string;
  fetch: (path: string, init?: RequestInit) => Promise<Response>;
  changed: (state: ChatState) => void;
  uuid?: () => string;
  now?: () => number;
  schedule?: (callback: () => void, delay: number) => ReturnType<typeof setTimeout>;
  cancel?: (timer: ReturnType<typeof setTimeout>) => void;
};

/** One account's in-memory chat state. No message text is persisted in browser storage. */
export class ChatSession {
  state = emptyChatState();
  private disposed = false;
  private visible = true;
  private generation = 0;
  private syncCursor: string | null = null;
  private syncAgain = false;
  private failures = 0;
  private retryAt = 0;
  private timer?: ReturnType<typeof setTimeout>;
  private syncController?: AbortController;
  private controllers = new Set<AbortController>();
  private roomControllers = new Set<AbortController>();
  private outbox = new Map<string, PendingMessage>();
  private readonly now: () => number;
  private readonly schedule: NonNullable<Dependencies["schedule"]>;
  private readonly cancel: NonNullable<Dependencies["cancel"]>;

  constructor(private readonly dependencies: Dependencies) {
    this.now = dependencies.now ?? Date.now;
    this.schedule = dependencies.schedule ?? setTimeout;
    this.cancel = dependencies.cancel ?? clearTimeout;
  }

  private publish(update: Partial<ChatState> = {}) {
    if (this.disposed) return;
    this.state = { ...this.state, ...update };
    this.state.pending = [...this.outbox.values()].filter(message => message.conversation_id === this.state.selectedId);
    this.dependencies.changed(this.state);
  }

  private controller(room = true) {
    const controller = new AbortController();
    this.controllers.add(controller);
    if (room) this.roomControllers.add(controller);
    return controller;
  }

  private release(controller: AbortController) {
    this.controllers.delete(controller);
    this.roomControllers.delete(controller);
  }

  private current(generation: number) { return !this.disposed && this.generation === generation; }

  private async request<T>(path: string, controller: AbortController, init?: RequestInit): Promise<T> {
    if (this.now() < this.retryAt) throw new ChatRequestError("请求较频繁，请稍后重试。", this.retryAt);
    const response = await this.dependencies.fetch(path, {
      ...init, signal: controller.signal, headers: { "Content-Type": "application/json" }
    });
    if (!response.ok) {
      let message = `请求失败（${response.status}），请稍后重试。`;
      try {
        const payload = await response.json();
        if (typeof payload.detail === "string") message = payload.detail;
      } catch { /* Proxies may return a non-JSON error. */ }
      if (response.status === 429 || response.status === 503) {
        this.retryAt = this.now() + retryAfterDelay(response.headers.get("Retry-After"), this.now());
      }
      throw new ChatRequestError(message, this.retryAt);
    }
    return response.json() as Promise<T>;
  }

  async loadConversations(more = false) {
    if (this.disposed || this.state.loadingList || (more && !this.state.nextConversationCursor)) return;
    const controller = this.controller(false);
    const cursor = more ? this.state.nextConversationCursor : null;
    this.publish({ loadingList: true, notice: "" });
    try {
      const page = await this.request<ConversationPage>(`/api/v2/conversations?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`, controller);
      if (this.disposed || controller.signal.aborted) return;
      this.publish({
        conversations: mergeConversations(this.state.conversations, page.items),
        nextConversationCursor: page.has_more ? page.next_cursor : null
      });
      if (!this.state.selectedId && page.items[0]) this.select(page.items[0].id);
    } catch (error) {
      if (!controller.signal.aborted) this.publish({ notice: error instanceof Error ? error.message : "加载会话失败。" });
    } finally {
      this.release(controller);
      this.publish({ loadingList: false });
    }
  }

  select(conversationId: string) {
    if (this.disposed || this.state.selectedId === conversationId) return;
    this.generation++;
    this.clearTimer();
    this.roomControllers.forEach(controller => controller.abort());
    this.roomControllers.clear();
    this.syncController = undefined;
    this.syncCursor = null;
    this.syncAgain = false;
    this.failures = 0;
    this.publish({ selectedId: conversationId, messages: [], olderCursor: null, hasOlder: false,
      ready: false, loadingOlder: false, syncing: false, notice: "" });
    void this.sync();
  }

  private clearTimer() {
    if (this.timer !== undefined) this.cancel(this.timer);
    this.timer = undefined;
  }

  private poll(delay: number) {
    this.clearTimer();
    if (this.disposed || !this.visible || !this.state.selectedId) return;
    this.timer = this.schedule(() => { this.timer = undefined; void this.sync(); }, Math.max(delay, this.retryAt - this.now()));
  }

  setVisible(visible: boolean) {
    this.visible = visible;
    if (!visible) {
      this.clearTimer();
      this.syncController?.abort();
    } else {
      void this.sync();
    }
  }

  private acceptMessages(messages: CareMessage[]) {
    const merged = mergeMessages(this.state.messages, messages);
    for (const message of messages) {
      if (message.client_message_id && message.sender_id === this.dependencies.accountId) this.outbox.delete(message.client_message_id);
    }
    const latest = merged.at(-1);
    const conversations = latest ? this.state.conversations.map(conversation =>
      conversation.id === latest.conversation_id && latest.seq > conversation.last_seq
        ? { ...conversation, last_seq: latest.seq, last_message_at: latest.created_at }
        : conversation) : this.state.conversations;
    this.publish({ messages: merged, conversations: mergeConversations([], conversations) });
  }

  async sync() {
    if (this.disposed || !this.visible || !this.state.selectedId) return;
    if (this.state.syncing) { this.syncAgain = true; return; }
    this.clearTimer();
    const generation = this.generation;
    const conversationId = this.state.selectedId;
    const controller = this.controller();
    this.syncController = controller;
    this.syncAgain = false;
    this.publish({ syncing: true });
    let more = false;
    try {
      const initial = this.syncCursor === null;
      const page = await this.request<MessagePage>(`/api/v2/conversations/${encodeURIComponent(conversationId)}/messages?limit=50${this.syncCursor ? `&after=${encodeURIComponent(this.syncCursor)}` : ""}`, controller);
      if (!this.current(generation) || controller.signal.aborted) return;
      this.acceptMessages(page.items);
      // Only a complete GET page may advance this cursor. A send ACK can arrive out of order.
      this.syncCursor = page.sync_cursor;
      more = !initial && page.has_more;
      this.failures = 0;
      this.publish({ ready: true, notice: "", ...(initial ? { olderCursor: page.older_cursor, hasOlder: page.has_more } : {}) });
    } catch (error) {
      if (this.current(generation) && !controller.signal.aborted) {
        this.failures++;
        this.publish({ notice: error instanceof Error ? error.message : "同步消息失败，正在重试。" });
      }
    } finally {
      this.release(controller);
      if (this.current(generation)) {
        this.syncController = undefined;
        this.publish({ syncing: false });
        this.poll(this.failures ? Math.min(30_000, 1000 * 2 ** Math.min(this.failures, 5)) : more || this.syncAgain ? 0 : 3000);
      }
    }
  }

  async loadOlder() {
    if (this.disposed || this.state.loadingOlder || !this.state.hasOlder || !this.state.olderCursor) return;
    const generation = this.generation;
    const controller = this.controller();
    this.publish({ loadingOlder: true });
    try {
      const page = await this.request<MessagePage>(`/api/v2/conversations/${encodeURIComponent(this.state.selectedId)}/messages?limit=50&before=${encodeURIComponent(this.state.olderCursor)}`, controller);
      if (!this.current(generation) || controller.signal.aborted) return;
      this.acceptMessages(page.items);
      this.publish({ olderCursor: page.older_cursor, hasOlder: page.has_more });
    } catch (error) {
      if (this.current(generation) && !controller.signal.aborted) this.publish({ notice: error instanceof Error ? error.message : "加载历史消息失败。" });
    } finally {
      this.release(controller);
      if (this.current(generation)) this.publish({ loadingOlder: false });
    }
  }

  send(body: string): boolean {
    body = body.trim();
    if (this.disposed || !this.state.ready || !body || body.length > 4000 || this.state.pending.some(message => message.status === "sending")) return false;
    const message: PendingMessage = {
      client_message_id: (this.dependencies.uuid ?? (() => crypto.randomUUID()))(),
      conversation_id: this.state.selectedId, body, status: "sending"
    };
    this.outbox.set(message.client_message_id, message);
    this.publish();
    void this.post(message);
    return true;
  }

  retry(clientMessageId: string) {
    const message = this.outbox.get(clientMessageId);
    if (this.disposed || !message || message.status !== "failed" || message.conversation_id !== this.state.selectedId) return;
    this.outbox.set(clientMessageId, { ...message, status: "sending", error: undefined });
    this.publish();
    void this.post(message);
  }

  private async post(message: PendingMessage) {
    const generation = this.generation;
    const controller = this.controller();
    try {
      const result = await this.request<CareMessage>(`/api/v2/conversations/${encodeURIComponent(message.conversation_id)}/messages`, controller, {
        method: "POST", body: JSON.stringify({ client_message_id: message.client_message_id, body: message.body })
      });
      if (this.disposed) return;
      this.outbox.delete(message.client_message_id);
      if (this.current(generation) && !controller.signal.aborted) {
        this.acceptMessages([result]);
        // Fetch from the previous GET cursor, including any peer messages before this ACK.
        void this.sync();
      } else this.publish();
    } catch (error) {
      if (this.disposed) return;
      // A GET may already have confirmed this message while its POST response was lost.
      if (this.outbox.has(message.client_message_id)) {
        this.outbox.set(message.client_message_id, { ...message, status: "failed",
          error: controller.signal.aborted ? "发送结果未确认，可重试确认。" : error instanceof Error ? error.message : "发送失败。" });
        this.publish();
      }
    } finally {
      this.release(controller);
    }
  }

  dispose() {
    this.disposed = true;
    this.clearTimer();
    this.controllers.forEach(controller => controller.abort());
    this.controllers.clear();
    this.roomControllers.clear();
    this.outbox.clear();
    this.state = emptyChatState();
  }
}
