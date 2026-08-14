const ledger = require("../../services/ledger");
const { safeBuildDataModuleReadModel, modulesForDate } = require("../../utils/dataModuleContract");

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
function decorateDetail(detail, moduleModel) {
  if (!detail) return detail;
  return {
    ...detail,
    body: (detail.body || []).map(item => ({ ...item, dataModules: modulesForDate(moduleModel, "body", item.Date || detail.date) })),
    diet: (detail.diet || []).map(item => ({ ...item, dataModules: modulesForDate(moduleModel, "diet", item.Date || detail.date) })),
    training: (detail.training || []).map(item => ({ ...item, dataModules: modulesForDate(moduleModel, "training", item.Date || detail.date) }))
  };
}

Page({
  data: { loading: true, error: "", date: "", detail: null, session: null, sessionModules: [], movements: [], mode: "archive", showBody: false, showDiet: false, showTraining: false, part: "" },
  async onLoad(options) {
    const date = String(options.date || "").slice(0, 10);
    const part = options.part || "";
    const mode = options.mode === "training" ? "training" : "archive";
    if (mode === "training") {
      const [response, moduleResponse] = await Promise.all([
        ledger.call("trainingDayDetail", { date }),
        ledger.call("dataModules")
      ]);
      const data = response.ok ? response.data : null;
      const moduleModel = moduleResponse.ok ? safeBuildDataModuleReadModel(moduleResponse.data) : { modules: [] };
      this.setData({ loading: false, mode, date, part, detail: null, session: data ? data.session : null, sessionModules: modulesForDate(moduleModel, "training", date), movements: data ? displaySets(data.movements) : [], error: response.ok ? "" : response.message });
      return;
    }
    const [response, moduleResponse] = await Promise.all([
      ledger.call("recordDetail", { date }),
      ledger.call("dataModules")
    ]);
    const moduleModel = moduleResponse.ok ? safeBuildDataModuleReadModel(moduleResponse.data) : { modules: [] };
    this.setData({ loading: false, mode, date, detail: response.ok ? decorateDetail(response.data, moduleModel) : null, session: null, sessionModules: [], movements: [], error: response.ok ? "" : response.message });
  },
  toggle(event) {
    const key = event.currentTarget.dataset.key;
    this.setData({ [key]: !this.data[key] });
  },
  openMovement(event) {
    const id = event.currentTarget.dataset.id;
    if (id) wx.navigateTo({ url: `/pages/movement/index?id=${encodeURIComponent(id)}&part=${this.data.part}` });
  },
});
