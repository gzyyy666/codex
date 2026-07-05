const ledger = require("../../services/ledger");
Page({
  data: { loading: true, error: "", status: null, identity: null },
  async onShow() {
    const [status, identity] = await Promise.all([ledger.call("status"), ledger.call("whoami")]);
    this.setData({ loading: false, status: status.ok ? status.data : null, identity: identity.ok ? identity.data : null, error: status.ok ? "" : status.message });
  }
});
