const ledger = require("../../services/ledger");
const { BODY_PARTS, byId } = require("../../utils/bodyParts");

function sortedArea(area, sortBy) {
  const movements = (area.movements || []).slice();
  if (sortBy === "recent") movements.sort((a, b) => String(b.latest && b.latest.date || "").localeCompare(String(a.latest && a.latest.date || "")) || b.sessions - a.sessions);
  else if (sortBy === "name") movements.sort((a, b) => String(a.display_name || "").localeCompare(String(b.display_name || ""), "zh-CN"));
  else movements.sort((a, b) => b.sessions - a.sessions || String(b.latest && b.latest.date || "").localeCompare(String(a.latest && a.latest.date || "")));
  return { ...area, movements };
}

Page({
  data: { loading: true, error: "", selected: "", sortBy: "frequency", areas: BODY_PARTS, area: null },
  async onShow() {
    const pending = getApp().globalData.selectedBodyPart || "";
    getApp().globalData.selectedBodyPart = "";
    if (!this.data.areas.some(item => item.session_count !== undefined)) await this.loadOverview();
    if (pending) await this.loadArea(pending);
    else if (!this.data.selected) this.setData({ loading: false });
  },
  onTabItemTap() {
    this.overview();
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
    const area = response.ok ? sortedArea({ ...response.data, tone: theme.tone }, this.data.sortBy) : null;
    this.setData({ loading: false, area, error: response.ok ? "" : response.message });
  },
  setSort(event) {
    const sortBy = event.currentTarget.dataset.sort;
    this.setData({ sortBy, area: this.data.area ? sortedArea(this.data.area, sortBy) : null });
  },
  overview() { this.setData({ selected: "", area: null, error: "" }); },
  openMovement(event) { wx.navigateTo({ url: `/pages/movement/index?id=${event.currentTarget.dataset.id}` }); }
});
