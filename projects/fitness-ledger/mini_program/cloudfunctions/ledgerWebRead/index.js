const cloud = require("wx-server-sdk");
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();

const COLLECTIONS = {
  meta: "fl_meta", latest: "fl_latest_summary", daily: "fl_daily_records",
  diet: "fl_diet_records", training: "fl_training_sessions", movements: "fl_movements",
  history: "fl_movement_history", search: "fl_search_index", raw: "fl_raw_entries",
  quality: "fl_data_quality_issues", dataModules: "fl_data_modules",
  dataModuleRecords: "fl_data_module_records", dataModuleContract: "fl_data_module_contract"
};

const BODY_PARTS = {
  shoulders: { label: "肩", labelEn: "SHOULDERS", groups: ["Shoulder", "Shoulders", "肩部"] },
  chest: { label: "胸", labelEn: "CHEST", groups: ["Chest", "胸部"] },
  back: { label: "背", labelEn: "BACK", groups: ["Back", "背部"] },
  legs: { label: "腿", labelEn: "LEGS", groups: ["Leg", "Legs", "Lower Body", "腿部"] },
  arms: { label: "手臂", labelEn: "ARMS", groups: ["Arm", "Arms", "Biceps", "Triceps", "手臂"] },
  glutes: { label: "臀", labelEn: "GLUTES", groups: ["Glute", "Glutes", "臀", "臀部", "Hip", "Hips"] },
  core: { label: "核心", labelEn: "CORE", groups: ["Core", "Ab", "Abs", "腹", "核心"] },
  cardio: { label: "有氧", labelEn: "CARDIO", groups: ["Cardio", "Aerobic", "有氧"] }
};

// Keep the read-only PWA contract aligned with the Web normalizer when the
// cloud metadata collection has not received the organization document yet.
// Core is visible by default; Glutes and Cardio remain opt-in.
const DEFAULT_MOVEMENT_CATEGORIES = [
  { category_id: "chest", display_name: "Chest", active: true, sort_order: 10, system: true },
  { category_id: "shoulders", display_name: "Shoulders", active: true, sort_order: 20, system: true },
  { category_id: "back", display_name: "Back", active: true, sort_order: 30, system: true },
  { category_id: "legs", display_name: "Legs", active: true, sort_order: 40, system: true },
  { category_id: "glutes", display_name: "Glutes", active: false, sort_order: 50, system: true },
  { category_id: "arms", display_name: "Arms", active: true, sort_order: 60, system: true },
  { category_id: "core", display_name: "Core", active: true, sort_order: 70, system: true },
  { category_id: "cardio", display_name: "Cardio", active: false, sort_order: 80, system: true }
];

