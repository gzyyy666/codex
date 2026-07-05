const ledger = require("../../services/ledger");
const { BODY_PARTS, byId } = require("../../utils/bodyParts");

Page({
  data: { loading: true, error: "", selected: "", areas: BODY_PARTS, area: null },
  async onShow() {
    const pending = getApp().globalData.selectedBodyPart || "";
    getApp().globalData.selectedBodyPart = "";
    if (!this.data.areas.some(item => item.session_count !== undefined)) await this.loadOverview();
    if (pending) await this.loadArea(pending);
    else if (!this.data.selected) this.setData({ loading: false });
  },
  async loadOverview() {
    this.setData({ loading: true, error: "" });
    const response = await ledger.call("bodyAreas");
    const counts = response.ok ? response.data.reduce((map, item) => { map[item.id] = item; return map; }, {}) : {};
    this.setData({
      loading: false,
      areas: BODY_PARTS.map(item => ({ ...item, ...(counts[item.id] || {}) })),
      error: response.ok ? "" : response.message
    });
  },
  selectArea(event) { this.loadArea(event.currentTarget.dataset.part); },
  async loadArea(part) {
    const theme = byId(part);
    if (!theme) return;
    this.setData({ loading: true, error: "", selected: part, area: { label: theme.cn, labelEn: theme.en, tone: theme.tone, session_count: 0, movement_count: 0, latest_date: "", movements: [] } });
    const response = await ledger.call("bodyArea", { part });
    this.setData({ loading: false, area: response.ok ? { ...response.data, tone: theme.tone } : null, error: response.ok ? "" : response.message });
  },
  overview() { this.setData({ selected: "", area: null, error: "" }); },
  openMovement(event) { wx.navigateTo({ url: `/pages/movement/index?id=${event.currentTarget.dataset.id}` }); }
});
