const ledger = require("../../services/ledger");
const { safeBuildDataModuleReadModel, modulesForDate } = require("../../utils/dataModuleContract");

function filtered(records, query, order) {
  const needle = String(query || "").trim().replace(/[./]/g, "-");
  return records.filter(item => !needle || String(item.Date || "").includes(needle))
    .sort((a, b) => (order === "oldest" ? 1 : -1) * String(a.Date || "").localeCompare(String(b.Date || "")));
}
function decorate(records, moduleModel) {
  return records.map(item => ({ ...item, dataModules: modulesForDate(moduleModel, "body", item.Date) }));
}

Page({
  data: { loading: true, error: "", sourceRecords: [], records: [], query: "", order: "newest" },
  async onLoad() {
    const [response, moduleResponse] = await Promise.all([
      ledger.call("bodyRecords", { limit: 30 }),
      ledger.call("dataModules")
    ]);
    const moduleModel = moduleResponse.ok ? safeBuildDataModuleReadModel(moduleResponse.data) : { modules: [] };
    const sourceRecords = response.ok ? decorate(response.data, moduleModel) : [];
    this.setData({ loading: false, sourceRecords, records: filtered(sourceRecords, "", "newest"), error: response.ok ? "" : response.message });
  },
  onInput(event) { const query = event.detail.value; this.setData({ query, records: filtered(this.data.sourceRecords, query, this.data.order) }); },
  toggleOrder() { const order = this.data.order === "newest" ? "oldest" : "newest"; this.setData({ order, records: filtered(this.data.sourceRecords, this.data.query, order) }); },
  open(event) { wx.navigateTo({ url: `/pages/record/index?date=${String(event.currentTarget.dataset.date || "").slice(0, 10)}` }); }
});