function result(data) { return { ok: true, data }; }
function failure(code, message) { return { ok: false, code, message }; }
async function list(name, limit = 20, skip = 0, orderField = "Date") {
  return (await db.collection(name).orderBy(orderField, "desc").skip(skip).limit(Math.min(Math.max(limit, 1), 50)).get()).data;
}
async function all(name, maxItems = 500) {
  const rows = [];
  const pageSize = 100;
  for (let skip = 0; skip < maxItems; skip += pageSize) {
    const page = (await db.collection(name).skip(skip).limit(pageSize).get()).data;
    rows.push(...page);
    if (page.length < pageSize) break;
  }
  return rows.slice(0, maxItems);
}
async function safeAll(name, maxItems = 500) {
  try { return await all(name, maxItems); } catch (_error) { return []; }
}
function moduleSurface(value, fallbackValue, fallbackLabel) {
  if (value && typeof value === "object") return { value: String(value.value || fallbackValue), label: String(value.label || fallbackLabel) };
  return { value: String(value || fallbackValue), label: fallbackLabel };
}
function mobileRecord(item, moduleId) {
  const record = {
    record_id: String(item.record_id || item.id || item._id || ""),
    module_id: String(item.module_id || moduleId || ""),
    date: String(item.date || item.Date || "").slice(0, 10),
    value: item.value,
    actual_unit: String(item.actual_unit || item.display_unit || "")
  };
  if (item.display_value !== undefined && item.display_value !== null) record.display_value = item.display_value;
  if (item.display_unit) record.display_unit = String(item.display_unit);
  return record;
}
function normalizedMobileContract(payload) {
  const modules = Array.isArray(payload && payload.modules) ? payload.modules : [];
  return {
    schema: "fitness-ledger-mini-module-contract-v1",
    page_required: false,
    renderers: Array.from(new Set(modules.map(item => String(item.renderer || "")).filter(Boolean))).sort(),
    modules: modules.map(item => {
      const history = (Array.isArray(item.history) ? item.history : []).map(record => mobileRecord(record, item.module_id)).filter(record => record.date);
      history.sort((a, b) => b.date.localeCompare(a.date));
      const latest = item.latest ? mobileRecord(item.latest, item.module_id) : (history[0] || null);
      return {
        module_id: String(item.module_id || ""),
        label: String(item.label || item.module_id || ""),
        category_id: String(item.category_id || "extension"),
        renderer: String(item.renderer || "single_metric"),
        status: String(item.status || "active"),
        recording_enabled: item.recording_enabled !== false,
        record_level: item.record_level || { value: "daily_scalar", label: "每日一个数值" },
        display_surface: moduleSurface(item.display_surface, "category_page", "跟随所属类别页面"),
        display_page: item.display_page ? moduleSurface(item.display_page, "home", "首页") : null,
        latest,
        history,
        empty_state: latest || history.length ? null : { kind: "empty", message: "暂无记录" }
      };
    }).filter(item => item.module_id)
  };
}
function buildMobileDataModuleContract(moduleRows, recordRows) {
  const recordsByModule = {};
  (recordRows || []).forEach(item => {
    const moduleId = String(item.module_id || "");
    if (!moduleId) return;
    if (!recordsByModule[moduleId]) recordsByModule[moduleId] = [];
    recordsByModule[moduleId].push(mobileRecord(item, moduleId));
  });
  const modules = (moduleRows || []).filter(item => item && item.mini_program_visible !== false).map(item => {
    const moduleId = String(item.module_id || "");
    const history = (recordsByModule[moduleId] || []).filter(record => record.date).sort((a, b) => b.date.localeCompare(a.date));
    return { ...item, module_id: moduleId, history, latest: history[0] || null };
  });
  return normalizedMobileContract({ modules });
}
async function mobileDataModulePayload() {
  // Prefer the full sanitized collections so the Web archive is not limited
  // to the compact Mini contract's history window.
  const [modules, records] = await Promise.all([
    safeAll(COLLECTIONS.dataModules, 200),
    safeAll(COLLECTIONS.dataModuleRecords, 1000)
  ]);
  if (modules.length) return buildMobileDataModuleContract(modules, records);
  const contractRows = await safeAll(COLLECTIONS.dataModuleContract, 3);
  const contract = contractRows.find(item => item && item.schema === "fitness-ledger-mini-module-contract-v1");
  return contract ? normalizedMobileContract(contract) : normalizedMobileContract({ modules: [] });
}
function normalized(value) { return String(value || "").trim().toLowerCase(); }
function matchesAny(value, terms) {
  const source = normalized(value);
  return terms.some(term => source.includes(normalized(term)));
}
function groupMatches(value, groups) {
  const source = normalized(value);
  return groups.some(group => source === normalized(group) || source.includes(normalized(group)));
}

function fallbackThemeId(label) {
  return `legacy:${String(label || "training").trim().toLowerCase().replace(/[^a-z0-9\u3400-\u9fff]+/g, "-").replace(/^-+|-+$/g, "") || "training"}`;
}

function themeIds(record, organization) {
  const themes = Array.isArray(organization && organization.session_themes) ? organization.session_themes : [];
  const valid = new Set(themes.map(item => String(item.theme_id || "")).filter(Boolean));
  const stored = Array.isArray(record && record.session_theme_ids)
    ? record.session_theme_ids
    : [record && record.session_theme_id];
  const ids = stored.map(value => String(value || "").trim()).filter(value => value && valid.has(value));
  if (ids.length) return Array.from(new Set(ids));
  const label = String((record && (record.session_theme_name || record["Session Theme"] || record.Split)) || "").trim();
  const matched = themes.find(item => String(item.display_name || "").trim() === label);
  return matched ? [String(matched.theme_id)] : (label ? [fallbackThemeId(label)] : []);
}

function themeNames(record, organization) {
  const themes = Array.isArray(organization && organization.session_themes) ? organization.session_themes : [];
  const byId = Object.fromEntries(themes.map(item => [String(item.theme_id || ""), String(item.display_name || item.theme_id || "")]));
  const names = themeIds(record, organization).map(id => byId[id]).filter(Boolean);
  const persisted = String((record && record.session_theme_name) || "").trim();
  if (persisted && !names.includes(persisted)) names.push(persisted);
  return names;
}

function fallbackTrainingOrganization(trainingRows) {
  const themes = [];
  let seen = new Set();
  (trainingRows || []).forEach(row => {
    const label = String(row.session_theme_name || row["Session Theme"] || row.Split || "").trim();
    if (!label) return;
    const id = String(row.session_theme_id || "").trim() || fallbackThemeId(label);
    if (seen.has(id)) return;
    seen = new Set([...seen, id]);
    themes.push({ theme_id: id, display_name: label, active: true, pinned: false, sort_order: themes.length * 10, color_key: "neutral" });
  });
  return { session_themes: themes, movement_categories: DEFAULT_MOVEMENT_CATEGORIES.map(item => ({ ...item })) };
}

