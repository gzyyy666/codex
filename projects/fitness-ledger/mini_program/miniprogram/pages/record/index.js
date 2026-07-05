const ledger = require("../../services/ledger");
Page({
  data: { loading: true, error: "", detail: null },
  async onLoad(options) {
    const response = await ledger.call("recordDetail", { date: options.date || "" });
    this.setData({ loading: false, detail: response.ok ? response.data : null, error: response.ok ? "" : response.message });
  }
});
