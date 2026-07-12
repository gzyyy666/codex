const STORAGE_PREFIX = "fitness-ledger:training-draft:";
function localDate() { const date = new Date(); return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10); }
function blankExercise(index) { return { id: `${Date.now()}-${index}`, name: "", weight: "", reps: "", sets: "", notes: "" }; }
function blankDraft(date = localDate()) { return { version: 1, date, theme: "", exercises: [blankExercise(0)], updatedAt: "" }; }
function key(date) { return `${STORAGE_PREFIX}${date}`; }
function normalize(draft, date) { const source = draft && typeof draft === "object" ? draft : {}; const rows = Array.isArray(source.exercises) && source.exercises.length ? source.exercises : [blankExercise(0)]; return { version: 1, date, theme: String(source.theme || ""), exercises: rows.map((item, index) => ({ ...blankExercise(index), ...item, id: item.id || `${Date.now()}-${index}` })), updatedAt: String(source.updatedAt || "") }; }
function load(date = localDate()) { try { return normalize(wx.getStorageSync(key(date)), date); } catch (_) { return blankDraft(date); } }
function save(draft) { const next = normalize(draft, draft && draft.date || localDate()); next.updatedAt = new Date().toISOString(); wx.setStorageSync(key(next.date), next); return next; }
function clear(date = localDate()) { wx.removeStorageSync(key(date)); }
module.exports = { blankExercise, blankDraft, load, save, clear };