function mergeMovementCategories(existing) {
  const rows = Array.isArray(existing) ? existing : [];
  const byId = new Map(rows
    .filter(item => item && String(item.category_id || "").trim())
    .map(item => [String(item.category_id), item]));
  const merged = DEFAULT_MOVEMENT_CATEGORIES.map(item => ({ ...item, ...(byId.get(item.category_id) || {}) }));
  const known = new Set(merged.map(item => item.category_id));
  rows.forEach(item => {
    const categoryId = String(item?.category_id || "").trim();
    if (categoryId && !known.has(categoryId)) merged.push({ ...item, category_id: categoryId });
  });
  return merged;
}

async function trainingOrganizationPayload(trainingRows) {
  const metaRows = await safeAll(COLLECTIONS.meta, 3);
  const stored = metaRows.find(item => item && item.training_organization && typeof item.training_organization === "object");
  const organization = stored && stored.training_organization;
  if (!organization) return fallbackTrainingOrganization(trainingRows);
  return {
    session_themes: Array.isArray(organization.session_themes) ? organization.session_themes.filter(item => item && item.active !== false) : [],
    movement_categories: mergeMovementCategories(organization.movement_categories)
  };
}

function decorateTrainingRows(rows, organization) {
  return (rows || []).map(row => ({ ...row, theme_names: themeNames(row, organization) }));
}
function setSummary(sets) {
  return (Array.isArray(sets) ? sets : []).map(item => {
    if (Array.isArray(item.segments) && item.segments.length) {
      const parts = item.segments.map(segment => `${segment.weight_text || (Number(segment.weight) > 0 ? `${Number(segment.weight)}kg` : "自重")} × ${segment.reps || "-"}`).join(" + ");
      return `${parts}${Number(item.sets || 1) > 1 ? ` × ${item.sets}组` : ""}`;
    }
    const weight = item.weight_text || (Number(item.weight) > 0 ? `${Number(item.weight)}kg` : "自重");
    return `${weight} × ${item.reps || "-"} × ${item.sets || 1}`;
  }).join(" · ");
}
function compactHistory(item) {
  const metrics = item.metrics || {};
  return {
    id: item.id || item._id,
    date: item.date || "",
    order: item.order || null,
    sets: item.sets || [],
    summary: setSummary(item.sets),
    notes: item.notes || "",
    max_weight: Number(metrics.max_weight || 0),
    total_reps: Number(metrics.total_reps || 0),
    volume: Number(metrics.volume || 0),
    organization_relations: Array.isArray(item.organization_relations) ? item.organization_relations : []
  };
}
function relationContextForItem(session, item, movementMap) {
  const itemId = String(item?.movement_instance_id || item?.id || "");
  if (!itemId || !session) return [];
  const sessionItems = Array.isArray(session.movement_items) ? session.movement_items : [];
  const itemByInstanceId = Object.fromEntries(sessionItems.map(row => [String(row.movement_instance_id || row.id || ""), row]));
  return (Array.isArray(session.organization_relations) ? session.organization_relations : [])
    .filter(relation => Array.isArray(relation.members) && relation.members.map(String).includes(itemId))
    .map(relation => {
      const members = relation.members.map(String);
      const enriched = { ...relation, member_order: members.indexOf(itemId) + 1, member_count: members.length, co_members: [] };
      enriched.co_members = members.filter(memberId => memberId !== itemId).map((memberId, index) => {
        const member = itemByInstanceId[memberId] || {};
        const definition = movementMap[String(member.movement_id || "")] || {};
        return {
          movement_id: member.movement_id || "",
          movement_name: member.display_name || definition.display_name || "",
          movement_instance_id: memberId,
          relation_order: members.indexOf(memberId) + 1,
          order_in_session: member.order_in_session || member.order || "",
          sets_lines: Array.isArray(member.sets) && member.sets.length ? [setSummary(member.sets)] : []
        };
      });
      return enriched;
    });
}
function buildBodyArea(partId, movements, history, sessions) {
  const theme = BODY_PARTS[partId];
  if (!theme) return null;
  const activeMovements = movements.filter(item => item.active !== false && groupMatches(item.muscle_group, theme.groups));
  const sessionById = Object.fromEntries((sessions || []).map(item => [String(item.id || item._id || ""), item]));
  const sessionsByDate = {};
  (sessions || []).forEach(item => {
    const date = String(item.Date || "").slice(0, 10);
    if (date) (sessionsByDate[date] || (sessionsByDate[date] = [])).push(item);
  });
  const movementMap = Object.fromEntries((movements || []).map(item => [String(item.movement_id || ""), item]));
  const historySession = item => {
    const byId = sessionById[String(item.training_session_id || "")];
    if (byId) return byId;
    const dateCandidates = sessionsByDate[String(item.date || "").slice(0, 10)] || [];
    const instanceId = String(item.movement_instance_id || item.id || "");
    return dateCandidates.find(session => instanceId && (session.movement_items || []).some(row => String(row.movement_instance_id || row.id || "") === instanceId))
      || (dateCandidates.length === 1 ? dateCandidates[0] : null);
  };
  const historyByMovement = {};
  history.forEach(item => {
    if (!historyByMovement[item.movement_id]) historyByMovement[item.movement_id] = [];
    historyByMovement[item.movement_id].push(item);
  });
  const movementCards = activeMovements.map(movement => {
    const records = (historyByMovement[movement.movement_id] || []).sort((a, b) => String(b.date).localeCompare(String(a.date)));
    const compact = records.map(item => {
      const session = historySession(item);
      const relations = relationContextForItem(session, item, movementMap);
      return { ...compactHistory(item), training_session_id: String(item.training_session_id || session?.id || ""), order: item.order_in_session || item.order || 0, organization_relations: relations.length ? relations : compactHistory(item).organization_relations };
    });
    const best = compact.reduce((current, item) => {
      if (!current || item.max_weight > current.max_weight || (item.max_weight === current.max_weight && item.volume > current.volume)) return item;
      return current;
    }, null);
    return {
      movement_id: movement.movement_id,
      display_name: movement.display_name,
      english_name: movement.english_name || "",
      muscle_group: movement.muscle_group || "",
      pinned: movement.pinned === true,
      focus_rank: Number(movement.focus_rank || 0),
      sessions: compact.length,
      latest: compact[0] || null,
      previous: compact[1] || null,
      best,
      recent: compact.slice(0, 3)
    };
  }).filter(item => item.sessions > 0).sort((a, b) => {
    const aFocused = Boolean(a.pinned) || a.focus_rank > 0, bFocused = Boolean(b.pinned) || b.focus_rank > 0;
    return Number(bFocused) - Number(aFocused)
      || (a.focus_rank > 0 ? a.focus_rank : Number.MAX_SAFE_INTEGER) - (b.focus_rank > 0 ? b.focus_rank : Number.MAX_SAFE_INTEGER)
      || b.sessions - a.sessions
      || String(a.display_name).localeCompare(String(b.display_name), "zh-CN");
  });
  const activeIds = new Set(activeMovements.map(item => String(item.movement_id || "")));
  const movementById = Object.fromEntries(activeMovements.map(item => [String(item.movement_id || ""), item]));
  const relatedBySession = {};
  history.forEach(item => {
    const movementId = String(item.movement_id || "");
    const date = String(item.date || "").slice(0, 10);
    if (!date || !activeIds.has(movementId)) return;
    const session = historySession(item);
    const key = String(item.training_session_id || session?.id || `date:${date}`);
    if (!relatedBySession[key]) relatedBySession[key] = [];
    const relations = relationContextForItem(session, item, movementMap);
    relatedBySession[key].push({ ...compactHistory(item), movement_id: movementId, display_name: movementById[movementId].display_name || "", training_session_id: key, organization_relations: relations.length ? relations : compactHistory(item).organization_relations });
  });
  const matchedSessions = Object.keys(relatedBySession).sort((a, b) => {
    const aDate = String(relatedBySession[a][0]?.date || ""), bDate = String(relatedBySession[b][0]?.date || "");
    return bDate.localeCompare(aDate) || b.localeCompare(a);
  }).map(key => {
    const related = relatedBySession[key].sort((a, b) => Number(a.order || 999) - Number(b.order || 999));
    const session = sessionById[key] || {};
    const date = String(related[0]?.date || session.Date || "").slice(0, 10);
    return {
      id: session.id || session._id || key.replace(/^date:/, ""),
      date,
      split: session.Split || "",
      notes: session.Notes || "",
      related_count: related.length,
      related_movements: related.map(item => item.display_name).filter(Boolean),
      movement_summary: related.map(item => `${item.display_name}${item.summary ? `：${item.summary}` : ""}`).join("；")
    };
  });
  return {
    id: partId,
    label: theme.label,
    labelEn: theme.labelEn,
    session_count: matchedSessions.length,
    movement_count: movementCards.length,
    latest_date: matchedSessions[0] ? matchedSessions[0].date : "",
    movements: movementCards,
    sessions: matchedSessions.slice(0, 12)
  };
}
async function bodyAreaPayload(partId) {
  const datasets = await Promise.all([
    all(COLLECTIONS.movements, 200),
    all(COLLECTIONS.history, 500),
    all(COLLECTIONS.training, 200)
  ]);
  return buildBodyArea(partId, datasets[0], datasets[1], datasets[2]);
}

