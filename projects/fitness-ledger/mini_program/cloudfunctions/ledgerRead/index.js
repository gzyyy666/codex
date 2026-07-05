const cloud = require("wx-server-sdk");
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV });
const db = cloud.database();

const COLLECTIONS = {
  meta: "fl_meta", latest: "fl_latest_summary", daily: "fl_daily_records",
  diet: "fl_diet_records", training: "fl_training_sessions", movements: "fl_movements",
  history: "fl_movement_history", search: "fl_search_index", raw: "fl_raw_entries",
  quality: "fl_data_quality_issues"
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

exports.main = async (event) => {
  const openid = cloud.getWXContext().OPENID;
  if (event.action === "whoami") return result({ openid });
  if (!allowed(openid)) return failure("FORBIDDEN", "当前微信账号未加入只读访问名单。");
  try {
    switch (event.action) {
      case "status": return result((await list(COLLECTIONS.meta, 1, 0, "generated_at"))[0] || null);
      case "latest": return result((await list(COLLECTIONS.latest, 1, 0, "date"))[0] || null);
      case "recent": return result(await list(COLLECTIONS.daily, Number(event.limit || 10), Number(event.skip || 0)));
      case "trainingReference": {
        const where = event.split ? { Split: db.RegExp({ regexp: String(event.split), options: "i" }) } : {};
        return result((await db.collection(COLLECTIONS.training).where(where).orderBy("Date", "desc").limit(8).get()).data);
      }
      case "search": {
        const query = String(event.query || "").trim();
        if (!query) return result([]);
        return result((await db.collection(COLLECTIONS.search).where({ text: db.RegExp({ regexp: query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), options: "i" }) }).limit(30).get()).data);
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
