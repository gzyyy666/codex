const STORAGE_PREFIX = "fitness-ledger:freeform-notepad:v1:";
const LEGACY_PREFIX = "fitness-ledger:training-draft:";
const MIGRATION_PREFIX = "fitness-ledger:freeform-notepad:migrated-v1:";

function key(part) { return `${STORAGE_PREFIX}${part}`; }
function migrationKey(part) { return `${MIGRATION_PREFIX}${part}`; }
function load(part) { try { return String(wx.getStorageSync(key(part)) || ""); } catch (_) { return ""; } }
function save(part, text) { wx.setStorageSync(key(part), String(text || "")); }
function clear(part) { wx.removeStorageSync(key(part)); }
function legacyText(draft) {
  if (!draft || typeof draft !== "object") return "";
  const lines = [];
  if (draft.date) lines.push(String(draft.date));
  if (draft.theme) lines.push(String(draft.theme));
  (Array.isArray(draft.exercises) ? draft.exercises : []).forEach(item => {
    const fields = [item.name, item.weight && `${item.weight} kg`, item.reps && `${item.reps} reps`, item.sets && `${item.sets} sets`].filter(Boolean);
    if (fields.length) lines.push(fields.join(" · "));
    if (item.notes) lines.push(String(item.notes));
  });
  return lines.join("\n").trim();
}
function matchesPart(theme, part) {
  const value = String(theme || "").toLowerCase();
  const words = { shoulders: ["肩", "shoulder"], chest: ["胸", "chest"], back: ["背", "back"], legs: ["腿", "leg"], arms: ["手臂", "臂", "arm"] };
  return (words[part] || []).some(word => value.includes(word));
}
function migrateLegacy(part, existing) {
  if (existing) { wx.setStorageSync(migrationKey(part), true); return existing; }
  if (wx.getStorageSync(migrationKey(part))) return existing;
  let keys = [];
  try { keys = wx.getStorageInfoSync().keys || []; } catch (_) { return existing; }
  const notes = keys.filter(item => item.indexOf(LEGACY_PREFIX) === 0).map(item => {
    try { return wx.getStorageSync(item); } catch (_) { return null; }
  }).filter(draft => matchesPart(draft && draft.theme, part)).map(legacyText).filter(Boolean);
  wx.setStorageSync(migrationKey(part), true);
  if (!notes.length) return existing;
  const migrated = notes.join("\n\n");
  save(part, migrated);
  return migrated;
}
module.exports = { load, save, clear, migrateLegacy, STORAGE_PREFIX };