function sessionMovementRows(session, movementMap) {
  return (Array.isArray(session && session.movement_items) ? session.movement_items : [])
    .filter(item => item && item.movement_id)
    .map((item, index) => {
      const movementId = String(item.movement_id);
      const definition = movementMap[movementId] || {};
      return {
        movement_id: movementId,
        display_name: item.display_name || definition.display_name || movementId,
        english_name: definition.english_name || "",
        muscle_group: definition.muscle_group || "",
        order: item.order_in_session || item.order || index + 1,
        sets: Array.isArray(item.sets) ? item.sets : [],
        notes: item.notes || "",
        date: String(session.Date || "").slice(0, 10),
        training_session_id: String(session.id || session._id || ""),
        organization_relations: relationContextForItem(session, item, movementMap)
      };
    });
}

function buildSessionMovementCards(sessionRows, movementMap, historyRows) {
  let selectedIds = new Set();
  const fallbackRows = [];
  sessionRows.forEach(session => sessionMovementRows(session, movementMap).forEach(item => {
    selectedIds = new Set([...selectedIds, item.movement_id]);
    fallbackRows.push(item);
  }));
  const recordsByMovement = {};
  (historyRows || []).forEach(item => {
    const movementId = String(item.movement_id || "");
    if (!selectedIds.has(movementId)) return;
    if (!recordsByMovement[movementId]) recordsByMovement[movementId] = [];
    recordsByMovement[movementId].push({ ...item, date: String(item.date || "").slice(0, 10) });
  });
  fallbackRows.forEach(item => {
    if (!recordsByMovement[item.movement_id]) recordsByMovement[item.movement_id] = [];
    if (!recordsByMovement[item.movement_id].some(row => String(row.training_session_id || "") === item.training_session_id)) {
      recordsByMovement[item.movement_id].push(item);
    }
  });
  return Array.from(selectedIds).map(movementId => {
    const definition = movementMap[movementId] || {};
    const records = recordsByMovement[movementId] || [];
    const compact = records.map(item => ({
      date: String(item.date || "").slice(0, 10),
      training_session_id: String(item.training_session_id || ""),
      order: item.order_in_session || item.order || 0,
      sets: Array.isArray(item.sets) ? item.sets : [],
      summary: item.summary || setSummary(item.sets),
      notes: item.notes || "",
      organization_relations: Array.isArray(item.organization_relations) ? item.organization_relations : []
    })).sort((a, b) => String(b.date).localeCompare(String(a.date)) || Number(b.order || 0) - Number(a.order || 0));
    if (!compact.length) return null;
    return {
      movement_id: movementId,
      display_name: definition.display_name || fallbackRows.find(item => item.movement_id === movementId)?.display_name || movementId,
      english_name: definition.english_name || "",
      muscle_group: definition.muscle_group || "",
      pinned: definition.pinned === true,
      focus_rank: Number(definition.focus_rank || 0),
      sessions: new Set(compact.map(item => item.training_session_id || item.date)).size,
      latest: compact[0],
      previous: compact[1] || null,
      best: compact[0],
      recent: compact.slice(0, 3)
    };
  }).filter(Boolean).sort((a, b) => Number(b.pinned) - Number(a.pinned) || Number(a.focus_rank || 9999) - Number(b.focus_rank || 9999) || b.sessions - a.sessions || String(a.display_name).localeCompare(String(b.display_name), "zh-CN"));
}

