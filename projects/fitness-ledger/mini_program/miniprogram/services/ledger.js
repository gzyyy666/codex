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
    const result = response.result || { ok: false, code: "EMPTY_RESPONSE", message: "云端没有返回数据。" };
    if (!result.ok && result.code === "UNKNOWN_ACTION") {
      return { ...result, message: "训练参考接口尚未更新，请重新部署 ledgerRead 云函数。" };
    }
    if (!result.ok && result.code === "QUERY_FAILED") {
      return { ...result, message: "训练参考数据暂不可用，请稍后重试或检查同步状态。" };
    }
    return result;
  } catch (_error) {
    return { ok: false, code: "NETWORK_ERROR", message: "读取失败，请检查网络与云函数。" };
  }
}

module.exports = { call };
