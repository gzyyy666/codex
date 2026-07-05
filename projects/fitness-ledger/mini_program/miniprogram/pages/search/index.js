const ledger = require("../../services/ledger");

function normalizeResult(item) {
  if (item.title) return item;
  if (item.type === "movement") {
    const parts = String(item.text || "").split(/\s+/).filter(Boolean);
    return { ...item, title: parts[0] || "动作", subtitle: "动作档案", preview: parts.slice(1, 8).join(" ") };
  }
  const labels = { daily: "身体记录", diet: "饮食记录", training: "训练记录" };
  return {
    ...item,
    title: `${labels[item.type] || "档案记录"} · ${String(item.date || "").slice(0, 10)}`,
    subtitle: labels[item.type] || "档案记录",
    preview: String(item.text || "").replace(/\s+/g, " ").slice(0, 92)
  };
}
Page({
  data: { query: "", loading: false, error: "", results: [] },
  onInput(event) { this.setData({ query: event.detail.value }); },
  async search() {
    this.setData({ loading: true, error: "" });
    const response = await ledger.call("search", { query: this.data.query });
    this.setData({ loading: false, results: response.ok ? response.data.map(normalizeResult) : [], error: response.ok ? "" : response.message });
  },
  open(event) {
    const item = this.data.results[event.currentTarget.dataset.index];
    if (item.type === "movement") wx.navigateTo({ url: `/pages/movement/index?id=${item.id}` });
    else if (item.date) wx.navigateTo({ url: `/pages/record/index?date=${item.date}` });
  }
});
