export async function apiErrorMessage(response: Response): Promise<string> {
  const fallback = response.status >= 500
    ? "服务暂时不可用，请稍后重试。"
    : `请求未完成（${response.status}），请检查填写的信息。`;
  try {
    const payload: unknown = await response.json();
    if (!payload || typeof payload !== "object" || !("detail" in payload)) return fallback;
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail.flatMap(item => item && typeof item.msg === "string" ? [item.msg] : []);
      if (messages.length) return messages.join("；");
    }
  } catch { /* HTML error pages and empty responses use a readable fallback. */ }
  return fallback;
}
