const ledger = require("../../services/ledger");
Page({
  data: { loading: true, error: "", movement: null, history: [] },
  async onLoad(options) {
    const id = options.id || "";
    const [movement, history] = await Promise.all([ledger.call("movement", { movementId: id }), ledger.call("movementHistory", { movementId: id, limit: 5 })]);
    this.setData({ loading: false, movement: movement.ok ? movement.data : null, history: history.ok ? history.data : [], error: !movement.ok ? movement.message : (!history.ok ? history.message : "") });
  }
});