async function sessionThemeAreaPayload(themeId) {
  const trainingRows = await all(COLLECTIONS.training, 200);
  const organization = await trainingOrganizationPayload(trainingRows);
  const theme = (organization.session_themes || []).find(item => String(item.theme_id || "") === String(themeId || ""));
  if (!theme) return null;
  const sessions = trainingRows.filter(row => themeIds(row, organization).includes(String(themeId)));
  sessions.sort((a, b) => String(b.Date || "").localeCompare(String(a.Date || "")) || String(b.id || "").localeCompare(String(a.id || "")));
  const movements = await all(COLLECTIONS.movements, 200);
  const movementMap = Object.fromEntries(movements.map(item => [String(item.movement_id || ""), item]));
  const history = await all(COLLECTIONS.history, 500);
  const rows = sessions.map(session => {
    const items = sessionMovementRows(session, movementMap);
    return {
      id: session.id || session._id || String(session.Date || ""),
      date: String(session.Date || "").slice(0, 10),
      theme_names: themeNames(session, organization),
      title: session.session_theme_name || theme.display_name || "训练",
      split: session.Split || "",
      related_count: items.length,
      related_movements: items.map(item => item.display_name).filter(Boolean),
      movement_summary: session["Standardized Summary"] || items.map(item => `${item.display_name}${setSummary(item.sets) ? `：${setSummary(item.sets)}` : ""}`).join("；") || "暂无完整动作摘要",
      full_summary: session["Standardized Summary"] || items.map(item => `${item.display_name}${setSummary(item.sets) ? `：${setSummary(item.sets)}` : ""}`).join("；") || "暂无完整动作摘要",
      organization_relations: Array.isArray(session.organization_relations) ? session.organization_relations : [],
      notes: session.Notes || ""
    };
  });
  return {
    id: String(themeId),
    label: String(theme.display_name || themeId),
    labelEn: String(theme.display_name || themeId).toUpperCase(),
    theme,
    session_count: rows.length,
    movement_count: new Set(sessions.flatMap(session => sessionMovementRows(session, movementMap).map(item => item.movement_id))).size,
    latest_date: rows[0] ? rows[0].date : "",
    movements: buildSessionMovementCards(sessions, movementMap, history),
    sessions: rows.slice(0, 12)
  };
}

