import { useRef, useState } from "react";
import { useEffect } from "react";
import { FileText, Plus, X, History, UserRound, Activity, BookOpenCheck, CheckCircle2, ChevronDown, Database, Loader2, MessageSquareText, Search, Send, Sparkles, Stethoscope, UploadCloud } from "lucide-react";
import type { ChatResponse, CitationSource, AiSessionHistory, AiConversationMessage, StreamProcessEvent, AiFlowItem, AccountRead, AiAttachment } from "../../types";
import { apiFetch } from "../../lib/api";
import { apiErrorMessage } from "../../lib/api-error";
import { consumeConsultationStream } from "../../lib/consultation-stream";
import { statusLabel } from "../../lib/presentation";

export default function Consultation({ account }: { account: AccountRead }) {
  const [message, setMessage] = useState("");
  const [attachments, setAttachments] = useState<AiAttachment[]>([]);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [sessions, setSessions] = useState<AiSessionHistory[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<AiConversationMessage[]>([]);
  const [processEvents, setProcessEvents] = useState<StreamProcessEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const requestVersion = useRef(0);
  const streamController = useRef<AbortController | null>(null);
  const messageList = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const list = messageList.current;
    if (list && list.scrollHeight - list.scrollTop - list.clientHeight < 240) list.scrollTop = list.scrollHeight;
  }, [chatMessages]);

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const result = await apiFetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!result.ok) {
      throw new Error(await apiErrorMessage(result));
    }
    return result.json() as Promise<T>;
  }

  async function loadSessionMessages(sessionId: string, version = ++requestVersion.current) {
    setHistoryLoading(true);
    setError("");
    try {
      const rows = await requestJson<AiConversationMessage[]>(`/api/v1/ai/sessions/${sessionId}/messages?user_id=${encodeURIComponent(account.id)}&limit=300`);
      if (version !== requestVersion.current) return;
      setSelectedSessionId(sessionId);
      setChatMessages(rows);
      const lastAiMessage = [...rows].reverse().find(item => item.sender === "ai");
      setResponse(lastAiMessage ? responseFromStoredMessage(lastAiMessage) : null);
      setProcessEvents([]);
      setHistoryOpen(false);
    } catch (loadError) {
      if (version === requestVersion.current) setError(loadError instanceof Error ? loadError.message : "加载问诊消息失败。");
    } finally {
      if (version === requestVersion.current) setHistoryLoading(false);
    }
  }

  async function loadSessions(nextSelectedId?: string | null) {
    const version = ++requestVersion.current;
    setHistoryLoading(true);
    try {
      const rows = await requestJson<AiSessionHistory[]>(`/api/v1/ai/sessions?user_id=${encodeURIComponent(account.id)}&limit=80`);
      if (version !== requestVersion.current) return;
      setSessions(rows);
      const targetId = nextSelectedId ?? selectedSessionId ?? rows[0]?.id ?? null;
      if (targetId) await loadSessionMessages(targetId, version);
      else { setSelectedSessionId(null); setChatMessages([]); }
    } catch (loadError) {
      if (version === requestVersion.current) setError(loadError instanceof Error ? loadError.message : "加载历史问诊失败。");
    } finally {
      if (version === requestVersion.current) setHistoryLoading(false);
    }
  }

  function startNewSession() {
    if (loading) return;
    requestVersion.current += 1;
    setHistoryLoading(false);
    setHistoryOpen(false);
    setSelectedSessionId(null);
    setChatMessages([]);
    setResponse(null);
    setProcessEvents([]);
    setError("");
    setMessage("");
    setAttachments([]);
  }

  useEffect(() => {
    void loadSessions();
    return () => { requestVersion.current += 1; streamController.current?.abort(); };
  }, [account.id]);

  async function submitConsultation() {
    const outgoingText = message.trim();
    if (!outgoingText || loading || historyLoading || streamController.current) {
      return;
    }
    setLoading(true);
    const controller = new AbortController();
    streamController.current = controller;
    setError("");
    setProcessEvents([]);
    const pendingUserId = `pending-user-${Date.now()}`;
    const pendingAiId = `pending-ai-${Date.now()}`;
    setChatMessages((current) => [
      ...current,
      {
        id: pendingUserId,
        session_id: selectedSessionId,
        sender: "user",
        content: outgoingText,
        created_at: new Date().toISOString()
      },
      {
        id: pendingAiId,
        session_id: selectedSessionId,
        sender: "ai",
        content: "",
        intent_category: "medical_consult",
        intent_subcategory: "streaming",
        cache_hit_level: "streaming",
        created_at: new Date().toISOString()
      }
    ]);
    setResponse({
      answer: "",
      intent: { category: "medical_consult", subcategory: "streaming", confidence: 0 },
      cache_hit_level: "streaming",
      citations: [],
      tool_calls: [],
      steps: [],
      intermediate_conclusions: []
    });
    try {
      const result = await apiFetch("/api/v1/ai/chat/stream", {
        method: "POST",
        signal: controller.signal,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: outgoingText,
          attachments,
          user_id: account.id,
          conversation_id: selectedSessionId
        })
      });
      if (!result.ok) {
        throw new Error(await apiErrorMessage(result));
      }
      if (!result.body) {
        throw new Error("浏览器不支持流式响应。");
      }
      await consumeConsultationStream(result.body, frame => handleStreamChunk(frame, pendingAiId));
      setMessage("");
      setAttachments([]);
    } catch (streamError) {
      if (!controller.signal.aborted) {
        const detail = streamError instanceof Error ? streamError.message : "问诊暂时不可用";
        setError(`${detail} 草稿已保留；本次未完成的回复已移除。`);
        setChatMessages(current => current.filter(item => item.id !== pendingAiId && item.id !== pendingUserId));
        setResponse(null);
        setProcessEvents([]);
      }
    } finally {
      streamController.current = null;
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  function handleStreamChunk(rawEvent: string, pendingAiId: string) {
    const payload = parseSsePayload(rawEvent);
    if (!payload) {
      return;
    }
    const type = String(payload.type || "");
    if (type === "token") {
      const content = String(payload.content || "");
      setResponse((current) => ({
        ...(current || {
          intent: { category: "medical_consult", subcategory: "streaming", confidence: 0 },
          cache_hit_level: "streaming",
          citations: []
        }),
        answer: `${current?.answer || ""}${content}`
      }));
      setChatMessages((current) => current.map((item) => item.id === pendingAiId ? { ...item, content: `${item.content || ""}${content}` } : item));
    } else if (type === "status") {
      const detail = String(payload.detail || "");
      appendProcessEvent({
        type: "status",
        label: String(payload.label || "正在处理"),
        detail,
        status: detail.includes("处理中") ? "running" : "completed"
      });
    } else if (type === "tool") {
      const toolCall = asRecord(payload.tool_call);
      const toolName = String(toolCall.tool_name || "tool");
      appendProcessEvent({
        type: "tool",
        label: toolLabel(toolName),
        detail: summarizeToolCall(toolCall),
        status: String(toolCall.status || "completed")
      });
      setResponse((current) => ({
        ...(current || emptyStreamingResponse()),
        tool_calls: [...(current?.tool_calls || []), toolCall]
      }));
    } else if (type === "sources") {
      const sources = Array.isArray(payload.sources) ? payload.sources as ChatResponse["citations"] : [];
      const documentCount = countCitationDocuments(sources);
      appendProcessEvent({
        type: "sources",
        label: "已找到参考来源",
        detail: documentCount ? `检索到 ${documentCount} 个知识库文档` : "未检索到明确来源",
        status: "completed"
      });
      setResponse((current) => ({
        ...(current || emptyStreamingResponse()),
        citations: sources
      }));
    } else if (type === "final") {
      const finalResponse = payload.response as ChatResponse | undefined;
      if (finalResponse) {
        setResponse(finalResponse);
        const finalSessionId = finalResponse.session_id || selectedSessionId;
        if (finalSessionId) {
          setSelectedSessionId(finalSessionId);
        }
        setChatMessages((current) => current.map((item) => item.id === pendingAiId ? {
          ...item,
          session_id: finalSessionId,
          content: finalResponse.answer,
          intent_category: finalResponse.intent.category,
          intent_subcategory: finalResponse.intent.subcategory,
          intent_confidence: finalResponse.intent.confidence,
          cache_hit_level: finalResponse.cache_hit_level,
          metadata_json: {
            citations: finalResponse.citations,
            task_type: finalResponse.task_type,
            run_id: finalResponse.run_id,
            trace_id: finalResponse.trace_id,
            tool_calls: finalResponse.tool_calls,
            steps: finalResponse.steps,
            intermediate_conclusions: finalResponse.intermediate_conclusions
          }
        } : item.session_id ? item : { ...item, session_id: finalSessionId }));
        void loadSessions(finalSessionId || null);
        return true;
      }
    } else if (type === "error") {
      const message = String(payload.message || "流式问诊失败。");
      setError(message);
      throw new Error(message);
    }
  }

  function appendProcessEvent(event: Omit<StreamProcessEvent, "id">) {
    setProcessEvents((current) => [
      ...current,
      {
        ...event,
        id: typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${event.type}-${Date.now()}-${Math.random()}`
      }
    ].filter((item, index, items) => {
      if (index === 0) {
        return true;
      }
      const previous = items[index - 1];
      return item.type !== previous.type || item.label !== previous.label || item.detail !== previous.detail;
    }).slice(-12));
  }

  const selectedSession = sessions.find((item) => item.id === selectedSessionId);

  async function handleConsultationFiles(files: FileList | null) {
    if (!files?.length) {
      return;
    }
    const selected = await Promise.all(
      Array.from(files).slice(0, 4).map(async (file) => {
        const isReadableText =
          file.type.startsWith("text/") ||
          file.name.endsWith(".txt") ||
          file.name.endsWith(".md") ||
          file.name.endsWith(".csv") ||
          file.name.endsWith(".json");
        let content = "";
        if (isReadableText) {
          content = (await file.text()).slice(0, 12000);
        }
        return {
          file_name: file.name,
          file_type: file.type || "application/octet-stream",
          content
        };
      })
    );
    setAttachments(selected);
    setError(selected.some((item) => !item.content) ? "部分文件无法读取内容，请改用文本文件，或将报告摘要填写到问诊内容中。" : "");
  }

  return (
    <section className="care-consult-layout" aria-label="智能问诊工作区">
      <aside className={`care-card care-history ${historyOpen ? "is-open" : ""}`}>
        <button className="care-button care-full" disabled={loading} onClick={startNewSession} type="button"><Plus size={18} />新建问诊</button>
        <div className="care-history-heading"><h2>历史问诊</h2><button className="care-icon-button care-history-toggle" aria-label="展开或收起问诊历史" aria-expanded={historyOpen} aria-controls="care-history-list" onClick={() => setHistoryOpen(!historyOpen)} type="button"><History size={19} /></button></div>
        <div id="care-history-list" className="care-history-list">
          {historyLoading && <p className="care-muted" role="status">正在加载历史问诊…</p>}
          {sessions.map(session => <button className={`care-history-item ${selectedSessionId === session.id ? "is-active" : ""}`} disabled={loading || historyLoading} key={session.id} onClick={() => void loadSessionMessages(session.id)} type="button" aria-current={selectedSessionId === session.id ? "true" : undefined}><span><MessageSquareText size={16} /><strong>{session.title || "未命名问诊"}</strong></span><p>{session.summary || "点击查看对话"}</p><small>{formatDateTime(session.updated_at || session.created_at)}</small></button>)}
          {!historyLoading && !sessions.length && <div className="care-empty"><MessageSquareText size={27} /><p>暂无历史问诊</p><small>每次咨询都会记录在这里</small></div>}
        </div><p className="care-history-note"><Stethoscope size={18} />让每次照护，都有迹可循。</p>
      </aside>
      <article className="care-card care-chat">
        <header className="care-chat-heading"><span className="care-square-icon"><Stethoscope size={24} /></span><div><h2>{selectedSession?.title || "新的智能问诊"}</h2><p>护理知识与健康咨询助手</p></div><span className="care-badge">AI 辅助</span></header>
        <div className="care-chat-scroll" ref={messageList}>
          <div className="care-chat-messages" role="log" aria-label="问诊对话" aria-busy={loading}>
            {chatMessages.map(item => <div className={`care-chat-message ${item.sender === "user" ? "is-user" : "is-assistant"}`} key={item.id}><span className="care-message-avatar">{item.sender === "user" ? <UserRound size={20} /> : <Stethoscope size={21} />}</span><div className="care-message-content"><small>{item.sender === "user" ? "我" : "AI 问诊助手"} · {formatDateTime(item.created_at)}</small><div className="care-message-bubble">{item.sender === "ai" ? <FormattedAnswer text={item.content} loading={loading && !item.content} /> : <p>{item.content}</p>}</div></div></div>)}
            {!chatMessages.length && !historyLoading && <div className="care-consult-welcome"><span className="care-welcome-mark"><Stethoscope size={37} strokeWidth={1.4} /></span><h2>有什么护理问题想了解？</h2><p>描述你的观察与疑问，也可以添加护理记录。<br />从更清晰的信息开始，一起整理照护思路。</p><div className="care-suggestions">{["如何整理日常护理观察记录？","居家照护沟通前需要准备哪些信息？"].map(text => <button className="care-button is-outline" key={text} onClick={() => setMessage(text)} type="button">{text}</button>)}</div></div>}
          </div>
          {response && <div className="care-chat-evidence"><ReferenceSources response={response} /><details className="collapsiblePanel streamProcess aiInsightPanel"><summary className="processHeader"><span><Sparkles size={17} /><strong>{loading ? "正在整理回复" : "查看处理过程"}</strong></span><ChevronDown size={17} /></summary><AiCallFlow response={response} processEvents={processEvents} loading={loading} /></details></div>}
        </div>
        <form className="care-composer" onSubmit={event => {event.preventDefault(); void submitConsultation();}}>
          {error && <p className="care-notice is-error" role="alert">{error}</p>}
          <label className="ov-sr-only" htmlFor="consultationInput">问诊内容</label><textarea id="consultationInput" disabled={loading || historyLoading} rows={3} placeholder="描述症状、护理观察或检查摘要…" value={message} onChange={event => setMessage(event.target.value)} />
          {attachments.length > 0 && <div className="care-attachments">{attachments.map((attachment,index) => <span key={`${attachment.file_name}-${index}`}><FileText size={15} /><span>{attachment.file_name}<small>{attachment.content ? `${attachment.content.length} 字` : "未读取内容"}</small></span><button className="care-icon-button" aria-label={`移除附件 ${attachment.file_name}`} disabled={loading} type="button" onClick={() => setAttachments(current => current.filter((_,i) => i !== index))}><X size={14} /></button></span>)}</div>}
          <div className="care-composer-actions"><div className="care-actions"><label className={`care-attach-button ${loading ? "is-disabled" : ""}`} htmlFor="consultationFiles"><UploadCloud size={18} />添加附件<input id="consultationFiles" disabled={loading} type="file" multiple accept=".txt,.md,.csv,.json,text/*" onChange={event => {void handleConsultationFiles(event.target.files);event.target.value = "";}} /></label><button className="care-text-button" disabled={loading} onClick={() => setMessage("如何整理日常护理观察记录，方便与护理人员沟通？")} type="button">护理示例</button></div><button className="care-button" disabled={loading || historyLoading || !message.trim()} type="submit">{loading ? <Loader2 className="spin" size={17} /> : <Send size={17} />}{loading ? "回复中…" : "发送"}</button></div>
          <p className="care-consult-disclaimer">AI 内容仅供参考，不能替代医生诊断。附件支持文本内容，最多 4 个，每个读取前 12,000 字。</p>
        </form>
      </article>
    </section>
  );

  function responseFromStoredMessage(messageItem: AiConversationMessage): ChatResponse {
    const metadata = asRecord(messageItem.metadata_json);
    const citations = Array.isArray(metadata.citations) ? metadata.citations as ChatResponse["citations"] : [];
    return {
      answer: messageItem.content,
      intent: {
        category: messageItem.intent_category || "medical_consult",
        subcategory: messageItem.intent_subcategory || "",
        confidence: messageItem.intent_confidence || 0
      },
      cache_hit_level: messageItem.cache_hit_level || "stored",
      citations,
      task_type: String(metadata.task_type || "knowledge_qa"),
      run_id: typeof metadata.run_id === "string" ? metadata.run_id : null,
      trace_id: typeof metadata.trace_id === "string" ? metadata.trace_id : null,
      session_id: messageItem.session_id || selectedSessionId,
      tool_calls: Array.isArray(metadata.tool_calls) ? metadata.tool_calls as Array<Record<string, unknown>> : [],
      steps: Array.isArray(metadata.steps) ? metadata.steps as Array<Record<string, unknown>> : [],
      intermediate_conclusions: Array.isArray(metadata.intermediate_conclusions)
        ? metadata.intermediate_conclusions as Array<Record<string, unknown>>
        : []
    };
  }
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "暂无时间";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function emptyStreamingResponse(): ChatResponse {
  return {
    answer: "",
    intent: { category: "medical_consult", subcategory: "streaming", confidence: 0 },
    cache_hit_level: "streaming",
    citations: [],
    tool_calls: [],
    steps: [],
    intermediate_conclusions: []
  };
}

function parseSsePayload(rawEvent: string): Record<string, unknown> | null {
  const data = rawEvent
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""))
    .join("\n")
    .trim();
  if (!data) {
    return null;
  }
  try {
    const parsed = JSON.parse(data);
    return asRecord(parsed);
  } catch {
    return null;
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function ReferenceSources({ response }: { response: ChatResponse }) {
  const sources = collectCitationSources(response);

  return (
    <section className="referenceSourcesPanel" aria-label="参考知识库来源">
      <div className="referenceHeader">
        <span>
          <BookOpenCheck size={18} />
          <strong>参考知识库来源</strong>
        </span>
        <small>{sources.length ? `检索到 ${sources.length} 个文档` : "暂无明确来源"}</small>
      </div>
      {sources.length ? (
        <div className="citationList referenceCitationList">
          {sources.map((source, index) => (
            <div key={`${sourceTitle(source)}-${source.doc_id || ""}-${source.source || ""}-${index}`}>
              <strong>{sourceTitle(source)}</strong>
              <small>{sourceMeta(source)}</small>
              {source.source_url && <a href={source.source_url} rel="noreferrer" target="_blank">打开来源</a>}
            </div>
          ))}
        </div>
      ) : (
        <p className="mutedText referenceEmpty">本轮回复暂未返回明确的知识库文件来源。</p>
      )}
    </section>
  );
}

function collectCitationSources(response: ChatResponse): CitationSource[] {
  const candidates: CitationSource[] = [...(response.citations || [])];

  for (const step of response.steps || []) {
    const output = asRecord(step.output_data);
    candidates.push(...extractSourcesFromOutput(output));
  }

  for (const toolCall of response.tool_calls || []) {
    const output = asRecord(toolCall.output);
    candidates.push(...extractSourcesFromOutput(output));
  }

  return groupCitationDocuments(candidates.map(normalizeCitationSource)).slice(0, 12);
}

function groupCitationDocuments(sources: CitationSource[]): CitationSource[] {
  const grouped = new Map<string, CitationSource>();
  for (const source of sources) {
    const key = citationDocumentKey(source);
    const existing = grouped.get(key);
    if (existing) {
      existing.hit_count = (existing.hit_count || 1) + 1;
      if (!existing.source_url && source.source_url) {
        existing.source_url = source.source_url;
      }
      if (!existing.doc_id && source.doc_id) {
        existing.doc_id = source.doc_id;
      }
      continue;
    }
    grouped.set(key, {
      title: sourceTitle(source),
      doc: source.doc,
      source: source.source,
      source_url: source.source_url,
      doc_id: source.doc_id,
      hit_count: source.hit_count || 1
    });
  }
  return Array.from(grouped.values());
}

function citationDocumentKey(source: CitationSource) {
  return String(source.doc_id || source.doc || source.source || source.source_url || sourceTitle(source)).trim().toLowerCase();
}

function countCitationDocuments(sources: CitationSource[]) {
  return groupCitationDocuments(sources.map(normalizeCitationSource)).length;
}

function extractSourcesFromOutput(output: Record<string, unknown>): CitationSource[] {
  const sources = Array.isArray(output.sources) ? output.sources.map(asRecord) : [];
  const chunks = Array.isArray(output.chunks) ? output.chunks.map(asRecord) : [];
  const chunkSources = chunks.map((chunk) => {
    const metadata = asRecord(chunk.metadata);
    return {
      title: String(metadata.title || metadata.file_name || metadata.filename || metadata.source || "知识库文档"),
      doc: String(metadata.file_name || metadata.filename || metadata.title || metadata.source || ""),
      source: String(metadata.source || metadata.file_name || metadata.filename || ""),
      doc_id: metadata.doc_id as string | number | undefined,
      page: metadata.page_label as string | number | undefined || metadata.page as string | number | undefined,
      chunk_index: metadata.chunk_index as string | number | undefined,
      snippet: String(chunk.content || chunk.page_content || chunk.text || "")
    };
  });
  return [...sources, ...chunkSources];
}

function normalizeCitationSource(value: CitationSource | Record<string, unknown>): CitationSource {
  const source = asRecord(value);
  return {
    title: stringOrUndefined(source.title) || stringOrUndefined(source.doc) || stringOrUndefined(source.source),
    doc: stringOrUndefined(source.doc),
    source: stringOrUndefined(source.source),
    source_url: stringOrUndefined(source.source_url) || stringOrUndefined(source.url),
    doc_id: source.doc_id as string | number | undefined,
    snippet: stringOrUndefined(source.snippet) || stringOrUndefined(source.content),
    content: stringOrUndefined(source.content),
    page: source.page as string | number | undefined,
    chunk_index: source.chunk_index as string | number | undefined
  };
}

function stringOrUndefined(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function sourceTitle(source: CitationSource) {
  return source.title || source.doc || source.source || (source.doc_id ? `知识库文档 ${source.doc_id}` : "知识库文档");
}

function sourceMeta(source: CitationSource) {
  const parts = [];
  if (source.doc_id) {
    parts.push(`文档ID：${source.doc_id}`);
  }
  if (source.source && source.source !== sourceTitle(source)) {
    parts.push(source.source);
  }
  return parts.join(" / ") || "知识库检索来源";
}

function AiCallFlow({
  response,
  processEvents,
  loading
}: {
  response: ChatResponse;
  processEvents: StreamProcessEvent[];
  loading: boolean;
}) {
  const items = buildAiFlowItems(response, processEvents, loading);
  return (
    <div className="aiFlowSurface">
      <div className="aiRunMeta">
        <span>任务链路：{taskTypeLabel(response.task_type || "knowledge_qa")}</span>
        <span>运行：{response.run_id || "本地流式会话"}</span>
      </div>
      <div className="processTimeline aiCallTimeline">
        {items.map((event) => (
          <div className={`processEvent ${event.type} ${event.status}`} key={event.id}>
            <span>{flowIcon(event)}</span>
            <div>
              <strong>{event.label}</strong>
              {event.detail && <small>{event.detail}</small>}
            </div>
            <em>{flowStatusLabel(event.status)}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildAiFlowItems(response: ChatResponse, processEvents: StreamProcessEvent[], loading: boolean): AiFlowItem[] {
  const liveItems = processEvents.map((event) => ({
    id: event.id,
    type: event.type,
    label: event.label,
    detail: event.detail,
    status: event.status || "completed"
  }));
  const derivedItems: AiFlowItem[] = [];

  (response.steps || []).forEach((step, index) => {
    const stepName = String(step.step_name || step.name || "unknown_step");
    const output = asRecord(step.output_data);
    derivedItems.push({
      id: `step-${index}-${stepName}`,
      type: stepName.includes("search") ? "tool" : "status",
      label: stepLabel(stepName),
      detail: summarizeStep(stepName, output),
      status: String(step.status || "completed")
    });
  });

  (response.tool_calls || []).forEach((toolCall, index) => {
    const toolName = String(toolCall.tool_name || "tool");
    derivedItems.push({
      id: `tool-${index}-${toolName}`,
      type: "tool",
      label: toolLabel(toolName),
      detail: summarizeToolCall(toolCall),
      status: String(toolCall.status || "completed")
    });
  });

  if (response.citations?.length) {
    const documentCount = countCitationDocuments(response.citations);
    derivedItems.push({
      id: "sources-final",
      type: "sources",
      label: "参考来源",
      detail: documentCount ? `${documentCount} 个知识库文档参与回答` : "未检索到明确来源",
      status: "completed"
    });
  }

  const items = liveItems.length ? [...liveItems, ...derivedItems] : derivedItems;
  const deduped = dedupeFlowItems(items);
  if (deduped.length) {
    return deduped;
  }
  return [{
    id: "waiting",
    type: "status",
    label: loading ? "等待 AI 服务响应" : "暂无可展示调用流程",
    detail: loading ? "正在连接问诊服务并准备接收流式事件" : "新的问诊开始后会显示实时调用步骤",
    status: loading ? "running" : "pending"
  }];
}

function dedupeFlowItems(items: AiFlowItem[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${item.type}:${item.label}:${item.detail}:${item.status}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  }).slice(-18);
}

function flowIcon(event: AiFlowItem) {
  if (event.status === "running") {
    return <Loader2 className="spin" size={15} />;
  }
  if (event.type === "tool") {
    return <Database size={15} />;
  }
  if (event.type === "sources") {
    return <Search size={15} />;
  }
  if (event.type === "error") {
    return <Activity size={15} />;
  }
  return <CheckCircle2 size={15} />;
}

function flowStatusLabel(status: string) {
  const labels: Record<string, string> = {
    running: "进行中",
    completed: "完成",
    success: "完成",
    failed: "失败",
    pending: "等待"
  };
  return labels[status] || statusLabel(status);
}

function stepLabel(stepName: string) {
  const labels: Record<string, string> = {
    memory_read: "读取历史对话",
    intent_recognition: "识别问诊意图",
    question_classification: "判断问题类型",
    question_rewrite: "改写检索问题",
    knowledge_search: "调用知识库检索",
    result_evaluation: "评估检索结果",
    answer_generation: "生成问诊回复",
    memory_write: "保存对话记忆",
    clarification: "判断是否需要追问"
  };
  return labels[stepName] || stepName.replaceAll("_", " ");
}

function taskTypeLabel(taskType: string) {
  const labels: Record<string, string> = {
    knowledge_qa: "知识库问答",
    reasoning: "医学推理",
    chitchat: "基础对话",
    admin_copilot: "管理助手",
    knowledge_inspection: "知识巡检"
  };
  return labels[taskType] || taskType;
}

function summarizeStep(stepName: string, output: Record<string, unknown>) {
  if (stepName === "memory_read") {
    return output.has_history ? "已读取当前问诊的上下文历史" : "当前会话暂无可用历史";
  }
  if (stepName === "question_rewrite") {
    return String(output.rewritten_question || "已完成检索问题整理");
  }
  if (stepName === "knowledge_search") {
    const documents = countCitationDocuments(extractSourcesFromOutput(output));
    return documents ? `检索到 ${documents} 个候选文档` : "未检索到候选文档";
  }
  if (stepName === "result_evaluation") {
    return output.is_sufficient === false ? "检索依据不足，后续回答会保守处理" : "检索依据通过评估";
  }
  if (stepName === "answer_generation") {
    return "已汇总上下文、知识库文档和问诊问题生成回复";
  }
  return "步骤已执行";
}

function FormattedAnswer({ text, loading }: { text: string; loading: boolean }) {
  const blocks = text.trim().replace(/(^|\n)(#{1,6} .+)(?=\n|$)/g, "$1\n\n$2\n\n").split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  if (!blocks.length) {
    return <p className="answerText mutedText">{loading ? "正在组织问诊回复..." : "暂无回答内容。"}</p>;
  }
  return (
    <div className="answerText">
      {blocks.map((block, index) => {
        const heading = block.match(/^#{1,6}\s+(.+)$/);
        if (heading) return <h3 key={`heading-${index}`}>{heading[1]}</h3>;
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        const isBulletList = lines.every((line) => /^[-*•]/.test(line));
        const isNumberedList = lines.every((line) => /^\d+[.、]/.test(line));
        if (isBulletList) {
          return (
            <ul key={`${block}-${index}`}>
              {lines.map((line, lineIndex) => <li key={`${line}-${lineIndex}`}>{line.replace(/^[-*•]\s*/, "")}</li>)}
            </ul>
          );
        }
        if (isNumberedList) {
          return (
            <ol key={`${block}-${index}`}>
              {lines.map((line, lineIndex) => <li key={`${line}-${lineIndex}`}>{line.replace(/^\d+[.、]\s*/, "")}</li>)}
            </ol>
          );
        }
        return <p key={`${block}-${index}`}>{block}</p>;
      })}
    </div>
  );
}

function toolLabel(toolName: string) {
  const labels: Record<string, string> = {
    question_rewrite: "问题改写",
    knowledge_search: "知识库检索",
    rerank: "证据重排",
    conversation_memory_read: "读取对话记忆",
    conversation_memory_write: "写入对话记忆",
    doc_summary: "文档摘要",
    ocr_extract: "OCR 识别",
    answer_generation: "生成回答"
  };
  return labels[toolName] || toolName.replaceAll("_", " ");
}

function summarizeToolCall(toolCall: Record<string, unknown>) {
  const status = String(toolCall.status || "completed");
  const duration = typeof toolCall.duration_ms === "number" ? `，耗时 ${Math.round(toolCall.duration_ms)}ms` : "";
  const output = asRecord(toolCall.output);
  const count = Array.isArray(output.results) ? `，返回 ${output.results.length} 条结果` : "";
  return `${statusLabel(status)}${count}${duration}`;
}
