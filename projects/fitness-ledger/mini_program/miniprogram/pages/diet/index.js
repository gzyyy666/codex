const ledger = require("../../services/ledger");

function filtered(records, query, order) {
  const needle = String(query || "").trim().replace(/[./]/g, "-");
  return records.filter(item => !needle || String(item.Date || "").includes(needle))
    .sort((a, b) => (order === "oldest" ? 1 : -1) * String(a.Date || "").localeCompare(String(b.Date || "")));
}

Page({
  data: { loading: true, error: "", sourceRecords: [], records: [], query: "", order: "newest" },
  async onLoad() {
    const response = await ledger.call("dietRecords", { limit: 30 });
    const sourceRecords = response.ok ? response.data : [];
    this.setData({ loading: false, sourceRecords, records: filtered(sourceRecords, "", "newest"), error: response.ok ? "" : response.message });
  },
  onInput(event) { const query = event.detail.value; this.setData({ query, records: filtered(this.data.sourceRecords, query, this.data.order) }); },
  toggleOrder() { const order = this.data.order === "newest" ? "oldest" : "newest"; this.setData({ order, records: filtered(this.data.sourceRecords, this.data.query, order) }); },
  open(event) { wx.navigateTo({ url: `/pages/record/index?date=${String(event.currentTarget.dataset.date || "").slice(0, 10)}` }); }
});
