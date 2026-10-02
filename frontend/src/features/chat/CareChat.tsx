import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Loader2, MessageSquareText, RefreshCw, Send } from "lucide-react";
import type { AccountRead } from "../../types";
import { apiFetch } from "../../lib/api";
import { ChatSession, emptyChatState } from "./chat-session";

const sourceLabels: Record<string, string> = { job: "招聘", application: "应聘", invitation: "邀请", profile: "资料", direct: "直接沟通" };

export default function CareChat({ account }: { account: AccountRead }) {
  const [state, setState] = useState(emptyChatState);
  const [body, setBody] = useState("");
  const session = useRef<ChatSession | null>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const followLatest = useRef(true);
  const scrollAnchor = useRef<{ height: number; top: number } | null>(null);

  useEffect(() => {
    const current = new ChatSession({ accountId: account.id, fetch: apiFetch, changed: setState });
    session.current = current;
    setState(emptyChatState());
    setBody("");
    const visibilityChanged = () => current.setVisible(document.visibilityState === "visible");
    visibilityChanged();
    document.addEventListener("visibilitychange", visibilityChanged);
    void current.loadConversations();
    return () => {
      document.removeEventListener("visibilitychange", visibilityChanged);
      current.dispose();
      session.current = null;
    };
  }, [account.id]);

  useLayoutEffect(() => {
    const element = viewport.current;
    if (!element) return;
    if (scrollAnchor.current && !state.loadingOlder) {
      element.scrollTop = scrollAnchor.current.top + element.scrollHeight - scrollAnchor.current.height;
      scrollAnchor.current = null;
    } else if (!scrollAnchor.current && followLatest.current) {
      element.scrollTop = element.scrollHeight;
    }
  }, [state.messages, state.pending, state.loadingOlder]);

  const sending = state.pending.some(message => message.status === "sending");
  function send() {
    if (session.current?.send(body)) {
      followLatest.current = true;
      setBody("");
    }
  }

  return (
    <section className="chatLayout">
      <article className="panel conversationPanel">
        <div className="panelHeader compact">
          <h2>我的会话</h2>
          <button className="iconButton" disabled={state.loadingList} onClick={() => void session.current?.loadConversations()} title="刷新会话" type="button">
            {state.loadingList ? <Loader2 className="spin" size={19} /> : <RefreshCw size={19} />}
          </button>
        </div>
        {state.notice && <p className="notice" role="status">{state.notice}</p>}
        <div className="miniList">
          {state.conversations.map(conversation => (
            <button
              className={`conversationTile ${state.selectedId === conversation.id ? "active" : ""}`}
              key={conversation.id} type="button"
              onClick={() => {
                if (state.selectedId === conversation.id) return;
                followLatest.current = true;
                scrollAnchor.current = null;
                setBody("");
                session.current?.select(conversation.id);
              }}
            >
              <strong>{conversation.title || "护理沟通"}</strong>
              <span>{sourceLabels[conversation.source_type] || "直接沟通"} / {conversation.last_message_at || conversation.created_at || "暂无时间"}</span>
            </button>
          ))}
          {state.nextConversationCursor && <button className="secondaryButton" disabled={state.loadingList} onClick={() => void session.current?.loadConversations(true)} type="button">加载更多会话</button>}
          {!state.loadingList && state.conversations.length === 0 && <p className="mutedText">暂无会话，可在招聘或应聘发布页面点击“沟通”创建。</p>}
        </div>
      </article>

      <article className="panel chatPanel">
        <div className="panelHeader compact">
          <h2>聊天窗口</h2>
          {state.syncing ? <Loader2 className="spin" size={20} aria-label="同步消息中" /> : <MessageSquareText size={20} />}
        </div>
        <div className="messageList" ref={viewport} aria-label="聊天消息" onScroll={() => {
          const element = viewport.current;
          if (element) followLatest.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80;
        }}>
          {state.hasOlder && <button className="secondaryButton" type="button" disabled={state.loadingOlder} onClick={() => {
            const element = viewport.current;
            if (element) scrollAnchor.current = { height: element.scrollHeight, top: element.scrollTop };
            void session.current?.loadOlder();
          }}>{state.loadingOlder ? "加载中…" : "加载更早消息"}</button>}
          {state.messages.map(message => (
            <div className={`messageBubble ${message.sender_id === account.id ? "mine" : ""}`} key={message.id}>
              <span>{message.sender_id === account.id ? "我" : "对方"}</span>
              <p>{message.body || message.content}</p>
              {message.sender_id === account.id && <small className="mutedText">已发送</small>}
            </div>
          ))}
          {state.pending.map(message => (
            <div className="messageBubble mine" key={message.client_message_id}>
              <span>我</span><p>{message.body}</p>
              {message.status === "sending" ? <small role="status">发送中…</small> : <div>
                <small role="status">{message.error || "发送失败。"}</small>
                <button className="secondaryButton" type="button" onClick={() => session.current?.retry(message.client_message_id)}>重试发送</button>
              </div>}
            </div>
          ))}
          {!state.messages.length && !state.pending.length && <p className="mutedText">{state.selectedId ? state.ready ? "暂无消息，可以开始沟通。" : "正在加载消息…" : "选择会话后开始沟通。"}</p>}
        </div>
        <div className="chatComposer">
          <textarea aria-label="沟通内容" maxLength={4000} placeholder="输入沟通内容" value={body} onChange={event => setBody(event.target.value)} />
          <button className="primaryButton" disabled={!state.ready || !body.trim() || sending} onClick={send} type="button">
            <Send size={18} /><span>{sending ? "发送中…" : "发送"}</span>
          </button>
        </div>
      </article>
    </section>
  );
}
