const ledger = require("../../services/ledger");
const { safeBuildDataModuleReadModel, modulesForExtension } = require("../../utils/dataModuleContract");
const BUILD_VERSION = "v2026.08.15-data-module-extension-13";

function homeModules(response) {
  if (!response.ok) return [];
  const model = safeBuildDataModuleReadModel(response.data);
  return model.modules.filter(item => item.display_surface.value === "page_widget" && (!item.display_page || item.display_page.value === "home"));
}

function extensionModules(response) {
  if (!response.ok) return [];
  const model = safeBuildDataModuleReadModel(response.data);
  return modulesForExtension(model);
}
Page({
  data: { loading: true, error: "", status: null, identity: null, homeModules: [], extensionModules: [], buildVersion: BUILD_VERSION },
  async onShow() {
    getApp().globalData.resetReferenceNotepad = true;
    const [status, identity, modules] = await Promise.all([ledger.call("status"), ledger.call("whoami"), ledger.call("dataModules")]);
    this.setData({ loading: false, status: status.ok ? status.data : null, identity: identity.ok ? identity.data : null, homeModules: homeModules(modules), extensionModules: extensionModules(modules), error: status.ok ? "" : status.message });
  },
  openBody() { wx.navigateTo({ url: "/pages/body/index" }); },
  openDiet() { wx.navigateTo({ url: "/pages/diet/index" }); }
});
