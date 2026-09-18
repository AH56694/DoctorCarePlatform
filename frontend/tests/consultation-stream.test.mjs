import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const source = readFileSync(new URL("../src/lib/consultation-stream.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { consumeConsultationStream } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const encoder = new TextEncoder();
function stream(parts) {
  return new ReadableStream({ start(controller) { for (const part of parts) controller.enqueue(part); controller.close(); } });
}
function parse(frame) { return JSON.parse(frame.replace(/^data:\s*/, "")); }

test("SSE preserves Chinese UTF-8 characters and CRLF frames across byte boundaries", async () => {
  const bytes = encoder.encode('data: {"type":"token","content":"护理记录"}\r\n\r\ndata: {"type":"final"}\r\n\r\n');
  const messages = [];
  await consumeConsultationStream(stream([...bytes].map(byte => Uint8Array.of(byte))), frame => {
    const payload = parse(frame); messages.push(payload); return payload.type === "final";
  });
  assert.deepEqual(messages, [{ type: "token", content: "护理记录" }, { type: "final" }]);
});

test("final frame without a trailing delimiter is accepted and releases the reader", async () => {
  const body = stream([encoder.encode('data: {"type":"final"}')]);
  await consumeConsultationStream(body, frame => parse(frame).type === "final");
  assert.equal(body.locked, false);
});

test("truncated response fails instead of being presented as a complete answer", async () => {
  const body = stream([encoder.encode('data: {"type":"token","content":"partial"}\n\n')]);
  await assert.rejects(consumeConsultationStream(body, () => false), /未收到完整结果/);
  assert.equal(body.locked, false);
});

test("server errors propagate and cancel the stream", async () => {
  const body = stream([encoder.encode('data: {"type":"error","message":"服务暂不可用"}\n\n')]);
  await assert.rejects(consumeConsultationStream(body, frame => { throw new Error(parse(frame).message); }), /服务暂不可用/);
  assert.equal(body.locked, false);
});
