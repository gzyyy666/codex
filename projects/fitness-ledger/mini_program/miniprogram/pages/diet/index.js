const ledger = require("../../services/ledger");

Page({
  data: { loading: true, error: "", records: [] },
  async onLoad() {
    const response = await ledger.call("dietRecords", { limit: 30 });
    this.setData({ loading: false, records: response.ok ? response.data : [], error: response.ok ? "" : response.message });
  },
  open(event) { wx.navigateTo({ url: `/pages/record/index?date=${String(event.currentTarget.dataset.date || "").slice(0, 10)}` }); }
});
