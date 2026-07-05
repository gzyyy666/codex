const ledger = require("../../services/ledger");
Page({
  data: { loading: true, error: "", status: null, openid: "" },
  async onShow() {
    const [status, identity] = await Promise.all([ledger.call("status"), ledger.call("whoami")]);
    this.setData({ loading: false, status: status.ok ? status.data : null, openid: identity.ok ? identity.data.openid : "", error: status.ok ? "" : status.message });
  }
});