async function movementCatalogPayload() {
  const movements = await all(COLLECTIONS.movements, 200);
  return movements.filter(item => item.active !== false && item.movement_id && item.display_name).map(item => ({
    movement_id: String(item.movement_id),
    display_name: String(item.display_name),
    english_name: String(item.english_name || ""),
    aliases: Array.isArray(item.aliases) ? item.aliases.map(value => String(value)).filter(Boolean) : [],
    muscle_group: String(item.muscle_group || ""),
    body_parts: Object.keys(BODY_PARTS).filter(partId => groupMatches(item.muscle_group, BODY_PARTS[partId].groups))
  }));
}
function validIsoDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(String(value || ""));
}
function chunks(values, size) {
  const result = [];
  for (let index = 0; index < values.length; index += size) result.push(values.slice(index, index + size));
  return result;
}
async function allOnDate(name, field, date, maxItems = 500) {
  const rows = [];
  const pageSize = 100;
  for (let skip = 0; skip < maxItems; skip += pageSize) {
    const page = (await db.collection(name).where({ [field]: date }).skip(skip).limit(pageSize).get()).data;
    rows.push(...page);
    if (page.length < pageSize) break;
  }
  return rows.slice(0, maxItems);
}
async function getTrainingDayDetail(sessionId, entryDate, organization) {
  const trainingRows = await all(COLLECTIONS.training, 200);
  const requestedId = String(sessionId || "").trim();
  const date = String(entryDate || "").slice(0, 10);
  const session = trainingRows.find(item => requestedId && String(item.id || item._id || "") === requestedId)
    || trainingRows.find(item => !requestedId && String(item.Date || "").slice(0, 10) === date)
    || null;
  const sessionDate = String(session?.Date || date).slice(0, 10);
  const historyRows = await allOnDate(COLLECTIONS.history, "date", sessionDate);
  const history = requestedId
    ? historyRows.filter(item => !item.training_session_id || String(item.training_session_id) === String(session?.id || session?._id || requestedId))
    : historyRows;
  const movementIds = [...new Set([
    ...(session ? sessionMovementRows(session, {}).map(item => item.movement_id) : []),
    ...history.map(item => String(item.movement_id || ""))
  ].filter(Boolean))];
  const movementRows = movementIds.length ? (await Promise.all(chunks(movementIds, 20).map(ids => (
    db.collection(COLLECTIONS.movements).where({ movement_id: db.command.in(ids) }).get()
  )))).flatMap(item => item.data || []) : [];
  const movementById = Object.fromEntries(movementRows.map(item => [String(item.movement_id || ""), item]));
  const sessionItems = session ? sessionMovementRows(session, movementById) : [];
  const sourceItems = sessionItems.length ? sessionItems : history.map((item, index) => ({
    movement_id: String(item.movement_id || ""),
    display_name: movementById[String(item.movement_id || "")]?.display_name || String(item.movement_id || ""),
    english_name: movementById[String(item.movement_id || "")]?.english_name || "",
    muscle_group: movementById[String(item.movement_id || "")]?.muscle_group || "",
    order: item.order,
    sets: Array.isArray(item.sets) ? item.sets : [],
    notes: item.notes || "",
    date: sessionDate,
    training_session_id: String(session?.id || session?._id || "")
  }));
  const movements = sourceItems.map((item, index) => {
    const movementId = String(item.movement_id || "");
    const movement = movementById[movementId] || {};
    return {
      movement_id: movementId,
      movement_name: item.display_name || movement.display_name || movementId,
      english_name: item.english_name || movement.english_name || "",
      muscle_group: item.muscle_group || movement.muscle_group || "",
      order_in_session: item.order === undefined || item.order === null ? index + 1 : item.order,
      sets: Array.isArray(item.sets) ? item.sets : [],
      notes: item.notes || "",
      _source_index: index
    };
  }).sort((a, b) => {
    const aOrder = a.order_in_session === null ? Number.MAX_SAFE_INTEGER : Number(a.order_in_session);
    const bOrder = b.order_in_session === null ? Number.MAX_SAFE_INTEGER : Number(b.order_in_session);
    return aOrder - bOrder || a._source_index - b._source_index;
  }).map(({ _source_index, ...item }) => item);
  return {
    date: sessionDate,
    session: session ? {
      id: session.id || session._id || "",
      date: sessionDate,
      session_sequence: session.session_sequence || 1,
      session_theme_id: String(session.session_theme_id || ""),
      session_theme_ids: Array.isArray(session.session_theme_ids) ? session.session_theme_ids : [],
      theme_names: themeNames(session, organization),
      split: session.Split || "",
      summary: session["Standardized Summary"] || "",
      notes: session.Notes || ""
    } : null,
    movements
  };
}

