const cloud = require("wx-server-sdk");
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();

const COLLECTIONS = {
  meta: "fl_meta", latest: "fl_latest_summary", daily: "fl_daily_records",
  diet: "fl_diet_records", training: "fl_training_sessions", movements: "fl_movements",
  history: "fl_movement_history", search: "fl_search_index", raw: "fl_raw_entries",
  quality: "fl_data_quality_issues"
};

const BODY_PARTS = {
  shoulders: { label: "肩", labelEn: "SHOULDERS", groups: ["Shoulder", "Shoulders", "肩部"], split: ["肩", "shoulder"] },
  chest: { label: "胸", labelEn: "CHEST", groups: ["Chest", "胸部"], split: ["胸", "chest"] },
  back: { label: "背", labelEn: "BACK", groups: ["Back", "背部"], split: ["背", "back"] },
  legs: { label: "腿", labelEn: "LEGS", groups: ["Leg", "Legs", "Lower Body", "腿部", "臀部"], split: ["腿", "臀", "leg", "lower"] },
  arms: { label: "手臂", labelEn: "ARMS", groups: ["Arm", "Arms", "Biceps", "Triceps", "手臂"], split: ["手臂", "二头", "三头", "arm", "biceps", "triceps"] }
};

function result(data) { return { ok: true, data }; }
function failure(code, message) { return { ok: false, code, message }; }
function allowed(openid) {
  const values = String(process.env.FITNESS_LEDGER_ALLOWED_OPENIDS || "").split(",").map(v => v.trim()).filter(Boolean);
  return values.includes(openid);
}
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
function normalized(value) { return String(value || "").trim().toLowerCase(); }
function matchesAny(value, terms) {
  const source = normalized(value);
  return terms.some(term => source.includes(normalized(term)));
}
function groupMatches(value, groups) {
  const source = normalized(value);
  return groups.some(group => source === normalized(group) || source.includes(normalized(group)));
}
function setSummary(sets) {
  return (Array.isArray(sets) ? sets : []).map(item => {
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
    volume: Number(metrics.volume || 0)
  };
}
function buildBodyArea(partId, movements, history, sessions) {
  const theme = BODY_PARTS[partId];
  if (!theme) return null;
  const activeMovements = movements.filter(item => item.active !== false && groupMatches(item.muscle_group, theme.groups));
  const historyByMovement = {};
  history.forEach(item => {
    if (!historyByMovement[item.movement_id]) historyByMovement[item.movement_id] = [];
    historyByMovement[item.movement_id].push(item);
  });
  const movementCards = activeMovements.map(movement => {
    const records = (historyByMovement[movement.movement_id] || []).sort((a, b) => String(b.date).localeCompare(String(a.date)));
    const compact = records.map(compactHistory);
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
  }).filter(item => item.sessions > 0).sort((a, b) => Number(b.pinned) - Number(a.pinned) || a.focus_rank - b.focus_rank || b.sessions - a.sessions || String(a.display_name).localeCompare(String(b.display_name), "zh-CN"));
  const activeIds = new Set(activeMovements.map(item => String(item.movement_id || "")));
  const movementById = Object.fromEntries(activeMovements.map(item => [String(item.movement_id || ""), item]));
  const relatedByDate = {};
  history.forEach(item => {
    const movementId = String(item.movement_id || "");
    const date = String(item.date || "").slice(0, 10);
    if (!date || !activeIds.has(movementId)) return;
    if (!relatedByDate[date]) relatedByDate[date] = [];
    relatedByDate[date].push({ ...compactHistory(item), movement_id: movementId, display_name: movementById[movementId].display_name || "" });
  });
  const sessionsByDate = {};
  sessions.forEach(item => { const date = String(item.Date || "").slice(0, 10); if (date && !sessionsByDate[date]) sessionsByDate[date] = item; });
  const matchedSessions = Object.keys(relatedByDate).sort((a, b) => b.localeCompare(a)).map(date => {
    const session = sessionsByDate[date] || {};
    const related = relatedByDate[date].sort((a, b) => Number(a.order || 999) - Number(b.order || 999));
    return {
      id: session.id || session._id || date,
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
    latest_date: matchedSessions[0] ? matchedSessions[0].Date : "",
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

exports.main = async (event) => {
  const wxContext = cloud.getWXContext();
  const openid = wxContext.OPENID;
  if (event.action === "whoami" || event.action === "getOpenId") {
    return result({
      openid,
      appid: wxContext.APPID || "",
      env: process.env.TCB_ENV || process.env.SCF_NAMESPACE || ""
    });
  }
  if (!allowed(openid)) return failure("FORBIDDEN", "当前微信账号未加入只读访问名单。");
  try {
    switch (event.action) {
      case "status": return result((await list(COLLECTIONS.meta, 1, 0, "generated_at"))[0] || null);
      case "latest": return result((await list(COLLECTIONS.latest, 1, 0, "date"))[0] || null);
      case "recent": return result(await list(COLLECTIONS.daily, Number(event.limit || 10), Number(event.skip || 0)));
      case "bodyRecords": return result(await list(COLLECTIONS.daily, Number(event.limit || 30), Number(event.skip || 0)));
      case "dietRecords": return result(await list(COLLECTIONS.diet, Number(event.limit || 30), Number(event.skip || 0)));
      case "trainingRecords": {
        const rows = await all(COLLECTIONS.training, 200);
        rows.sort((a, b) => String(b.Date || "").localeCompare(String(a.Date || "")));
        return result(rows);
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
      case "trainingReference": {
        const where = event.split ? { Split: db.RegExp({ regexp: String(event.split), options: "i" }) } : {};
        return result((await db.collection(COLLECTIONS.training).where(where).orderBy("Date", "desc").limit(8).get()).data);
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
      case "recordDetail": {
        const date = String(event.date || "").slice(0, 10);
        const fetch = name => db.collection(name).where({ Date: date }).get();
        const [body, diet, training] = await Promise.all([fetch(COLLECTIONS.daily), fetch(COLLECTIONS.diet), fetch(COLLECTIONS.training)]);
        return result({ date, body: body.data, diet: diet.data, training: training.data });
      }
      case "quality": return result(await list(COLLECTIONS.quality, 50, 0, "date"));
      default: return failure("UNKNOWN_ACTION", "未知只读操作。");
    }
  } catch (_error) {
    return failure("QUERY_FAILED", "云端查询失败，请稍后重试。");
  }
};
