import { writeFile } from "node:fs/promises";

const [url, selector, output] = process.argv.slice(2);
if (!url || !selector || !output) {
  throw new Error("Usage: node capture_web_state.mjs <url> <click-selector> <output.png>");
}

const page = await fetch(`http://127.0.0.1:9225/json/new?${encodeURIComponent(url)}`, { method: "PUT" }).then((response) => response.json());
const socket = new WebSocket(page.webSocketDebuggerUrl);
const pending = new Map();
let sequence = 0;

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) reject(new Error(message.error.message));
  else resolve(message.result);
});

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

function send(method, params = {}) {
  const id = ++sequence;
  socket.send(JSON.stringify({ id, method, params }));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1600, height: 1000, deviceScaleFactor: 1, mobile: false });
await send("Runtime.evaluate", { expression: "new Promise(resolve => setTimeout(resolve, 2500))", awaitPromise: true });
const click = await send("Runtime.evaluate", {
  expression: `(() => { const target = document.querySelector(${JSON.stringify(selector)}); if (!target) return false; target.click(); return true; })()`,
  returnByValue: true,
});
if (!click.result.value) throw new Error(`Selector not found: ${selector}`);
await send("Runtime.evaluate", { expression: "new Promise(resolve => setTimeout(resolve, 1800))", awaitPromise: true });
const screenshot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
await writeFile(output, Buffer.from(screenshot.data, "base64"));
await send("Page.close");
socket.close();