async function readAction(event) {
  if (event.action === "whoami" || event.action === "getOpenId") {
    return result({
      openid: "",
      appid: "",
      env: process.env.TCB_ENV || process.env.SCF_NAMESPACE || "",
      web: true
    });
  }
  try {
    switch (event.action) {
      case "status": return result((await list(COLLECTIONS.meta, 1, 0, "generated_at"))[0] || null);
      case "latest": return result((await list(COLLECTIONS.latest, 1, 0, "date"))[0] || null);
      case "recent": return result(await list(COLLECTIONS.daily, Number(event.limit || 10), Number(event.skip || 0)));
      case "bodyRecords": return result(await list(COLLECTIONS.daily, Number(event.limit || 30), Number(event.skip || 0)));
      case "dietRecords": return result(await list(COLLECTIONS.diet, Number(event.limit || 30), Number(event.skip || 0)));
      case "dataModules": return result(await mobileDataModulePayload());
      case "trainingOrganization": {
        const rows = await all(COLLECTIONS.training, 200);
        return result(await trainingOrganizationPayload(rows));
      }
      case "trainingRecords": {
        const rows = await all(COLLECTIONS.training, 200);
        rows.sort((a, b) => String(b.Date || "").localeCompare(String(a.Date || "")));
        return result(decorateTrainingRows(rows, await trainingOrganizationPayload(rows)));
      }
      case "bodyAreas": {
        const datasets = await Promise.all([
          all(COLLECTIONS.movements, 200),
          all(COLLECTIONS.history, 500),
          all(COLLECTIONS.training, 200)
        ]);
        const areas = Object.keys(BODY_PARTS).map(partId => buildBodyArea(partId, datasets[0], datasets[1], datasets[2]));
        return result(areas.map(item => ({
          id: item.id,
          label: item.label,
          labelEn: item.labelEn,
          session_count: item.session_count,
          movement_count: item.movement_count,
          latest_date: item.latest_date
        })));
      }
      case "bodyArea": {
        const data = await bodyAreaPayload(String(event.part || ""));
        return data ? result(data) : failure("INVALID_BODY_PART", "未识别训练部位。");
      }
      case "sessionThemeArea": {
        const data = await sessionThemeAreaPayload(String(event.themeId || ""));
        return data ? result(data) : failure("INVALID_SESSION_THEME", "未识别训练主题。");
      }
      case "movementCatalog": return result(await movementCatalogPayload());
      case "trainingReference": {
        const where = event.split ? { Split: db.RegExp({ regexp: String(event.split), options: "i" }) } : {};
        const rows = (await db.collection(COLLECTIONS.training).where(where).orderBy("Date", "desc").limit(8).get()).data;
        return result(decorateTrainingRows(rows, await trainingOrganizationPayload(rows)));
      }
      case "search": {
        const query = String(event.query || "").trim();
        if (!query) return result([]);
        const rows = (await db.collection(COLLECTIONS.search).where({ text: db.RegExp({ regexp: query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), options: "i" }) }).limit(30).get()).data;
        const movements = await all(COLLECTIONS.movements, 100);
        const movementMap = Object.fromEntries(movements.map(item => [item.movement_id, item]));
        return result(rows.map(item => {
          if (item.type === "movement" && movementMap[item.id]) {
            const movement = movementMap[item.id];
            return {
              type: item.type,
              id: item.id,
              title: movement.display_name,
              subtitle: [movement.english_name, movement.muscle_group].filter(Boolean).join(" · "),
              preview: `${Array.isArray(movement.aliases) ? movement.aliases.length : 0} 个别名`
            };
          }
          const labels = { daily: "身体记录", diet: "饮食记录", training: "训练记录" };
          return {
            type: item.type,
            id: item.id,
            date: String(item.date || "").slice(0, 10),
            title: `${labels[item.type] || "档案记录"} · ${String(item.date || "").slice(0, 10)}`,
            subtitle: labels[item.type] || "档案记录",
            preview: String(item.text || "").replace(/\s+/g, " ").slice(0, 92)
          };
        }));
      }
      case "movementHistory": return result((await db.collection(COLLECTIONS.history).where({ movement_id: String(event.movementId || "") }).orderBy("date", "desc").limit(Math.min(Number(event.limit || 5), 20)).get()).data);
      case "movement": return result((await db.collection(COLLECTIONS.movements).where({ movement_id: String(event.movementId || "") }).limit(1).get()).data[0] || null);
      case "trainingDayDetail": {
        const date = String(event.date || "").slice(0, 10);
        const sessionId = String(event.sessionId || "").trim();
        if (!sessionId && !validIsoDate(date)) return failure("INVALID_DATE", "日期格式应为 YYYY-MM-DD。");
        const rows = await all(COLLECTIONS.training, 200);
        return result(await getTrainingDayDetail(sessionId, date, await trainingOrganizationPayload(rows)));
      }
      case "recordDetail": {
        const date = String(event.date || "").slice(0, 10);
        const fetch = name => db.collection(name).where({ Date: date }).get();
        const [body, diet, training] = await Promise.all([fetch(COLLECTIONS.daily), fetch(COLLECTIONS.diet), fetch(COLLECTIONS.training)]);
        return result({ date, body: body.data, diet: diet.data, training: decorateTrainingRows(training.data, await trainingOrganizationPayload(training.data)) });
      }
      case "quality": return result(await list(COLLECTIONS.quality, 50, 0, "date"));
      default: return failure("UNKNOWN_ACTION", "未知只读操作。");
    }
  } catch (_error) {
    return failure("QUERY_FAILED", "云端查询失败，请稍后重试。");
  }
}

