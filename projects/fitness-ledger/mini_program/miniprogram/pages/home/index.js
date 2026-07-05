const ledger = require("../../services/ledger");
Page({
  data: { loading: true, error: "", latest: null },
  async onShow() {
    this.setData({ loading: true, error: "" });
    const response = await ledger.call("latest");
    this.setData({ loading: false, latest: response.ok ? response.data : null, error: response.ok ? "" : response.message });
  },
  today() { wx.switchTab({ url: "/pages/today/index" }); },
  reference() { wx.navigateTo({ url: "/pages/reference/index" }); },
  search() { wx.switchTab({ url: "/pages/search/index" }); }
});
