const ledger = require("../../services/ledger");
Page({
  data: { split: "", loading: false, error: "", records: [] },
  onInput(event) { this.setData({ split: event.detail.value }); },
  async load() {
    this.setData({ loading: true, error: "" });
    const response = await ledger.call("trainingReference", { split: this.data.split });
    this.setData({ loading: false, records: response.ok ? response.data : [], error: response.ok ? "" : response.message });
  }
});
