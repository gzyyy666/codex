const ledger = require("../../services/ledger");

function displaySets(movements) {
  return (movements || []).map((movement, movementIndex) => ({
    ...movement,
    displayOrder: movement.order === undefined || movement.order === null ? movementIndex + 1 : movement.order,
    sets: (Array.isArray(movement.sets) ? movement.sets : []).map((set, setIndex) => {
      const rawWeight = set.weight_text || set.weightText || set.weight;
      const numericWeight = rawWeight !== undefined && rawWeight !== null && /^\s*\d+(?:\.\d+)?\s*$/.test(String(rawWeight));
      return {
        ...set,
        id: set.id || set._id || `${movement.movement_id || movementIndex}-${setIndex}`,
        weightLabel: rawWeight === undefined || rawWeight === null || rawWeight === "" || Number(rawWeight) === 0 ? "" : (numericWeight ? `${Number(rawWeight)} kg` : String(rawWeight)),
        repsLabel: set.reps === undefined || set.reps === null || set.reps === "" ? "" : `${set.reps} 次`,
        setLabel: set.sets === undefined || set.sets === null || set.sets === "" ? "" : `${set.sets} 组`
      };
    })
  }));
}

Page({
  data: { loading: true, error: "", date: "", detail: null, session: null, movements: [], mode: "archive", showBody: false, showDiet: false, showTraining: false },
  async onLoad(options) {
    const date = String(options.date || "").slice(0, 10);
    const mode = options.mode === "training" ? "training" : "archive";
    if (mode === "training") {
      const response = await ledger.call("trainingDayDetail", { date });
      const data = response.ok ? response.data : null;
      this.setData({ loading: false, mode, date, detail: null, session: data ? data.session : null, movements: data ? displaySets(data.movements) : [], error: response.ok ? "" : response.message });
      return;
    }
    const response = await ledger.call("recordDetail", { date });
    this.setData({ loading: false, mode, date, detail: response.ok ? response.data : null, session: null, movements: [], error: response.ok ? "" : response.message });
  },
  toggle(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [key]: !this.data[key] });
  },
  openMovement(event) {
    const id = event.currentTarget.dataset.id;
    if (id) wx.navigateTo({ url: `/pages/movement/index?id=${encodeURIComponent(id)}` });
  }
});
