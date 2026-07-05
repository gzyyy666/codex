const ledger = require("../../services/ledger");
Page({
  data: { loading: true, error: "", item: null },
  async onShow() {
    const response = await ledger.call("latest");
    this.setData({ loading: false, item: response.ok ? response.data : null, error: response.ok ? "" : response.message });
  },
  openRecord() { if (this.data.item) wx.navigateTo({ url: `/pages/record/index?date=${this.data.item.date}` }); }
});
