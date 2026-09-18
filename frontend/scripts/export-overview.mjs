import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build, createServer } from "vite";
import react from "@vitejs/plugin-react";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const result = await build({
  root, configFile: false, plugins: [react()], logLevel: "warn",
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    write: false, minify: "esbuild", cssCodeSplit: false,
    lib: { entry: resolve(root, "src/features/overview/preview.tsx"), name: "DoctorCareOverview", formats: ["iife"] },
  },
});
const output = (Array.isArray(result) ? result : [result]).flatMap((bundle) => bundle.output);
const script = output.filter((item) => item.type === "chunk").map((item) => item.code).join("\n");
const css = output.filter((item) => item.type === "asset" && item.fileName.endsWith(".css")).map((item) => item.source).join("\n");
if (!script || !css) throw new Error("Overview export is missing its script or stylesheet.");
const illustration = await readFile(resolve(root, "public/images/overview-care-illustration.png"));
const imageData = `data:image/png;base64,${illustration.toString("base64")}`;
const renderer = await createServer({ root, configFile: false, plugins: [react()], server: { middlewareMode: true }, logLevel: "error" });
let markup;
try {
  const { renderOverview } = await renderer.ssrLoadModule("/scripts/render-overview.tsx");
  markup = renderOverview(imageData);
  // The public preview never contains real account data or authentication state.
  const patientPage = renderOverview(imageData, false);
  if (patientPage.includes('data-view="verification"') || patientPage.includes('data-view="knowledge"')) {
    throw new Error("Non-admin overview must not expose admin navigation.");
  }
} finally {
  await renderer.close();
}
const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light" />
  <meta name="description" content="DoctorCarePlatform 流程总览界面设计预览。所有数据为示例，支持离线打开。" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'" />
  <title>流程总览 · DoctorCarePlatform</title>
  <style>html,body{margin:0;background:#f5f8f6}button{font:inherit}${css.replace(/<\/style/gi, "<\\/style")}</style>
</head>
<body>
  <div id="overview-root">${markup}</div>
  <noscript>当前为静态预览。启用 JavaScript 后可使用筛选和移动导航；本文件无需联网，所有数据均为示例。</noscript>
  <script>${script.replace(/<\/script/gi, "<\\/script")}</script>
</body>
</html>
`;
// Keep the standalone deliverable at the repository root, outside the web bundle.
const target = resolve(root, "..", "overview.html");
await writeFile(target, html, "utf8");
console.log(`Exported standalone overview: ${target} (${(Buffer.byteLength(html) / 1024 / 1024).toFixed(2)} MB)`);
