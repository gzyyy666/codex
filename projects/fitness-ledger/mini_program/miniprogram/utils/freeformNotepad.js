const STORAGE_KEY = "fitness-ledger:freeform-notepad:v2:current-training";

function load() {
  try { return String(wx.getStorageSync(STORAGE_KEY) || ""); } catch (_) { return ""; }
}

function save(text) { wx.setStorageSync(STORAGE_KEY, String(text || "")); }
function clear() { wx.removeStorageSync(STORAGE_KEY); }

module.exports = { STORAGE_KEY, load, save, clear };
