import { privateAccountIdentity, privateDatabase } from "./api.js?v=20260820-04";

const root = document.querySelector("#share-app");
const COLLECTION = "fl_web_share_inbox";
// 同一次发送的重试保护窗口：窗口内相同内容视为重试会更新原记录，窗口外每次发送都是新记录。
const RETRY_WINDOW_MS = 10 * 60 * 1000;
const state = { incoming: null, items: [], loading: true, busy: false, error: "", notice: "", authRequired: false, pendingSend: null };

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
  const { uid } = await privateAccountIdentity();
  const rows = await (await collection()).where({ owner_uid: uid }).orderBy("received_at", "desc").limit(50).get();
  return Array.isArray(rows.data) ? rows.data : [];
}

async function enqueue(title, text) {
  const cleanText = String(text || "").trim().slice(0, 4000);
  if (!cleanText) throw new Error("请先输入要发送的文字。");
  const cleanTitle = String(title || "").trim().slice(0, 120);
  const clientId = await stableClientId(cleanTitle, cleanText);
  const { uid } = await privateAccountIdentity();
  const inbox = await collection();
  const existing = await inbox.where({ owner_uid: uid, client_id: clientId }).orderBy("received_at", "desc").limit(1).get();
  const existingRow = existing.data?.[0];
  // 以次为单位：只有重试窗口内的相同内容才视为同一次发送（更新），否则新建一条记录。
  const isRetry = existingRow && (Date.now() - Number(existingRow.received_at || 0)) < RETRY_WINDOW_MS;
  if (isRetry) {
    await inbox.doc(existingRow._id).update({ data: {
      title: cleanTitle,
      text: cleanText,
      source: "pwa_share",
      status: "pending",
      updated_at: Date.now(),
      expires_at: Date.now() + 30 * 24 * 60 * 60 * 1000
    }});
  } else {
    await inbox.add({ data: {
      owner_uid: uid,
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
  const { uid } = await privateAccountIdentity();
  const inbox = await collection();
  await inbox.where({ _id: itemId, owner_uid: uid }).update({ data: { status, updated_at: Date.now() } });
  state.items = await listItems();
}

async function writeClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const field = document.createElement("textarea");
  field.value = text;
  field.setAttribute("readonly", "");
  field.style.position = "fixed";
  field.style.opacity = "0";
  document.body.appendChild(field);
  field.select();
  const copied = document.execCommand("copy");
  field.remove();
  if (!copied) throw new Error("当前环境无法访问剪贴板。");
}

async function copyItem(item) {
  await writeClipboard(item.text || "");
  state.notice = "已复制到剪贴板，可以回到 Daily Entry 粘贴。";
  await updateStatus(item._id, "copied");
}

function renderIncoming() {
  if (!state.incoming) return "";
  const outbound = state.incoming.mode === "outbound";
  return `<section class="share-card"><div class="share-kicker">${outbound ? "电脑发来的一条文字" : "手机发来的一条文字"}</div><h2>${outbound ? "发送到云端" : "发送到电脑"}</h2><p>${outbound ? "确认后，文字会进入你的私有云端收件箱；不会直接写入正式记录。" : "确认后，文字会出现在电脑端的待处理列表。它不会直接写入正式记录。"}</p><textarea class="share-textarea" data-incoming-text>${esc(state.incoming.text)}</textarea><div class="share-actions"><button class="share-button primary" data-action="send-incoming">${outbound ? "确认发送" : "发送到电脑"}</button><button class="share-button" data-action="clear-incoming">取消</button></div></section>`;
}

function renderItems() {
  if (state.loading) return `<div class="share-empty">正在读取……</div>`;
  if (!state.items.length) return `<div class="share-empty">还没有待处理文字。</div>`;
  return state.items.map(item => `<article class="share-item"><div class="share-item-head"><strong>${esc(statusLabel(item.status))}</strong><span class="share-status">${esc(item.title || "文字收件")}</span></div><div class="share-item-text">${esc(item.text)}</div><div class="share-item-meta">${esc(formatDate(item.received_at))}</div><div class="share-actions"><button class="share-button" data-action="copy-item" data-item-id="${esc(item._id)}">复制文字</button><button class="share-button" data-action="process-item" data-item-id="${esc(item._id)}">标记已处理</button><button class="share-button" data-action="reject-item" data-item-id="${esc(item._id)}">拒绝</button></div></article>`).join("");
}

function renderSendConfirmation() {
  const pending = state.pendingSend;
  if (!pending) return "";
  return `<section class="share-card share-send-confirm" role="dialog" aria-modal="true" aria-label="再次确认发送"><div class="share-kicker">再次确认</div><h2>发送到电脑？</h2><p>发送后，电脑端“当日训练记录”会在近 7 天列表中显示这条文字；它不会自动写入正式训练记录。</p><pre class="share-item-text">${esc(pending.text)}</pre><div class="share-actions"><button class="share-button primary" data-action="confirm-send">确认发送到电脑</button><button class="share-button" data-action="cancel-send">返回修改</button></div></section>`;
}

function render() {
  if (state.pendingSend) {
    root.innerHTML = `<div class="share-shell">${renderSendConfirmation()}</div>`;
    return;
  }
  if (state.authRequired) {
    root.innerHTML = `<div class="share-shell"><section class="share-card share-auth"><div class="share-kicker">每日健身 / 文字收件箱</div><h1>需要登录</h1><p>请先在正式 PWA 中登录，再接收手机发来的文字。</p><a class="share-button" href="./#status">返回工作台</a></section></div>`;
    return;
  }
  root.innerHTML = `<div class="share-shell"><header class="share-head"><div><div class="share-kicker">每日健身 / 文字收件箱</div><h1>待处理文字</h1><p>手机发来的内容先放在这里。电脑端复制后，继续使用 Daily Entry 的预览与确认流程。</p></div><a class="share-back" href="./#status">返回工作台 ←</a></header>${state.error ? `<div class="share-notice error">${esc(state.error)}</div>` : ""}${state.notice ? `<div class="share-notice success" role="status">${esc(state.notice)}</div>` : ""}<div class="share-grid"><div>${renderIncoming()}<section class="share-card"><div class="share-kicker">手动输入</div><h2>补充一条文字</h2><p>如果手机系统没有显示分享入口，也可以把内容粘贴到这里。</p><textarea class="share-textarea" data-manual-text placeholder="例如：今天体重 70 kg，腰围 82.5 cm"></textarea><div class="share-actions"><button class="share-button primary" data-action="send-manual">发送到电脑</button></div></section></div><section class="share-card"><div class="share-kicker">电脑端处理</div><h2>最近收到</h2><div class="share-list">${renderItems()}</div></section></div></div>`;
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
  state.notice = "";
  try {
    await enqueue(title, text);
    state.notice = "已发送到云端“当日训练记录”。电脑端打开“当日训练记录”即可在近 7 天列表看到；放入 Daily Entry 后仍需预览并确认。";
  }
  catch (error) { state.error = error.message || "发送失败，正式记录未改变。"; }
  state.busy = false;
  render();
}

root.addEventListener("click", async event => {
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (!action || state.busy) return;
  if (action === "clear-incoming") { state.incoming = null; render(); return; }
  if (action === "send-incoming") { state.pendingSend = { title: state.incoming?.mode === "outbound" ? "电脑 Daily Entry" : "手机分享", text: root.querySelector("[data-incoming-text]")?.value || "" }; render(); return; }
  if (action === "send-manual") { state.pendingSend = { title: "手动输入", text: root.querySelector("[data-manual-text]")?.value || "" }; render(); return; }
  if (action === "cancel-send") { state.pendingSend = null; render(); return; }
  if (action === "confirm-send") { const pending = state.pendingSend; state.pendingSend = null; await send(pending?.title, pending?.text); return; }
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
  state.incoming = { title: params.get("share_title") || "手机分享", text: sharedText, mode: params.get("share_mode") || params.get("mode") || "inbound" };
  history.replaceState({}, "", "./share.html");
}
load();