function requestHeaders(event) {
  return event && event.headers && typeof event.headers === "object" ? event.headers : {};
}

function headerValue(event, name) {
  const expected = String(name).toLowerCase();
  const entry = Object.entries(requestHeaders(event)).find(([key]) => String(key).toLowerCase() === expected);
  return entry ? String(entry[1] || "") : "";
}

function hasBearerToken(event) {
  return /^Bearer\s+\S+/i.test(headerValue(event, "authorization"));
}

function authRequired() {
  return String(process.env.FITNESS_LEDGER_WEB_AUTH_REQUIRED || "true").toLowerCase() !== "false";
}

function allowedOrigin(event) {
  const origin = headerValue(event, "origin");
  if (!origin) return "";
  const allowed = String(process.env.FITNESS_LEDGER_WEB_ORIGINS || "")
    .split(",").map(value => value.trim()).filter(Boolean);
  return allowed.includes(origin) ? origin : "";
}

function httpResponse(event, statusCode, payload) {
  const origin = allowedOrigin(event);
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Vary": "Origin",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Accept, Content-Type, Authorization"
  };
  if (origin) headers["Access-Control-Allow-Origin"] = origin;
  return { statusCode, headers, body: JSON.stringify(payload) };
}

function requestData(event) {
  let body = {};
  if (typeof event.body === "string" && event.body.trim()) {
    try { body = JSON.parse(event.body); } catch (_) { body = {}; }
  } else if (event.body && typeof event.body === "object") {
    body = event.body;
  }
  return { ...body, ...(event.queryStringParameters || {}), action: event.queryStringParameters?.action || body.action || event.action || "" };
}

exports.main = async (event = {}) => {
  if (String(event.httpMethod || "").toUpperCase() === "OPTIONS") {
    return httpResponse(event, allowedOrigin(event) ? 204 : 403, {});
  }
  if (authRequired() && !hasBearerToken(event)) {
    return httpResponse(event, 401, failure("UNAUTHORIZED", "请先完成网页端登录。"));
  }
  const request = requestData(event);
  try {
    const payload = await readAction(request);
    return httpResponse(event, payload.ok ? 200 : 400, payload);
  } catch (_) {
    return httpResponse(event, 500, failure("QUERY_FAILED", "云端查询失败，请稍后重试。"));
  }
};
