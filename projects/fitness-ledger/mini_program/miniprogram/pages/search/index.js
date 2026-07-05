const ledger = require("../../services/ledger");
Page({
  data: { query: "", loading: false, error: "", results: [] },
  onInput(event) { this.setData({ query: event.detail.value }); },
  async search() {
    this.setData({ loading: true, error: "" });
    const response = await ledger.call("search", { query: this.data.query });
    this.setData({ loading: false, results: response.ok ? response.data : [], error: response.ok ? "" : response.message });
  },
  open(event) {
    const item = this.data.results[event.currentTarget.dataset.index];
    if (item.type === "movement") wx.navigateTo({ url: `/pages/movement/index?id=${item.id}` });
    else if (item.date) wx.navigateTo({ url: `/pages/record/index?date=${item.date}` });
  }
});
