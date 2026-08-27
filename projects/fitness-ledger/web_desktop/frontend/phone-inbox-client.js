const SDK_URL = "https://static.cloudbase.net/cloudbase-js-sdk/2.27.1/cloudbase.full.js";
const ENV_ID = "cloud1-d9g35v5s1a904a8ad";
const REGION = "ap-shanghai";
const COLLECTION = "fl_web_share_inbox";
const RECENT_DAYS = 7;
const QUERY_LIMIT = 50;
const REQUEST_TIMEOUT_MS = 15000;
// 电脑端保留最近 7 次发送；云端读取成功后自动落到本地缓存，云端不可用时回退。
const KEEP_COUNT = 7;
const CACHE_KEY = "fitness-ledger:phone-inbox-recent:v1";

let sdkPromise;
let appPromise;
let authPromise;

function withTimeout(promise, code) {
  let timer;
  return Promise.race([
    promise,
    new Promise((_, reject) => { timer = window.setTimeout(() => reject(Object.assign(new Error(code), { code })), REQUEST_TIMEOUT_MS); })
  ]).finally(() => window.clearTimeout(timer));
}

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
    }).catch(error => { sdkPromise = null; throw error; });
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
  const loginState = await withTimeout(current.getLoginState(), "PHONE_INBOX_AUTH_TIMEOUT");
  const user = loginState?.user || {};
  const loginType = String(loginState?.loginType || user.loginType || "").toUpperCase();
  const uid = String(user.uid || loginState?.oauthLoginState?.sub || "").trim();
  if (!loginState || loginState.isAnonymousAuth === true || loginType === "ANONYMOUS" || !uid) {
    const error = new Error("PHONE_INBOX_ACCOUNT_REQUIRED");
    error.code = "PHONE_INBOX_ACCOUNT_REQUIRED";
    throw error;
  }
  return { current, uid };
}

async function collection() {
  const app = await cloudBaseApp();
  return app.database().collection(COLLECTION);
}

function normalizeItem(item) {
  const nested = item?.data && typeof item.data === "object" ? item.data : {};
  return { ...nested, ...item };
}

function saveCache(items) {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify({ saved_at: Date.now(), items })); } catch (_) {}
}

export function readCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed?.items) ? parsed.items : [];
  } catch (_) { return []; }
}

export async function signIn(username, password) {
  const current = await auth();
  await withTimeout(current.signIn({ username: String(username || "").trim(), password: String(password || "") }), "PHONE_INBOX_AUTH_TIMEOUT");
  return listRecent();
}

export async function listRecent() {
  const { uid } = await requireLogin();
  const inbox = await collection();
  const cutoff = Date.now() - RECENT_DAYS * 24 * 60 * 60 * 1000;
  const result = await withTimeout(inbox.where({ owner_uid: uid }).orderBy("received_at", "desc").limit(QUERY_LIMIT).get(), "PHONE_INBOX_READ_TIMEOUT");
  const items = (Array.isArray(result.data) ? result.data : []).map(normalizeItem)
    .filter(item => item.status !== "expired" && Number(item.received_at || 0) >= cutoff)
    .slice(0, KEEP_COUNT);
  saveCache(items);
  return items;
}

export async function updateStatus(id, status) {
  const { uid } = await requireLogin();
  const inbox = await collection();
  await withTimeout(inbox.where({ _id: id, owner_uid: uid }).update({ status, updated_at: Date.now() }), "PHONE_INBOX_WRITE_TIMEOUT");
  return listRecent();
}

export async function removeItem(id) {
  const { uid } = await requireLogin();
  const inbox = await collection();
  await withTimeout(inbox.where({ _id: id, owner_uid: uid }).remove(), "PHONE_INBOX_WRITE_TIMEOUT");
  return listRecent();
}

export const recentDays = RECENT_DAYS;
