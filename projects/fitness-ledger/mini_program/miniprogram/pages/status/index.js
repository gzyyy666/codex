const ledger = require("../../services/ledger");
const BUILD_VERSION = "v2026.08.01-live-save-03";
Page({
  data: { loading: true, error: "", status: null, identity: null, buildVersion: BUILD_VERSION },
  async onShow() {
    getApp().globalData.resetReferenceNotepad = true;
    const [status, identity] = await Promise.all([ledger.call("status"), ledger.call("whoami")]);
    this.setData({ loading: false, status: status.ok ? status.data : null, identity: identity.ok ? identity.data : null, error: status.ok ? "" : status.message });
  },
  openBody() { wx.navigateTo({ url: "/pages/body/index" }); },
  openDiet() { wx.navigateTo({ url: "/pages/diet/index" }); }
});
