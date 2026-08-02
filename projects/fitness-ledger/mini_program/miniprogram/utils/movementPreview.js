const ledger = require("../services/ledger");

function formatSet(item) {
  const rawWeight = item.weight_text || item.weightText || item.weight;
  const numericWeight = rawWeight !== undefined && rawWeight !== null && /^\s*\d+(?:\.\d+)?\s*$/.test(String(rawWeight));
  return {
    weightLabel: rawWeight === undefined || rawWeight === null || rawWeight === "" || Number(rawWeight) === 0
      ? ""
      : (numericWeight ? `${Number(rawWeight)} kg` : String(rawWeight)),
    repsLabel: item.reps === undefined || item.reps === null || item.reps === "" ? "" : `${item.reps} 次`,
    setsLabel: item.sets === undefined || item.sets === null || item.sets === "" ? "" : `${item.sets} 组`
  };
}

function formatHistory(item) {
  return {
    date: String(item.date || "").slice(0, 10),
    order: item.order || item.exerciseIndex || item.sequence || item.position || 0,
    sets: Array.isArray(item.sets) ? item.sets.map(formatSet) : [],
    notes: String(item.notes || "")
  };
}
function summarize(record) {
  return (record && record.sets || []).map(set => [set.weightLabel, set.repsLabel, set.setsLabel].filter(Boolean).join(" · ")).filter(Boolean).join("  ");
}

async function load(movementId) {
  const id = String(movementId || "");
  if (!id) return { movement: null, history: [], error: "" };
  const [movement, history] = await Promise.all([
    ledger.call("movement", { movementId: id }),
    ledger.call("movementHistory", { movementId: id, limit: 20 })
  ]);
  return {
    movement: movement.ok ? movement.data : null,
    history: history.ok ? history.data.map(formatHistory) : [],
    error: movement.ok && history.ok ? "" : (movement.message || history.message || "动作历史暂不可用。")
  };
}

module.exports = { load, summarize };
