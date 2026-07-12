const ledger = require("../../services/ledger");
const { BODY_PARTS, byId } = require("../../utils/bodyParts");
const freshness = require("../../utils/freshness");

function sortedArea(area, sortBy) {
  const movements = (area.movements || []).slice();
  if (sortBy === "recent") movements.sort((a, b) => String(b.latest && b.latest.date || "").localeCompare(String(a.latest && a.latest.date || "")) || b.sessions - a.sessions);
  else if (sortBy === "name") movements.sort((a, b) => String(a.display_name || "").localeCompare(String(b.display_name || ""), "zh-CN"));
  else movements.sort((a, b) => {
    const aRank = Number(a.focus_rank || 0), bRank = Number(b.focus_rank || 0);
    const aFocused = Boolean(a.pinned) || aRank > 0, bFocused = Boolean(b.pinned) || bRank > 0;
    return Number(bFocused) - Number(aFocused)
      || (aRank > 0 ? aRank : Number.MAX_SAFE_INTEGER) - (bRank > 0 ? bRank : Number.MAX_SAFE_INTEGER)
      || b.sessions - a.sessions
      || String(b.latest && b.latest.date || "").localeCompare(String(a.latest && a.latest.date || ""));
  });
  return { ...area, movements };
}

function enrichSessions(area, records) {
  const byDate = (records || []).reduce((map, record) => { map[String(record.Date || "").slice(0, 10)] = record; return map; }, {});
  return { ...area, sessions: (area.sessions || []).map(session => {
    const record = byDate[session.date] || {};
    const title = String(session.split || "").trim() || `${area.label}训练`;
    return { ...session, title, full_summary: record["Standardized Summary"] || record.Summary || session.movement_summary || "暂无完整动作摘要" };
  }) };
}

Page({
  data: { loading: true, error: "", selected: "", sortBy: "frequency", freshness: null, areas: BODY_PARTS, area: null },
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
    const [response, status] = await Promise.all([ledger.call("bodyAreas"), ledger.call("status")]);
    const counts = response.ok ? response.data.reduce((map, item) => { map[item.id] = item; return map; }, {}) : {};
    this.setData({
      loading: false,
      areas: BODY_PARTS.map(item => ({ ...item, ...(counts[item.id] || {}) })),
      freshness: status.ok ? freshness.describe(status.data) : null,
      error: response.ok ? "" : response.message
    });
  },
  selectArea(event) { this.loadArea(event.currentTarget.dataset.part); },
  async loadArea(part) {
    const theme = byId(part);
    if (!theme) return;
    this.setData({ loading: true, error: "", selected: part, area: { label: theme.cn, labelEn: theme.en, tone: theme.tone, session_count: 0, movement_count: 0, latest_date: "", movements: [], sessions: [] } });
    const [response, records] = await Promise.all([ledger.call("bodyArea", { part }), ledger.call("trainingRecords")]);
    const area = response.ok ? sortedArea(enrichSessions({ ...response.data, tone: theme.tone }, records.ok ? records.data : []), this.data.sortBy) : null;
    this.setData({ loading: false, area, error: response.ok ? "" : response.message });
  },
  setSort(event) {
    const sortBy = event.currentTarget.dataset.sort;
    this.setData({ sortBy, area: this.data.area ? sortedArea(this.data.area, sortBy) : null });
  },
  overview() { this.setData({ selected: "", area: null, error: "" }); },
  openMovement(event) { wx.navigateTo({ url: `/pages/movement/index?id=${event.currentTarget.dataset.id}` }); },
  openSession(event) { wx.navigateTo({ url: `/pages/record/index?mode=training&date=${event.currentTarget.dataset.date}` }); }
});
