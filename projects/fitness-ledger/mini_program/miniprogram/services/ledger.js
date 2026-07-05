function configured() {
  const app = getApp();
  return Boolean(wx.cloud && app.globalData.config.envId);
}

async function call(action, params = {}) {
  if (!configured()) {
    return { ok: false, code: "NOT_CONFIGURED", message: "尚未配置 CloudBase 环境。" };
  }
  try {
    const response = await wx.cloud.callFunction({ name: "ledgerRead", data: { action, ...params } });
    return response.result || { ok: false, code: "EMPTY_RESPONSE", message: "云端没有返回数据。" };
  } catch (_error) {
    return { ok: false, code: "NETWORK_ERROR", message: "读取失败，请检查网络与云函数。" };
  }
}

module.exports = { call };
