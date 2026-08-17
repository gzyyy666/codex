const config = window.FL_PWA_CONFIG || {};
const API_BASE_URL = String(config.apiBaseUrl || "/api").replace(/\/$/, "");
const SDK_URL = "https://static.cloudbase.net/cloudbase-js-sdk/2.27.1/cloudbase.full.js";
let cloudbaseSdkPromise;
let cloudbaseAppPromise;
let webAuthPromise;

function accountLoginState(loginState) {
  const user = loginState?.user || {};
  const loginType = String(loginState?.loginType || user.loginType || "").toUpperCase();
  const uid = String(user.uid || loginState?.oauthLoginState?.sub || "").trim();
  const anonymous = loginState?.isAnonymousAuth === true || loginType === "ANONYMOUS";
  if (!loginState || anonymous || !uid) {
    const error = new Error("AUTH_ACCOUNT_REQUIRED");
    error.code = "AUTH_ACCOUNT_REQUIRED";
    throw error;
  }
  return { loginState, uid };
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
  accountLoginState(await auth.getLoginState());
  const token = await auth.getAccessToken();
  if (!token?.accessToken) throw new Error("AUTH_REQUIRED");
  return { Authorization: `Bearer ${token.accessToken}` };
}

export async function privateDatabase() {
  const auth = await webAuth();
  if (!auth) throw new Error("AUTH_REQUIRED");
  accountLoginState(await auth.getLoginState());
  const app = await cloudBaseApp();
  return app.database();
}

function buildUrl(action, params = {}) {
  const query = new URLSearchParams({ action, ...params });
  return `${API_BASE_URL}/pwa/read?${query.toString()}`;
}

export async function call(action, params = {}) {
  const authorization = await authorizationHeader();
  const response = await fetch(buildUrl(action, params), {
    method: "GET",
    credentials: config.credentials || "include",
    headers: { Accept: "application/json", ...authorization }
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
