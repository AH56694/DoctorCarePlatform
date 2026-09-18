/** Read complete SSE frames, including frames split across network chunks. */
export async function consumeConsultationStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (frame: string) => boolean | void
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  try {
    while (!completed) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || "";
      if (done && buffer.trim()) frames.push(buffer);
      for (const frame of frames) {
        if (onEvent(frame) === true) { completed = true; break; }
      }
      if (done) break;
    }
    if (!completed) throw new Error("回复连接已中断，未收到完整结果。请稍后重试。");
  } finally {
    try { await reader.cancel(); } catch { /* The connection may already be closed. */ }
    reader.releaseLock();
  }
}
