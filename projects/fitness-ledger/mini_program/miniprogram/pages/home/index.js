const ledger = require("../../services/ledger");
const { BODY_PARTS } = require("../../utils/bodyParts");

Page({
  data: { loading: true, error: "", latest: null, areas: BODY_PARTS },
  async onShow() {
    this.setData({ loading: true, error: "" });
    const [latest, areas] = await Promise.all([ledger.call("latest"), ledger.call("bodyAreas")]);
    const counts = areas.ok ? areas.data.reduce((map, item) => { map[item.id] = item; return map; }, {}) : {};
    this.setData({
      loading: false,
      latest: latest.ok ? latest.data : null,
      areas: BODY_PARTS.map(item => ({ ...item, ...(counts[item.id] || {}) })),
      error: latest.ok && areas.ok ? "" : (latest.message || areas.message)
    });
  },
  openArea(event) {
    getApp().globalData.selectedBodyPart = event.currentTarget.dataset.part;
    wx.switchTab({ url: "/pages/reference/index" });
  },
  today() { wx.navigateTo({ url: "/pages/today/index" }); },
  search() { wx.switchTab({ url: "/pages/search/index" }); }
});
