const ledger = require("../../services/ledger");
const { BODY_PARTS, byId } = require("../../utils/bodyParts");
const freshness = require("../../utils/freshness");
const notepad = require("../../utils/freeformNotepad");

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
  data: { loading: true, error: "", selected: "", sortBy: "frequency", freshness: null, areas: BODY_PARTS, area: null, notepadOpen: false, notepadTurning: false, noteText: "" },
  async onShow() {
    if (getApp().globalData.resetReferenceNotepad) {
      getApp().globalData.resetReferenceNotepad = false;
      this.overview();
    }
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
    const noteText = notepad.migrateLegacy(part, notepad.load(part));
    this.noteText = noteText;
    this.setData({ loading: true, error: "", selected: part, notepadOpen: false, noteText, area: { label: theme.cn, labelEn: theme.en, tone: theme.tone, session_count: 0, movement_count: 0, latest_date: "", movements: [], sessions: [] } });
    const [response, records] = await Promise.all([ledger.call("bodyArea", { part }), ledger.call("trainingRecords")]);
    const area = response.ok ? sortedArea(enrichSessions({ ...response.data, label: theme.cn, labelEn: theme.en, tone: theme.tone }, records.ok ? records.data : []), this.data.sortBy) : this.data.area;
    this.setData({ loading: false, area, error: response.ok ? "" : response.message });
  },
  setSort(event) {
    const sortBy = event.currentTarget.dataset.sort;
    this.setData({ sortBy, area: this.data.area ? sortedArea(this.data.area, sortBy) : null });
  },
  overview() { this.setData({ selected: "", area: null, error: "", notepadOpen: false, noteText: "" }); },
  toggleNotepad() {
    if (this.data.notepadOpen) { this.setData({ notepadOpen: false }); return; }
    this.setData({ notepadTurning: true });
    setTimeout(() => this.setData({ notepadOpen: true, notepadTurning: false }), 150);
  },
  noop() {},
  onNoteInput(event) { this.noteText = event.detail.value; notepad.save(this.data.selected, this.noteText); },
  copyNote() {
    if (!this.noteText) { wx.showToast({ title: "暂无可复制内容", icon: "none" }); return; }
    wx.setClipboardData({ data: this.noteText, success: () => wx.showToast({ title: "已复制全部", icon: "success" }) });
  },
  clearNote() {
    wx.showModal({ title: "清空临时记录？", content: `只清空${this.data.area.label}的临时记录，不会影响正式训练记录。`, confirmText: "清空", confirmColor: "#a33d31", success: result => {
      if (!result.confirm) return;
      notepad.clear(this.data.selected);
      this.noteText = "";
      this.setData({ noteText: "" });
    } });
  },
  openMovement(event) { wx.navigateTo({ url: `/pages/movement/index?id=${event.currentTarget.dataset.id}&part=${this.data.selected}` }); },
  openSession(event) { wx.navigateTo({ url: `/pages/record/index?mode=training&date=${event.currentTarget.dataset.date}&part=${this.data.selected}` }); }
});
