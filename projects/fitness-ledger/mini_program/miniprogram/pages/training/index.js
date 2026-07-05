const ledger = require("../../services/ledger");

function normalizedDate(value) {
  const source = String(value || "").trim().replace(/[./]/g, "-");
  const short = source.match(/^(\d{1,2})-(\d{1,2})$/);
  if (short) return `${String(short[1]).padStart(2, "0")}-${String(short[2]).padStart(2, "0")}`;
  return source;
}

function filterRecords(records, query, order) {
  const needle = normalizedDate(query);
  return records
    .filter(item => !needle || String(item.Date || "").includes(needle))
    .sort((a, b) => (order === "oldest" ? 1 : -1) * String(a.Date || "").localeCompare(String(b.Date || "")));
}

Page({
  data: { loading: true, error: "", sourceRecords: [], records: [], query: "", order: "newest" },
  async onLoad() {
    const response = await ledger.call("trainingRecords");
    const sourceRecords = response.ok ? response.data : [];
    this.setData({
      loading: false,
      sourceRecords,
      records: filterRecords(sourceRecords, "", "newest"),
      error: response.ok ? "" : response.message
    });
  },
  onInput(event) {
    const query = event.detail.value;
    this.setData({ query, records: filterRecords(this.data.sourceRecords, query, this.data.order) });
  },
  toggleOrder() {
    const order = this.data.order === "newest" ? "oldest" : "newest";
    this.setData({ order, records: filterRecords(this.data.sourceRecords, this.data.query, order) });
  },
  open(event) {
    wx.navigateTo({ url: `/pages/record/index?date=${String(event.currentTarget.dataset.date || "").slice(0, 10)}` });
  }
});
