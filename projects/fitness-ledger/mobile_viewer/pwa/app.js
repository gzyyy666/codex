import { apiDescription, getSearch, getToday, getTraining } from "./api.js";

const PLAN = [
  { id: "shoulders", label: "肩背训练", note: "第 1 天", emoji: "🏋️", color: "pink", terms: ["肩", "背", "shoulder", "back"] },
  { id: "chest", label: "胸腹训练", note: "第 2 天", emoji: "💪", color: "blue", terms: ["胸", "腹", "chest", "core"] },
  { id: "legs", label: "臀腿训练", note: "第 3 天", emoji: "🦵", color: "orange", terms: ["腿", "臀", "leg", "lower"] },
  { id: "cardio", label: "有氧循环", note: "第 4 天", emoji: "🔥", color: "yellow", terms: ["有氧", "cardio", "跑", "骑"] }
];

const state = {
  tab: readTab(),
  today: null,
  training: null,
  search: [],
  searchQuery: "",
  busy: true,
  error: ""
};

const app = document.querySelector("#app");

function readTab() {
  const value = window.location.hash.slice(1);
  return ["home", "plan", "records", "body", "more"].includes(value) ? value : "home";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function firstValue(object, keys, fallback = "-") {
  for (const key of keys) {
    const value = object?.[key];
    if (value !== undefined && value !== null && String(value).trim() !== "") return value;
  }
  return fallback;
}

function formatDate(value) {
  const text = String(value || "");
  return text.length >= 10 ? text.slice(0, 10) : text || "暂无日期";
}

function formatWeight(value) {
  if (value === "-" || value === "") return "-";
  return String(value).includes("kg") ? String(value) : `${value} kg`;
}

function trainingLabel(today) {
  return firstValue(today?.training, ["split", "Split"], firstValue(today?.body, ["Training"], "暂无训练"));
}

function isPlanActive(item, today) {
  const source = trainingLabel(today).toLowerCase();
  return item.terms.some(term => source.includes(term.toLowerCase()));
}

function summaryStats(today) {
  const body = today?.body || {};
  const diet = today?.diet || {};
  return [
    ["体重", formatWeight(firstValue(body, ["Weight (kg)", "weight", "weight_text"]))],
    ["训练", trainingLabel(today)],
    ["热量", firstValue(diet, ["Calories (kcal)", "calories"], "-")],
    ["蛋白质", firstValue(diet, ["Protein (g)", "protein"], "-")]
  ];
}

function setLines(movement) {
  const sets = Array.isArray(movement?.sets) ? movement.sets : [];
  return sets.map(row => {
    const weight = row.weight_text || (row.weight ? `${row.weight}kg` : "自重");
    return `${weight} × ${row.reps || "-"} × ${row.sets || 1}`;
  });
}

function renderHeader() {
  const date = formatDate(state.today?.date);
  const connection = state.busy ? "正在读取" : state.error ? "连接需检查" : "只读已连接";
  return `
    <header class="topbar">
      <div class="topline"><span>${escapeHtml(date)}</span><span class="connection-dot ${state.error ? "is-error" : ""}"></span><span>${escapeHtml(connection)}</span></div>
      <div class="greeting"><div><p class="eyebrow">FITNESS LEDGER</p><h1>💪 每日健身</h1><p>坚持记录，遇见更好的自己</p></div><div class="avatar">FL</div></div>
    </header>`;
}

function renderHome() {
  const today = state.today || {};
  const stats = summaryStats(today);
  const activePlan = PLAN.find(item => isPlanActive(item, today));
  const recordDate = formatDate(today.date);
  return `
    <main class="page home-page">
      <section class="hero-workbench">
        <div><span class="hero-kicker">只读训练账本</span><h2>今天先做<br><strong>${escapeHtml(trainingLabel(today))}</strong></h2><p>数据来自 FL 的最新同步副本，不在手机端直接改写正式记录。</p></div>
        <div class="hero-mark">${activePlan?.emoji || "✓"}</div>
      </section>
      <section class="today-action ${state.error ? "has-error" : ""}">
        <div class="status-ring">${state.error ? "!" : "✓"}</div>
        <div class="action-copy"><strong>${state.error ? "数据暂不可用" : "最新记录已可查看"}</strong><span>${escapeHtml(recordDate)} · ${escapeHtml(trainingLabel(today))}</span></div>
        <button class="primary-button" data-action="today">查看</button>
      </section>
      <section class="section-block"><div class="section-heading"><h2>一周四练计划</h2><button class="text-button" data-tab="plan">查看全部</button></div><div class="plan-grid">${PLAN.map(renderPlanCard).join("")}</div></section>
      <section class="section-block"><div class="section-heading"><h2>今日数据</h2><span class="muted">只读摘要</span></div><div class="stats-grid">${stats.map(([label, value]) => `<div class="metric-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}</div></section>
      ${state.error ? `<div class="notice error-notice">${escapeHtml(state.error)}<br><span>如果部署到手机，请确认 PWA 的 Web API 地址已配置，且接口允许当前登录方式访问。</span></div>` : ""}
    </main>`;
}

function renderPlanCard(item) {
  const active = isPlanActive(item, state.today || {});
  return `<button class="plan-card ${item.color} ${active ? "is-active" : ""}" data-plan="${item.id}"><span class="plan-emoji">${item.emoji}</span><strong>${item.label}</strong><small>${active ? "当前记录" : item.note}</small></button>`;
}

function renderPlan() {
  return `<main class="page"><section class="page-intro"><span class="eyebrow purple">PLAN</span><h2>一周四练</h2><p>先固定训练节奏，具体动作继续从 FL 的训练参考中读取。</p></section><section class="plan-list">${PLAN.map(item => `<article class="plan-row ${item.color} ${isPlanActive(item, state.today || {}) ? "is-active" : ""}"><span class="plan-emoji">${item.emoji}</span><div><strong>${item.label}</strong><span>${item.note} · ${isPlanActive(item, state.today || {}) ? "当前同步记录匹配" : "按你的训练周期使用"}</span></div><span class="row-arrow">›</span></article>`).join("")}</section><div class="notice">计划卡片目前是前台工作台配置，不会写入或覆盖 FL 的正式训练记录。</div></main>`;
}

function renderRecords() {
  const today = state.today || {};
  const sessions = Array.isArray(today.training_sessions) ? today.training_sessions : [];
  const training = state.training;
  const movements = training?.movements || training?.sessions?.[0]?.movements || [];
  return `<main class="page"><section class="page-intro"><span class="eyebrow purple">RECORDS</span><h2>最近记录</h2><p>原始记录和结构化训练数据继续由 FL 管理。</p></section><section class="record-summary"><div class="record-date">${escapeHtml(formatDate(today.date))}</div><strong>${escapeHtml(trainingLabel(today))}</strong><span>${escapeHtml(firstValue(today.training, ["summary", "Standardized Summary"], "暂无训练摘要"))}</span></section><section class="section-block"><div class="section-heading"><h2>训练动作</h2><span class="muted">${movements.length || 0} 项</span></div>${movements.length ? `<div class="movement-list">${movements.map((item, index) => `<article class="movement-row"><div class="movement-index">${item.order || index + 1}</div><div><strong>${escapeHtml(item.movement_name || item.display_name || item.movement_id || "未命名动作")}</strong><span>${escapeHtml(item.english_name || item.muscle_group || "")}</span><small>${escapeHtml(setLines(item).join(" · ") || item.summary || "暂无组数摘要")}</small></div></article>`).join("")}</div>` : `<div class="empty-card">点击“刷新数据”获取训练详情，或确认当前接口已部署。</div>`}</section><button class="wide-button" data-action="refresh">刷新数据</button></main>`;
}

function renderBody() {
  const body = state.today?.body || {};
  const diet = state.today?.diet || {};
  return `<main class="page"><section class="page-intro"><span class="eyebrow purple">BODY</span><h2>身体数据</h2><p>先看今天的关键数字，历史趋势由后续 Web 只读接口补齐。</p></section><div class="body-hero"><span>当前体重</span><strong>${escapeHtml(formatWeight(firstValue(body, ["Weight (kg)", "weight", "weight_text"])))}</strong><small>${escapeHtml(formatDate(state.today?.date))}</small></div><div class="stats-grid"><div class="metric-card"><span>热量</span><strong>${escapeHtml(firstValue(diet, ["Calories (kcal)", "calories"]))}</strong></div><div class="metric-card"><span>蛋白质</span><strong>${escapeHtml(firstValue(diet, ["Protein (g)", "protein"]))}</strong></div><div class="metric-card"><span>碳水</span><strong>${escapeHtml(firstValue(diet, ["Carbs (g)", "carbs"]))}</strong></div><div class="metric-card"><span>脂肪</span><strong>${escapeHtml(firstValue(diet, ["Fat (g)", "fat"]))}</strong></div></div><div class="notice">当前 PWA 保持只读，不会在浏览器中保存或提交身体数据。</div></main>`;
}

function renderMore() {
  const api = apiDescription();
  return `<main class="page"><section class="page-intro"><span class="eyebrow purple">MORE</span><h2>数据与设置</h2><p>把复杂的数据管理留在 FL，把手机端保持成简单入口。</p></section><section class="settings-card"><div><span>访问模式</span><strong>只读工作台</strong></div><div><span>接口位置</span><strong>${escapeHtml(api.baseUrl)}</strong></div><div><span>登录凭据</span><strong>不在前端保存密钥</strong></div><div><span>数据写入</span><strong>已关闭</strong></div></section><div class="notice">如果在 iPhone 上安装：用 Safari 打开部署地址，点击分享按钮，再选择“添加到主屏幕”。</div><button class="wide-button" data-action="refresh">重新读取云端</button></main>`;
}

function renderBottomNav() {
  const items = [["home", "⌂", "首页"], ["plan", "▦", "计划"], ["records", "▤", "记录"], ["body", "◒", "体重"], ["more", "•••", "更多"]];
  return `<nav class="bottom-nav">${items.map(([id, icon, label]) => `<button class="nav-item ${state.tab === id ? "is-active" : ""}" data-tab="${id}"><span>${icon}</span><small>${label}</small></button>`).join("")}</nav>`;
}

function render() {
  const page = { home: renderHome, plan: renderPlan, records: renderRecords, body: renderBody, more: renderMore }[state.tab]();
  app.innerHTML = `${renderHeader()}${page}${renderBottomNav()}`;
}

async function refresh() {
  state.busy = true;
  state.error = "";
  render();
  try {
    state.today = await getToday();
    if (state.tab === "records" && state.today?.date) {
      state.training = await getTraining(state.today.date);
    }
  } catch (error) {
    state.error = error.message === "HTTP_401" || error.message === "FORBIDDEN"
      ? "当前 Web 访问尚未完成登录或授权。"
      : "暂时无法读取 FL 数据。";
  } finally {
    state.busy = false;
    render();
  }
}

async function openRecords() {
  state.tab = "records";
  window.location.hash = "records";
  render();
  if (!state.training && state.today?.date) {
    try { state.training = await getTraining(state.today.date); render(); } catch (_error) { /* home data remains usable */ }
  }
}

document.addEventListener("click", event => {
  const tabButton = event.target.closest("[data-tab]");
  if (tabButton) {
    state.tab = tabButton.dataset.tab;
    window.location.hash = state.tab;
    render();
    if (state.tab === "records" && !state.training) openRecords();
    return;
  }
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "today") {
    state.tab = "records";
    window.location.hash = "records";
    openRecords();
  } else if (action === "refresh") {
    refresh();
  }
});

window.addEventListener("hashchange", () => {
  state.tab = readTab();
  render();
});

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}

render();
refresh();
