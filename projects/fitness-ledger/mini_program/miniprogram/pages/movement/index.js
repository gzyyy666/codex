const ledger = require("../../services/ledger");

function compact(item) {
  const metrics = item.metrics || {};
  return {
    ...item,
    maxWeight: Number(metrics.max_weight || 0),
    totalReps: Number(metrics.total_reps || 0),
    volume: Number(metrics.volume || 0),
    sessionOrder: Number(item.order || item.exerciseIndex || item.sequence || item.position || 0)
  };
}

Page({
  data: { loading: true, error: "", movement: null, history: [], latest: null, previous: null, best: null, showAliases: false, part: "" },
  async onLoad(options) {
    const id = options.id || "";
    const part = options.part || "";
    const [movement, history] = await Promise.all([ledger.call("movement", { movementId: id }), ledger.call("movementHistory", { movementId: id, limit: 10 })]);
    const records = history.ok ? history.data.map(compact) : [];
    const best = records.reduce((current, item) => !current || item.maxWeight > current.maxWeight || (item.maxWeight === current.maxWeight && item.volume > current.volume) ? item : current, null);
    this.setData({
      loading: false,
      movement: movement.ok ? movement.data : null,
      history: records,
      latest: records[0] || null,
      previous: records[1] || null,
      best,
      error: !movement.ok ? movement.message : (!history.ok ? history.message : ""), part
    });
  },
  toggleAliases() { this.setData({ showAliases: !this.data.showAliases }); },
  openTrainingSession(event) { wx.navigateTo({ url: `/pages/record/index?mode=training&date=${event.currentTarget.dataset.date}&part=${this.data.part}` }); }
});
