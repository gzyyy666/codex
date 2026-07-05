let config = require("./config/env.example");
try {
  config = require("./config/env.local");
} catch (_error) {
  // Local environment configuration is intentionally optional and untracked.
}

App({
  globalData: { config, selectedBodyPart: "" },
  onLaunch() {
    if (wx.cloud && config.envId) {
      wx.cloud.init({ env: config.envId, traceUser: true });
    }
  }
});
