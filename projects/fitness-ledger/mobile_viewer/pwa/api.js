const config = window.FL_PWA_CONFIG || {};
const API_BASE_URL = String(config.apiBaseUrl || "/api").replace(/\/$/, "");

function buildUrl(path) {
  if (/^https?:\/\//i.test(API_BASE_URL)) {
    return `${API_BASE_URL}${path}`;
  }
  return `${API_BASE_URL}${path}`;
}

async function request(path) {
  const response = await fetch(buildUrl(path), {
    method: "GET",
    credentials: config.credentials || "include",
    headers: { Accept: "application/json" }
  });
  if (!response.ok) {
    throw new Error(`HTTP_${response.status}`);
  }
  const payload = await response.json();
  if (payload && payload.ok === false) {
    throw new Error(payload.code || "API_FAILED");
  }
  return payload && payload.ok === true && Object.prototype.hasOwnProperty.call(payload, "data")
    ? payload.data
    : payload;
}

export function getToday() {
  return request("/today");
}

export function getTraining(date) {
  return request(`/training/${encodeURIComponent(date)}`);
}

export function getSearch(query) {
  return request(`/search?q=${encodeURIComponent(query)}`);
}

export function apiDescription() {
  return {
    baseUrl: API_BASE_URL,
    configured: Boolean(config.apiBaseUrl),
    mode: /^https?:\/\//i.test(API_BASE_URL) ? "external" : "same-origin"
  };
}
