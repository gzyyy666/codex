const config = window.FL_PWA_CONFIG || {};
const API_BASE_URL = String(config.apiBaseUrl || "/api").replace(/\/$/, "");
const SDK_URL = "https://static.cloudbase.net/cloudbase-js-sdk/2.27.1/cloudbase.full.js";
let cloudbaseSdkPromise;
let cloudbaseAppPromise;
let webAuthPromise;
const READ_TIMEOUT_MS = 12000;
const READ_ATTEMPTS = 2;

function retryableReadError(error) {
  return !error?.status || error.status >= 500 || ["READ_NETWORK", "READ_TIMEOUT"].includes(error.code);
}

async function fetchRead(url, options = {}) {
  let lastError;
  for (let attempt = 0; attempt < READ_ATTEMPTS; attempt += 1) {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const timer = window.setTimeout(() => controller?.abort(), READ_TIMEOUT_MS);
    try {
      const response = await fetch(url, {
        ...options,
        cache: "no-store",
        signal: controller?.signal
      });
      if (!response.ok) {
        const error = new Error(`HTTP_${response.status}`);
        error.code = `HTTP_${response.status}`;
        error.status = response.status;
        throw error;
      }
      return response;
    } catch (error) {
      const normalized = error?.name === "AbortError"
        ? Object.assign(new Error("READ_TIMEOUT"), { code: "READ_TIMEOUT" })
        : error?.status
          ? error
          : Object.assign(error instanceof Error ? error : new Error("READ_NETWORK"), { code: error?.code || "READ_NETWORK" });
      lastError = normalized;
      if (attempt >= READ_ATTEMPTS - 1 || !retryableReadError(normalized)) throw normalized;
      await new Promise(resolve => window.setTimeout(resolve, 250 * (attempt + 1)));
    } finally {
      window.clearTimeout(timer);
    }
  }
  throw lastError || new Error("READ_NETWORK");
}

function webAuthEnabled() {
  return config.requireWebAuth === true;
}

async function loadCloudBaseSdk() {
  if (window.cloudbase) return window.cloudbase;
  if (!cloudbaseSdkPromise) {
    cloudbaseSdkPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = SDK_URL;
      script.async = true;
      script.onload = () => window.cloudbase ? resolve(window.cloudbase) : reject(new Error("CLOUDBASE_SDK_MISSING"));
      script.onerror = () => reject(new Error("CLOUDBASE_SDK_LOAD_FAILED"));
      document.head.appendChild(script);
    });
  }
  return cloudbaseSdkPromise;
}

async function cloudBaseApp() {
  if (!webAuthEnabled()) throw new Error("WEB_AUTH_DISABLED");
  if (!config.envId) throw new Error("CLOUDBASE_ENV_MISSING");
  if (!cloudbaseAppPromise) {
    cloudbaseAppPromise = loadCloudBaseSdk().then(cloudbase => (
      cloudbase.init({ env: config.envId, region: config.region || "ap-shanghai" })
    ));
  }
  return cloudbaseAppPromise;
}

async function webAuth() {
  if (!webAuthEnabled()) return null;
  if (!webAuthPromise) {
    webAuthPromise = cloudBaseApp().then(app => app.auth());
  }
  return webAuthPromise;
}

export async function signIn(username, password) {
  const auth = await webAuth();
  if (!auth) throw new Error("WEB_AUTH_DISABLED");
  return auth.signIn({ username: String(username || "").trim(), password: String(password || "") });
}

export async function signOut() {
  const auth = await webAuth();
  if (auth) await auth.signOut();
}

async function authorizationHeader() {
  const auth = await webAuth();
  if (!auth) return {};
  if (!(await auth.getLoginState())) throw new Error("AUTH_REQUIRED");
  const token = await auth.getAccessToken();
  if (!token?.accessToken) throw new Error("AUTH_REQUIRED");
  return { Authorization: `Bearer ${token.accessToken}` };
}

export async function privateDatabase() {
  const auth = await webAuth();
  if (!auth || !(await auth.getLoginState())) throw new Error("AUTH_REQUIRED");
  const app = await cloudBaseApp();
  return app.database();
}

function buildUrl(action, params = {}) {
  const query = new URLSearchParams({ action, ...params });
  return `${API_BASE_URL}/pwa/read?${query.toString()}`;
}

export async function call(action, params = {}) {
  const authorization = await authorizationHeader();
  const response = await fetchRead(buildUrl(action, params), {
    method: "GET",
    credentials: config.credentials || "include",
    headers: { Accept: "application/json", ...authorization }
  });
  let payload;
  try {
    payload = await response.json();
  } catch (_) {
    throw Object.assign(new Error("READ_INVALID_JSON"), { code: "READ_INVALID_JSON" });
  }
  if (!payload || payload.ok !== true) throw new Error(payload?.code || "API_FAILED");
  return payload.data;
}

export function apiDescription() {
  return {
    baseUrl: API_BASE_URL,
    mode: /^https?:\/\//i.test(API_BASE_URL) ? "external" : "same-origin"
  };
}
