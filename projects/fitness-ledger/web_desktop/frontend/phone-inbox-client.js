const SDK_URL = "https://static.cloudbase.net/cloudbase-js-sdk/2.27.1/cloudbase.full.js";
const ENV_ID = "cloud1-d9g35v5s1a904a8ad";
const REGION = "ap-shanghai";
const COLLECTION = "fl_web_share_inbox";
const MAX_ITEMS = 7;

let sdkPromise;
let appPromise;
let authPromise;

function loadSdk() {
  if (window.cloudbase) return Promise.resolve(window.cloudbase);
  if (!sdkPromise) {
    sdkPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = SDK_URL;
      script.async = true;
      script.onload = () => window.cloudbase ? resolve(window.cloudbase) : reject(new Error("PHONE_INBOX_SDK_MISSING"));
      script.onerror = () => reject(new Error("PHONE_INBOX_SDK_LOAD_FAILED"));
      document.head.appendChild(script);
    });
  }
  return sdkPromise;
}

async function cloudBaseApp() {
  if (!appPromise) appPromise = loadSdk().then(cloudbase => cloudbase.init({ env: ENV_ID, region: REGION }));
  return appPromise;
}

async function auth() {
  if (!authPromise) authPromise = cloudBaseApp().then(app => app.auth());
  return authPromise;
}

async function requireLogin() {
  const current = await auth();
  if (!(await current.getLoginState())) {
    const error = new Error("PHONE_INBOX_AUTH_REQUIRED");
    error.code = "PHONE_INBOX_AUTH_REQUIRED";
    throw error;
  }
  return current;
}

async function collection() {
  const app = await cloudBaseApp();
  return app.database().collection(COLLECTION);
}

export async function signIn(username, password) {
  const current = await auth();
  await current.signIn({ username: String(username || "").trim(), password: String(password || "") });
  return listRecent();
}

export async function listRecent() {
  await requireLogin();
  const inbox = await collection();
  const result = await inbox.where({ _openid: "{openid}" }).orderBy("received_at", "desc").limit(MAX_ITEMS + 5).get();
  return (Array.isArray(result.data) ? result.data : []).filter(item => item.status !== "expired").slice(0, MAX_ITEMS);
}

export async function updateStatus(id, status) {
  await requireLogin();
  const inbox = await collection();
  await inbox.where({ _id: id, _openid: "{openid}" }).update({ data: { status, updated_at: Date.now() } });
  return listRecent();
}

export async function prune() {
  await requireLogin();
  const inbox = await collection();
  const result = await inbox.where({ _openid: "{openid}" }).orderBy("received_at", "desc").limit(MAX_ITEMS + 20).get();
  const rows = Array.isArray(result.data) ? result.data : [];
  const expired = rows.slice(MAX_ITEMS);
  for (const item of expired) {
    try {
      await inbox.doc(item._id).remove();
    } catch (_) {
      await inbox.where({ _id: item._id, _openid: "{openid}" }).update({ data: { status: "expired", updated_at: Date.now() } });
    }
  }
  return rows.slice(0, MAX_ITEMS);
}

export const maxItems = MAX_ITEMS;
