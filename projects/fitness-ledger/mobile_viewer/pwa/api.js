const config = window.FL_PWA_CONFIG || {};
const API_BASE_URL = String(config.apiBaseUrl || "/api").replace(/\/$/, "");

function buildUrl(action, params = {}) {
  const query = new URLSearchParams({ action, ...params });
  return `${API_BASE_URL}/pwa/read?${query.toString()}`;
}

export async function call(action, params = {}) {
  const response = await fetch(buildUrl(action, params), {
    method: "GET",
    credentials: config.credentials || "include",
    headers: { Accept: "application/json" }
  });
  if (!response.ok) throw new Error(`HTTP_${response.status}`);
  const payload = await response.json();
  if (!payload || payload.ok !== true) throw new Error(payload?.code || "API_FAILED");
  return payload.data;
}

export function apiDescription() {
  return {
    baseUrl: API_BASE_URL,
    mode: /^https?:\/\//i.test(API_BASE_URL) ? "external" : "same-origin"
  };
}
