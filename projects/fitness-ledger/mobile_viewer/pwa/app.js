import { apiDescription, call } from "./api.js";

const BODY_PARTS = [
  { id: "shoulders", cn: "肩", en: "SHOULDERS", tone: "amber" },
  { id: "chest", cn: "胸", en: "CHEST", tone: "coral" },
  { id: "back", cn: "背", en: "BACK", tone: "teal" },
  { id: "legs", cn: "腿", en: "LEGS", tone: "violet" },
  { id: "arms", cn: "手臂", en: "ARMS", tone: "cyan" }
];
const NOTE_KEY = "fitness-ledger:freeform-notepad:v2:current";
const BUILD_VERSION = "v2026.08.03-mobile-input-14";
const app = document.querySelector("#app");
const state = {
  route: parseRoute(), loading: true, error: "", status: null, identity: null,
  areas: [], area: null, trainingRecords: [], bodyRecords: [], dietRecords: [],
  record: null, trainingDay: null, movement: null, movementHistory: [],
  sortBy: "frequency", order: "newest", query: "", note: loadNote(),
  noteOpen: false, noteExpanded: false, noteCandidates: [], noteCandidatesCollapsed: false,
  showAliases: false, expanded: {}, candidatesRequest: 0
};

function parseRoute() {
  const raw = window.location.hash.slice(1) || "reference";
  const [path, query = ""] = raw.split("?");
  return { name: path || "reference", params: new URLSearchParams(query) };
}
function esc(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
function text(value, fallback = "-") { const result = String(value ?? "").trim(); return result || fallback; }
function date(value) { return String(value || "").slice(0, 10) || "暂无日期"; }
function loadNote() { try { return localStorage.getItem(NOTE_KEY) || ""; } catch (_) { return ""; } }
function saveNote(value) { state.note = String(value || ""); try { localStorage.setItem(NOTE_KEY, state.note); } catch (_) {} }
function bodyPart(id) { return BODY_PARTS.find(item => item.id === id) || BODY_PARTS[0]; }
function isTopRoute() { return ["reference", "training", "status"].includes(state.route.name); }
function navigate(route) { window.location.hash = route; }
function setError(error) { state.error = error?.message === "HTTP_401" ? "当前 Web 账号尚未完成授权。" : "读取失败，请检查网络与只读接口。"; }
function renderStartupError() {
  if (!app) return;
  app.innerHTML = `<main class="page"><div class="eyebrow">STARTUP / RECOVERY</div><h1 class="title">页面正在恢复。</h1><p class="intro">工作台脚本没有正常启动。请刷新一次；如果仍为空白，请把当前页面地址发给我。</p><button class="archive-entry" onclick="location.reload()"><span><strong>重新加载</strong><small>刷新工作台</small></span><b>↻</b></button></main>`;
}

function freshness(meta) {
  if (!meta) return "同步状态未知";
  const generated = String(meta.generated_at || "");
  const stamp = Date.parse(generated);
  const stale = Number.isFinite(stamp) && (Date.now() - stamp) > 48 * 3600000;
  return { text: `云端更新 ${generated || "尚未同步"} · 最新记录 ${meta.latest_record_date || "暂无"}`, stale };
}

function setLine(item) {
  const weight = item.weight_text || item.weightText || (item.weight ? `${item.weight} kg` : "自重");
  return `${weight} ${item.reps ? `${item.reps} 次` : ""} ${item.sets ? `× ${item.sets} 组` : ""}`.trim();
}
function setSummary(item) {
  if (item.summary) return item.summary;
  if (Array.isArray(item.sets) && item.sets.length) return item.sets.map(setLine).join("  ");
  if (Array.isArray(item.sets_lines)) return item.sets_lines.join(" · ");
  return "暂无组数记录";
}
function metric(item, key) { return item?.[key] ?? item?.[key.replace(/_([a-z])/g, (_, c) => c.toUpperCase())] ?? 0; }

function renderShell(content) {
  const nav = isTopRoute() ? `<nav class="tabbar"><button class="tab ${state.route.name === "reference" ? "active" : ""}" data-route="reference"><span>⌂</span><small>首页</small></button><button class="tab ${state.route.name === "training" ? "active" : ""}" data-route="training"><span>▤</span><small>训练记录</small></button><button class="tab ${state.route.name === "status" ? "active" : ""}" data-route="status"><span>◉</span><small>状态</small></button></nav>` : "";
  return `${content}${nav}`;
}
function pageStart(className = "") { return `<main class="page ${className}">`; }
function pageEnd() { return "</main>"; }
function header(eyebrow, title, intro = "") { return `<div class="eyebrow">${esc(eyebrow)}</div><h1 class="title">${title}</h1>${intro ? `<p class="intro">${esc(intro)}</p>` : ""}`; }
function stateMessage(message, error = false) { return `<div class="state ${error ? "error" : ""}">${esc(message)}</div>`; }

function renderReference() {
  const selected = state.route.params.get("part");
  if (!selected) {
    const fresh = freshness(state.status);
    return renderShell(`${pageStart("reference-page")}${header("BEFORE YOU TRAIN / READ ONLY", "训练部位<br>档案。", "不是训练计划。选择今天可能练的部位，快速回看动作、最近表现与历史轨迹。")}${fresh ? `<div class="freshness ${fresh.stale ? "stale" : ""}">${esc(fresh.text)}</div>` : ""}${state.loading ? stateMessage("正在整理动作档案…") : state.error ? stateMessage(state.error, true) : `<div class="area-list">${state.areas.map((item, index) => `<button class="area-row tone-${item.tone}" data-route="reference?part=${item.id}"><span class="area-number">0${index + 1}</span><span class="area-name"><b>${esc(item.cn || item.label)}</b><small>${esc(item.en || item.labelEn)}</small></span><span class="area-data"><small>${item.movement_count || 0} 动作</small><small>${item.session_count || 0} 次训练</small></span><span class="area-arrow">→</span></button>`).join("")}</div>`}${pageEnd()}`);
  }
  return renderReferenceArea(selected);
}

function renderReferenceArea(selected) {
  const area = state.area || { ...bodyPart(selected), label: bodyPart(selected).cn, labelEn: bodyPart(selected).en, movements: [], sessions: [] };
  const part = bodyPart(selected);
  const note = state.noteOpen ? `<section class="notepad-card"><div class="notepad-head"><div><div class="eyebrow">LOCAL ONLY / TRAINING NOTE</div><h2>TRAINING NOTE / 训练记录</h2></div><button data-action="toggle-note">FLIP</button></div><textarea data-note placeholder="Freeform notes, any format.">${esc(state.note)}</textarea><div class="notepad-actions"><button data-action="copy-note">${state.noteExpanded ? "COPY ALL" : "COPY"}</button><button class="danger-link" data-action="clear-note">CLEAR</button><button data-action="expand-note">${state.noteExpanded ? "COLLAPSE EDIT" : "EXPAND"}</button></div><div class="notepad-status">已自动保存</div></section>` : `<button class="part-hero tone-${part.tone}" data-action="toggle-note"><div class="hero-top"><span class="eyebrow">${esc(area.labelEn || part.en)} ARCHIVE</span><span class="flip-hint">FLIP</span></div><div class="part-title">${esc(area.label || part.cn)}</div><div class="part-meta">${area.session_count || 0} 次训练 · ${area.movement_count || 0} 个动作</div><div class="part-latest">最近训练 ${esc(area.latest_date || "暂无")}</div></button>`;
  const candidates = state.noteCandidates.length || state.noteCandidatesCollapsed ? `<section class="candidates ${state.noteCandidatesCollapsed ? "collapsed" : ""}"><div class="candidate-head"><span>可能相关动作 · 最近记录</span><button data-action="toggle-candidates">${state.noteCandidatesCollapsed ? "展开" : "收起"}</button></div>${!state.noteCandidatesCollapsed ? state.noteCandidates.map(candidate => `<button class="candidate" data-action="candidate" data-id="${esc(candidate.movement_id)}"><span><b>${esc(candidate.display_name)}</b><small>${esc(candidate.english_name || candidate.body_part_label || "")}</small>${candidate.preview ? `<em>${esc(candidate.preview)}</em>` : ""}</span><strong>详情 →</strong></button>`).join("") : ""}</section>` : "";
  const sort = state.sortBy;
  const movements = [...(area.movements || [])].sort((a, b) => sort === "recent" ? String(b.latest?.date || "").localeCompare(String(a.latest?.date || "")) : sort === "days" ? 0 : (Number(b.pinned) - Number(a.pinned) || Number(a.focus_rank || 9999) - Number(b.focus_rank || 9999) || b.sessions - a.sessions));
  const body = state.loading ? stateMessage(`正在读取${area.label || part.cn}部档案…`) : state.error ? stateMessage(state.error, true) : sort === "days" ? renderSessions(area.sessions || [], area.label || part.cn) : `<section class="movement-list"><div class="list-heading"><div><div class="eyebrow">MOVEMENTS / FREQUENCY</div><h2 class="section-title">动作与最近表现</h2></div><span class="count">${area.movement_count || movements.length}</span></div>${movements.length ? movements.map(renderMovementCard).join("") : stateMessage("该部位暂时没有动作历史。")}</section>`;
  return renderShell(`${pageStart(`reference-page selected-theme tone-page-${part.tone}`)}<img class="theme-art" src="./images/themes-v2/${esc(selected)}.webp" alt="">${note}${candidates}<div class="part-switch">${BODY_PARTS.map(item => `<button class="part-pill ${selected === item.id ? `active tone-${item.tone}` : ""}" data-route="reference?part=${item.id}">${item.cn}</button>`).join("")}</div><div class="sort-rail"><span class="sort-label">排序</span>${[["frequency", "训练频率"], ["recent", "最近训练"], ["days", "按训练日"]].map(([id, label]) => `<button class="sort-option ${sort === id ? "active" : ""}" data-sort="${id}">${label}</button>`).join("")}</div>${body}${state.noteDetail ? renderNoteDetail() : ""}${pageEnd()}`);
}

function renderMovementCard(item) {
  return `<button class="movement-card" data-action="movement" data-id="${esc(item.movement_id)}" data-part="${esc(state.route.params.get("part") || "")}"><div class="movement-head"><div>${item.pinned ? `<span class="focus-mark">★ FOCUS</span>` : ""}<div class="movement-name">${esc(item.display_name)}</div><div class="movement-en">${esc(item.english_name || "")}</div></div><span class="session-badge">${item.sessions || 0} 次</span></div>${item.latest ? `<div class="latest-set"><span>最近</span><span>${esc(item.latest.date)}${item.latest.order ? ` · 第 ${item.latest.order} 动作` : ""}</span></div><div class="set-summary">${esc(setSummary(item.latest))}</div>` : ""}<div class="compare-grid"><div class="compare-cell"><span>上一次</span><b>${esc(item.previous ? setSummary(item.previous) : "首次记录")}</b></div><div class="compare-cell"><span>历史最好</span><b>${item.best && metric(item.best, "max_weight") ? `${metric(item.best, "max_weight")} kg` : item.best && metric(item.best, "total_reps") ? `${metric(item.best, "total_reps")} reps` : "-"}</b></div></div>${item.latest?.notes ? `<div class="movement-note">${esc(item.latest.notes)}</div>` : ""}<div class="movement-action">查看完整轨迹 →</div></button>`;
}
function renderSessions(sessions, label) {
  return `<section class="session-list"><div class="list-heading"><div><div class="eyebrow">TRAINING DAYS / RECENT</div><h2 class="section-title">相关训练日</h2></div><span class="count">${sessions.length}</span></div>${sessions.length ? sessions.map(item => `<button class="session-card" data-action="session" data-date="${esc(item.date)}" data-part="${esc(state.route.params.get("part") || "")}"><div class="session-card-head"><b>${esc(item.date)}</b><span>${esc(item.title || item.split || `${label}训练`)}</span></div><div class="session-meta"><span>${item.related_count || 0} 个相关动作</span><span>完整训练上下文</span></div><div class="chips">${(item.related_movements || []).slice(0, 4).map(name => `<span>${esc(name)}</span>`).join("")}</div><p>${esc(item.full_summary || item.movement_summary || "暂无完整动作摘要")}</p>${item.notes ? `<div class="session-note">${esc(item.notes)}</div>` : ""}<div class="movement-action">查看当日训练 →</div></button>`).join("") : stateMessage("该部位暂时没有相关训练日。")}</section>`;
}

function renderTraining() {
  const records = filterRecords(state.trainingRecords, state.query, state.order);
  const fresh = freshness(state.status);
  return renderShell(`${pageStart("training-page")}<img class="archive-art" src="./images/training-archive.webp" alt="">${header("TRAINING ARCHIVE / DAILY", "训练记录。", "按日期回看当天训练主题与记录，需要细节时再展开。")}${fresh ? `<div class="freshness ${fresh.stale ? "stale" : ""}">${esc(fresh.text)}</div>` : ""}<div class="archive-tools"><input data-search placeholder="搜索日期，如 6-30 / 06.30" value="${esc(state.query)}"><button data-action="toggle-order">${state.order === "newest" ? "最新优先 ↓" : "最早优先 ↑"}</button></div>${state.loading ? stateMessage("正在读取训练档案…") : state.error ? stateMessage(state.error, true) : records.length ? `<section class="training-list">${records.map((item, index) => `<button class="training-slip slip-tone-${index % 3}" data-action="training-record" data-date="${esc(item.Date)}"><span class="training-index">${String(index + 1).padStart(2, "0")}</span><span class="slip-label">TRAINING NOTE</span><b class="training-date">${esc(item.Date)}</b><strong>${esc(item.Split || "未标注训练主题")}</strong><p>${esc(item["Standardized Summary"] || item.Summary || "暂无训练摘要")}</p>${item.Notes ? `<div class="training-note">${esc(item.Notes)}</div>` : ""}<span class="training-action">查看当日训练 →</span></button>`).join("")}</section>` : stateMessage("没有匹配的训练记录。")}${pageEnd()}`);
}
function filterRecords(records, query, order) { const needle = String(query || "").trim().replace(/[./]/g, "-"); return [...records].filter(item => !needle || String(item.Date || "").includes(needle)).sort((a, b) => (order === "oldest" ? 1 : -1) * String(a.Date || "").localeCompare(String(b.Date || ""))); }

function renderStatus() {
  const fresh = state.status;
  return renderShell(`${pageStart("status-page")}${header("LOCAL-FIRST / READ ONLY", "同步与档案。")}${state.loading ? stateMessage("检查中…") : state.error ? stateMessage(state.error, true) : `<section class="status-slab"><span class="status-dot"></span><div class="eyebrow">REPLICA STATUS</div><h2>只读副本已连接</h2><div class="row"><span>最后同步</span><b>${esc(fresh?.generated_at || "尚未同步")}</b></div><div class="row"><span>最新记录</span><b>${esc(fresh?.latest_record_date || "暂无")}</b></div><div class="row"><span>数据结构</span><b>${esc(fresh?.schema || "-")}</b></div></section><button class="archive-entry" data-route="body"><span><span class="eyebrow">SECONDARY ARCHIVE</span><strong>身体记录</strong><small>体重、排便、训练与有氧</small></span><b>→</b></button><button class="archive-entry diet-entry" data-route="diet"><span><span class="eyebrow">SECONDARY ARCHIVE</span><strong>饮食记录</strong><small>热量、三大营养素与餐食便签</small></span><b>→</b></button><section class="debug-card"><div class="eyebrow">ACCESS DIAGNOSTICS / NO PRIVATE DATA</div><div class="row"><span>权限</span><b>${state.identity?.openid ? "已识别账号" : "未识别 / Web 端"}</b></div><div class="row"><span>OpenID</span><b>${esc(state.identity?.openid || "未获取")}</b></div><div class="row"><span>Environment</span><b>${esc(state.identity?.env || "当前部署环境")}</b></div><div class="row"><span>前端版本</span><b>${BUILD_VERSION}</b></div></section>`}${pageEnd()}`);
}

function renderArchive(kind) {
  const isBody = kind === "body"; const records = isBody ? state.bodyRecords : state.dietRecords; const filtered = records.filter(item => !state.query || String(item.Date || "").includes(state.query.replace(/[./]/g, "-"))).sort((a, b) => (state.order === "oldest" ? 1 : -1) * String(a.Date || "").localeCompare(String(b.Date || "")));
  return `${pageStart(`${kind}-page`)}${header(isBody ? "BODY ARCHIVE / READ ONLY" : "DIET ARCHIVE / READ ONLY", isBody ? "身体记录。" : "饮食便签。", isBody ? "体重、训练与当天状态，按日期倒序保留。" : "先看热量与三大营养素，需要时再打开完整餐食。") }<div class="archive-tools"><input data-search placeholder="搜索日期，如 6-30 / 06.30" value="${esc(state.query)}"><button data-action="toggle-order">${state.order === "newest" ? "最新 ↓" : "最早 ↑"}</button></div>${state.loading ? stateMessage("正在读取档案…") : state.error ? stateMessage(state.error, true) : filtered.length ? filtered.map((item, index) => isBody ? `<button class="body-slip palette-${index % 4}" data-action="archive-record" data-date="${esc(item.Date)}"><span class="slip-index">${String(index + 1).padStart(2, "0")}</span><b class="slip-date">${esc(item.Date)}</b><strong class="slip-weight">${esc(text(item["Weight (kg)"], "-"))}<small>kg</small></strong><div class="slip-facts"><span>训练 <b>${esc(item.Training || "休息")}</b></span><span>排便 <b>${esc(item["Bowel Movement"] || "-")}</b></span><span>有氧 <b>${esc(item.Cardio || "无")}</b></span></div><p>${esc(item.Notes || "没有备注")}</p><span class="slip-action">查看记录 →</span></button>` : `<button class="diet-slip offset-${index % 3}" data-action="archive-record" data-date="${esc(item.Date)}"><div class="diet-head"><span><span class="eyebrow">NUTRITION NOTE</span><b>${esc(item.Date)}</b></span><strong>${esc(item["Calories (kcal)"] || "-")}<small>kcal</small></strong></div><div class="macro-strip"><span>P <b>${esc(item["Protein (g)"] || "-")}g</b></span><span>C <b>${esc(item["Carbs (g)"] || "-")}g</b></span><span>F <b>${esc(item["Fat (g)"] || "-")}g</b></span></div><p>${esc(item["Food Summary"] || "没有饮食摘要")}</p><span class="diet-action">阅读全文 →</span></button>`).join("") : stateMessage(isBody ? "暂无身体记录。" : "暂无饮食记录。")} ${pageEnd()}`;
}

function renderRecord() {
  const mode = state.route.params.get("mode") === "training"; const dateValue = state.route.params.get("date") || state.record?.date || "";
  if (mode) {
    const session = state.trainingDay?.session; const movements = state.trainingDay?.movements || [];
    return `${pageStart("record-page")}${header("TRAINING DAY / READ ONLY", dateValue || "训练日详情")}${state.loading ? stateMessage("读取中…") : state.error ? stateMessage(state.error, true) : !session ? stateMessage("该日期暂无训练明细。") : `<section class="record-section training-session-only"><div class="eyebrow">TRAINING SESSION</div><h2>${esc(session.split || "训练记录")}</h2>${session.summary ? `<p>${esc(session.summary)}</p>` : ""}${movements.length ? movements.map((item, index) => `<button class="training-action-card" data-action="movement" data-id="${esc(item.movement_id)}"><span>第 ${item.order || index + 1} 个动作</span><strong>${esc(item.movement_name || item.display_name || item.movement_id)}</strong><b>轨迹 →</b><small>${esc((item.sets || []).map(setLine).join(" · ") || "没有组数记录")}</small>${item.notes ? `<em>${esc(item.notes)}</em>` : ""}</button>`).join("") : stateMessage("该训练日暂无动作明细。")} ${session.notes ? `<div class="session-notes"><span>训练总备注</span>${esc(session.notes)}</div>` : ""}</section>`}${pageEnd()}`;
  }
  const detail = state.record;
  return `${pageStart("record-page")}${header("DAILY ARCHIVE / READ ONLY", dateValue || "记录详情")}${state.loading ? stateMessage("读取中…") : state.error ? stateMessage(state.error, true) : !detail ? stateMessage("该日期没有记录。") : `${(detail.body || []).map(item => `<section class="record-section body-section"><div class="record-head"><div><div class="eyebrow">BODY</div><h2>身体与当天状态</h2></div><button data-action="toggle" data-key="body">${state.expanded.body ? "收起" : "展开"}</button></div><div class="signal-grid"><span>WEIGHT<strong>${esc(item["Weight (kg)"] || "-")}kg</strong></span><span>BOWEL<strong>${esc(item["Bowel Movement"] || "-")}</strong></span></div><div class="row"><span>训练</span><b>${esc(item.Training || "未记录")}</b></div><div class="row"><span>有氧</span><b>${esc(item.Cardio || "未记录")}</b></div>${state.expanded.body ? `<p class="detail-text">${esc(item.Notes || "没有身体备注")}</p>` : ""}</section>`).join("")}${(detail.diet || []).map(item => `<section class="record-section diet-section"><div class="record-head"><div><div class="eyebrow">NUTRITION</div><h2>饮食</h2></div><button data-action="toggle" data-key="diet">${state.expanded.diet ? "收起" : "展开"}</button></div><div class="macro-line"><strong>${esc(item["Calories (kcal)"] || "-")} kcal</strong><span>P ${esc(item["Protein (g)"] || "-")} · C ${esc(item["Carbs (g)"] || "-")} · F ${esc(item["Fat (g)"] || "-")}</span></div><p class="detail-text ${state.expanded.diet ? "" : "clamp-3"}">${esc(item["Food Summary"] || "没有饮食摘要")}</p></section>`).join("")}${(detail.training || []).map(item => `<section class="record-section training-section"><div class="record-head"><div><div class="eyebrow">TRAINING</div><h2>${esc(item.Split || "训练记录")}</h2></div><button data-action="toggle" data-key="training">${state.expanded.training ? "收起" : "展开"}</button></div><p class="detail-text ${state.expanded.training ? "" : "clamp-3"}">${esc(item["Standardized Summary"] || "没有动作摘要")}</p>${state.expanded.training && item.Notes ? `<div class="training-note">${esc(item.Notes)}</div>` : ""}</section>`).join("")}`}${pageEnd()}`;
}

function renderMovement() {
  const movement = state.movement;
  const history = state.movementHistory || [];
  const latest = history[0];
  const previous = history[1];
  if (state.loading) return `${pageStart("movement-page")}${stateMessage("读取中…")}${pageEnd()}`;
  if (state.error) return `${pageStart("movement-page")}${stateMessage(state.error, true)}${pageEnd()}`;
  if (!movement) return `${pageStart("movement-page")}${stateMessage("没有找到该动作。")}${pageEnd()}`;

  const aliases = state.showAliases ? `<div class="chips">${(movement.aliases || []).map(item => `<span>${esc(item)}</span>`).join("")}</div>` : "";
  const hero = `<section class="movement-hero"><div class="eyebrow">MOVEMENT TRAJECTORY</div><h1 class="title movement-title">${esc(movement.display_name)}</h1><p>${esc(movement.english_name || "")} · ${esc(movement.muscle_group || "")}</p><button class="alias-toggle" data-action="aliases">${state.showAliases ? "收起别名" : "查看别名"} →</button>${aliases}</section>`;
  const latestMax = metric(latest, "max_weight") ? `${metric(latest, "max_weight")}kg` : "自重";
  const previousMax = previous ? (metric(previous, "max_weight") ? `${metric(previous, "max_weight")}kg` : "自重") : "-";
  const signal = latest ? `<section class="signal-board"><div class="board-head"><div><div class="eyebrow">RECENT SIGNALS</div><h2>最近变化</h2></div><span>${esc(date(latest.date))}</span></div><div class="signal-grid"><span>LATEST MAX<strong>${latestMax}</strong></span><span>TOTAL REPS<strong>${metric(latest, "total_reps") || "-"}</strong></span><span>VOLUME<strong>${metric(latest, "volume") || "-"}</strong></span><span>PREVIOUS MAX<strong>${previousMax}</strong></span></div></section>` : "";
  const historyCards = history.map((item, index) => {
    const orderLabel = item.order ? `第 ${item.order} 个动作` : `#${index + 1}`;
    const note = item.notes ? `<p>${esc(item.notes)}</p>` : "";
    return `<button class="history-slip" data-action="session" data-date="${esc(item.date)}"><div class="history-head"><b>${esc(date(item.date))}</b><span>${orderLabel}</span></div><div class="set-row"><span>${esc(setSummary(item))}</span><span>${metric(item, "total_reps") || "-"} reps</span></div>${note}<small>查看当天完整训练 →</small></button>`;
  }).join("");
  const trajectory = `<section class="trajectory"><div class="list-heading"><div><div class="eyebrow">RECENT THREE</div><h2 class="section-title">最近三次</h2></div><span class="count">${history.length}</span></div>${history.length ? historyCards : stateMessage("该动作暂无历史。")}</section>`;
  return `${pageStart("movement-page")}${hero}${signal}${trajectory}${pageEnd()}`;
}

function renderNoteDetail() { return ""; }

function render() {
  const active = document.activeElement;
  const focusedSelector = active?.matches("[data-note]") ? "[data-note]" : active?.matches("[data-search]") ? "[data-search]" : "";
  const focusedControl = focusedSelector ? {
    start: active.selectionStart,
    end: active.selectionEnd,
    scrollTop: active.scrollTop
  } : null;
  const name = state.route.name;
  const content = name === "reference" ? renderReference() : name === "training" ? renderTraining() : name === "status" ? renderStatus() : name === "body" ? renderArchive("body") : name === "diet" ? renderArchive("diet") : name === "record" ? renderRecord() : name === "movement" ? renderMovement() : renderReference();
  app.innerHTML = content;
  if (focusedControl) {
    const nextControl = app.querySelector(focusedSelector);
    if (nextControl) {
      nextControl.focus({ preventScroll: true });
      const length = nextControl.value.length;
      nextControl.setSelectionRange(Math.min(focusedControl.start, length), Math.min(focusedControl.end, length));
      nextControl.scrollTop = focusedControl.scrollTop;
    }
  }
}

async function loadRoute() {
  state.route = parseRoute(); state.loading = true; state.error = ""; render();
  try {
    const name = state.route.name; const part = state.route.params.get("part");
    if (name === "reference") {
      if (part) { const [area, records] = await Promise.all([call("bodyArea", { part }), call("trainingRecords")]); state.area = { ...area, sessions: (area.sessions || []).map(item => ({ ...item, full_summary: records.find(record => date(record.Date) === date(item.date))?.["Standardized Summary"] || item.full_summary })) }; }
      else { [state.areas, state.status] = await Promise.all([call("bodyAreas"), call("status")]); }
    } else if (name === "training") { [state.trainingRecords, state.status] = await Promise.all([call("trainingRecords"), call("status")]); }
    else if (name === "status") { [state.status, state.identity] = await Promise.all([call("status"), call("whoami")]); }
    else if (name === "body") state.bodyRecords = await call("bodyRecords", { limit: 30 });
    else if (name === "diet") state.dietRecords = await call("dietRecords", { limit: 30 });
    else if (name === "record") { const params = Object.fromEntries(state.route.params.entries()); if (params.mode === "training") state.trainingDay = await call("trainingDayDetail", { date: params.date }); else state.record = await call("recordDetail", { date: params.date }); }
    else if (name === "movement") { [state.movement, state.movementHistory] = await Promise.all([call("movement", { movementId: state.route.params.get("id") }), call("movementHistory", { movementId: state.route.params.get("id"), limit: 20 })]); }
  } catch (error) { setError(error); }
  state.loading = false; render();
}

let noteTimer;
async function updateCandidates() {
  clearTimeout(noteTimer); const request = ++state.candidatesRequest;
  if (!state.note.trim()) { state.noteCandidates = []; render(); return; }
  noteTimer = setTimeout(async () => {
    try {
      const catalog = await call("movementCatalog"); const source = state.note.toLowerCase();
      const matches = catalog.filter(item => [item.display_name, item.english_name, ...(item.aliases || [])].some(term => String(term || "").length > 1 && source.includes(String(term).toLowerCase()))).slice(0, 4);
      if (request !== state.candidatesRequest) return;
      state.noteCandidates = matches.map(item => ({ ...item, body_part_label: (item.body_parts || []).map(id => bodyPart(id).cn).join(" / ") })); render();
    } catch (_) { state.noteCandidates = []; render(); }
  }, 180);
}

document.addEventListener("input", event => { if (event.target.matches("[data-search]")) { state.query = event.target.value; render(); } if (event.target.matches("[data-note]")) { saveNote(event.target.value); updateCandidates(); } });
document.addEventListener("click", event => {
  const route = event.target.closest("[data-route]")?.dataset.route;
  if (route) { state.query = ""; state.order = "newest"; navigate(route); return; }
  const sort = event.target.closest("[data-sort]")?.dataset.sort; if (sort) { state.sortBy = sort; render(); return; }
  const action = event.target.closest("[data-action]")?.dataset.action; if (!action) return;
  if (action === "toggle-order") { state.order = state.order === "newest" ? "oldest" : "newest"; render(); }
  if (action === "toggle-note") { state.noteOpen = !state.noteOpen; render(); }
  if (action === "expand-note") { state.noteExpanded = !state.noteExpanded; render(); }
  if (action === "toggle-candidates") { state.noteCandidatesCollapsed = !state.noteCandidatesCollapsed; render(); }
  if (action === "copy-note") { navigator.clipboard?.writeText(state.note); }
  if (action === "clear-note") { if (window.confirm("清空当前 TRAINING NOTE？不会影响正式训练记录。")) { saveNote(""); state.noteCandidates = []; render(); } }
  if (action === "aliases") { state.showAliases = !state.showAliases; render(); }
  if (action === "movement" || action === "candidate") { navigate(`movement?id=${encodeURIComponent(event.target.closest("[data-id]").dataset.id)}&part=${encodeURIComponent(event.target.closest("[data-part]")?.dataset.part || state.route.params.get("part") || "")}`); }
  if (action === "session") { navigate(`record?mode=training&date=${encodeURIComponent(event.target.closest("[data-date]").dataset.date)}&part=${encodeURIComponent(event.target.closest("[data-part]")?.dataset.part || "")}`); }
  if (action === "training-record" || action === "archive-record") { navigate(`record?date=${encodeURIComponent(event.target.closest("[data-date]").dataset.date)}`); }
  if (action === "toggle") { const key = event.target.closest("[data-key]").dataset.key; state.expanded[key] = !state.expanded[key]; render(); }
});
window.addEventListener("hashchange", loadRoute);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("./sw.js").catch(() => {});
window.addEventListener("error", event => {
  if (!app?.innerHTML.trim()) renderStartupError();
  event.preventDefault();
});
window.addEventListener("unhandledrejection", event => {
  if (!app?.innerHTML.trim()) renderStartupError();
  event.preventDefault();
});
try { render(); } catch (_) { renderStartupError(); }
loadRoute().catch(() => renderStartupError());
