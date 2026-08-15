import { privateDatabase } from "./api.js";

const root = document.querySelector("#share-app");
const COLLECTION = "fl_web_share_inbox";
const state = { incoming: null, items: [], loading: true, busy: false, error: "", authRequired: false };

const statusObserver = new MutationObserver(() => {
  document.querySelectorAll(".share-item").forEach((node, index) => {
    node.dataset.status = state.items[index]?.status || "";
  });
});
statusObserver.observe(root, { childList: true, subtree: true });

function esc(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function formatDate(value) {
  const date = new Date(Number(value) || value);
  return Number.isNaN(date.getTime()) ? String(value || "") : date.toLocaleString("zh-CN", { hour12: false });
}

function statusLabel(status) {
  return ({ pending: "待处理", copied: "已复制", processed: "已处理", rejected: "已拒绝", failed: "需要重试" })[status] || "待处理";
}

async function stableClientId(title, text) {
  const source = `${title}\n${text}`;
  if (globalThis.crypto?.subtle) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(source));
    return `pwa-${Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("").slice(0, 32)}`;
  }
  let hash = 2166136261;
  for (const char of source) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619);
  return `pwa-${(hash >>> 0).toString(16)}`;
}

async function collection() {
  const database = await privateDatabase();
  return database.collection(COLLECTION);
}

async function listItems() {
  const rows = await (await collection()).where({ _openid: "{openid}" }).orderBy("received_at", "desc").limit(50).get();
  return Array.isArray(rows.data) ? rows.data : [];
}

async function enqueue(title, text) {
  const cleanText = String(text || "").trim().slice(0, 4000);
  if (!cleanText) throw new Error("请先输入要发送的文字。");
  const cleanTitle = String(title || "").trim().slice(0, 120);
  const clientId = await stableClientId(cleanTitle, cleanText);
  const inbox = await collection();
  const existing = await inbox.where({ _openid: "{openid}", client_id: clientId }).limit(1).get();
  if (!existing.data?.length) {
    await inbox.add({ data: {
      client_id: clientId,
      title: cleanTitle,
      text: cleanText,
      source: "pwa_share",
      status: "pending",
      received_at: Date.now(),
      updated_at: Date.now(),
      expires_at: Date.now() + 30 * 24 * 60 * 60 * 1000
    }});
  }
  state.incoming = null;
  state.items = await listItems();
}

async function updateStatus(itemId, status) {
  const inbox = await collection();
  await inbox.where({ _id: itemId, _openid: "{openid}" }).update({ data: { status, updated_at: Date.now() } });
  state.items = await listItems();
}

async function copyItem(item) {
  await navigator.clipboard.writeText(item.text || "");
  await updateStatus(item._id, "copied");
}

function renderIncoming() {
  if (!state.incoming) return "";
  return `<section class="share-card"><div class="share-kicker">手机发来的一条文字</div><h2>发送到电脑</h2><p>确认后，文字会出现在电脑端的待处理列表。它不会直接写入正式记录。</p><textarea class="share-textarea" data-incoming-text>${esc(state.incoming.text)}</textarea><div class="share-actions"><button class="share-button primary" data-action="send-incoming">发送到电脑</button><button class="share-button" data-action="clear-incoming">取消</button></div></section>`;
}

function renderItems() {
  if (state.loading) return `<div class="share-empty">正在读取……</div>`;
  if (!state.items.length) return `<div class="share-empty">还没有待处理文字。</div>`;
  return state.items.map(item => `<article class="share-item"><div class="share-item-head"><strong>${esc(statusLabel(item.status))}</strong><span class="share-status">${esc(item.title || "文字收件")}</span></div><div class="share-item-text">${esc(item.text)}</div><div class="share-item-meta">${esc(formatDate(item.received_at))}</div><div class="share-actions"><button class="share-button" data-action="copy-item" data-item-id="${esc(item._id)}">复制文字</button><button class="share-button" data-action="process-item" data-item-id="${esc(item._id)}">标记已处理</button><button class="share-button" data-action="reject-item" data-item-id="${esc(item._id)}">拒绝</button></div></article>`).join("");
}

function render() {
  if (state.authRequired) {
    root.innerHTML = `<div class="share-shell"><section class="share-card share-auth"><div class="share-kicker">每日健身 / 文字收件箱</div><h1>需要登录</h1><p>请先在正式 PWA 中登录，再接收手机发来的文字。</p><a class="share-button" href="./#status">返回工作台</a></section></div>`;
    return;
  }
  root.innerHTML = `<div class="share-shell"><header class="share-head"><div><div class="share-kicker">每日健身 / 文字收件箱</div><h1>待处理文字</h1><p>手机发来的内容先放在这里。电脑端复制后，继续使用 Daily Entry 的预览与确认流程。</p></div><a class="share-back" href="./#status">返回工作台 ←</a></header>${state.error ? `<div class="share-notice error">${esc(state.error)}</div>` : ""}<div class="share-grid"><div>${renderIncoming()}<section class="share-card"><div class="share-kicker">手动输入</div><h2>补充一条文字</h2><p>如果手机系统没有显示分享入口，也可以把内容粘贴到这里。</p><textarea class="share-textarea" data-manual-text placeholder="例如：今天体重 70 kg，腰围 82.5 cm"></textarea><div class="share-actions"><button class="share-button primary" data-action="send-manual">发送到电脑</button></div></section></div><section class="share-card"><div class="share-kicker">电脑端处理</div><h2>最近收到</h2><div class="share-list">${renderItems()}</div></section></div></div>`;
}

async function load() {
  state.loading = true;
  render();
  try {
    state.items = await listItems();
    state.loading = false;
    render();
  } catch (error) {
    state.loading = false;
    state.authRequired = /AUTH_REQUIRED|WEB_AUTH_DISABLED|CLOUDBASE_ENV_MISSING/.test(String(error.message || error));
    state.error = state.authRequired ? "" : "正式待处理收件箱暂时不可用，请稍后重试。";
    render();
  }
}

async function send(title, text) {
  if (state.busy) return;
  state.busy = true;
  state.error = "";
  try { await enqueue(title, text); }
  catch (error) { state.error = error.message || "发送失败，正式记录未改变。"; }
  state.busy = false;
  render();
}

root.addEventListener("click", async event => {
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (!action || state.busy) return;
  if (action === "clear-incoming") { state.incoming = null; render(); return; }
  if (action === "send-incoming") { await send("手机分享", root.querySelector("[data-incoming-text]")?.value); return; }
  if (action === "send-manual") { await send("手动输入", root.querySelector("[data-manual-text]")?.value); return; }
  const item = state.items.find(row => row._id === event.target.closest("[data-item-id]")?.dataset.itemId);
  if (!item) return;
  try {
    if (action === "copy-item") await copyItem(item);
    if (action === "process-item") await updateStatus(item._id, "processed");
    if (action === "reject-item") await updateStatus(item._id, "rejected");
    state.error = "";
  } catch (error) { state.error = error.message || "操作失败，原文仍保留。"; }
  render();
});

const params = new URLSearchParams(location.search);
const sharedText = params.get("share_text") || params.get("text");
if (sharedText) {
  state.incoming = { title: params.get("share_title") || "手机分享", text: sharedText };
  history.replaceState({}, "", "./share.html");
}
load();
