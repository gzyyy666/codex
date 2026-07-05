const ledger = require("../../services/ledger");
const { BODY_PARTS } = require("../../utils/bodyParts");

Page({
  data: { loading: true, actionLoading: false, error: "", syncNotice: "", latest: null, areas: BODY_PARTS, selected: "", area: null, featured: [] },
  async onShow() {
    this.setData({ loading: true, error: "", syncNotice: "" });
    const [latest, areas] = await Promise.all([ledger.call("latest"), ledger.call("bodyAreas")]);
    const counts = areas.ok ? areas.data.reduce((map, item) => { map[item.id] = item; return map; }, {}) : {};
    const merged = BODY_PARTS.map(item => ({ ...item, ...(counts[item.id] || {}) }));
    const recent = merged.slice().sort((a, b) => String(b.latest_date || "").localeCompare(String(a.latest_date || "")))[0];
    const selected = this.data.selected || (recent && recent.latest_date ? recent.id : "shoulders");
    this.setData({
      loading: false,
      latest: latest.ok ? latest.data : null,
      areas: merged,
      selected,
      error: latest.ok ? "" : latest.message,
      syncNotice: areas.ok ? "" : areas.message
    });
    if (areas.ok) await this.loadArea(selected);
  },
  selectArea(event) { this.loadArea(event.currentTarget.dataset.part); },
  async loadArea(part) {
    this.setData({ selected: part, actionLoading: true, syncNotice: "" });
    const response = await ledger.call("bodyArea", { part });
    this.setData({
      actionLoading: false,
      area: response.ok ? response.data : null,
      featured: response.ok ? response.data.movements.slice(0, 2) : [],
      syncNotice: response.ok ? "" : response.message
    });
  },
  viewAll() {
    getApp().globalData.selectedBodyPart = this.data.selected;
    wx.switchTab({ url: "/pages/reference/index" });
  },
  openMovement(event) { wx.navigateTo({ url: `/pages/movement/index?id=${event.currentTarget.dataset.id}` }); },
  today() { wx.navigateTo({ url: "/pages/today/index" }); },
  search() { wx.switchTab({ url: "/pages/search/index" }); }
});
