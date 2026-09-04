const SDK_URL = "https://static.cloudbase.net/cloudbase-js-sdk/2.27.1/cloudbase.full.js";
const ENV_ID = "cloud1-d9g35v5s1a904a8ad";
const REGION = "ap-shanghai";
const COLLECTION = "fl_web_share_inbox";
const RECENT_DAYS = 7;
const QUERY_LIMIT = 50;
const REQUEST_TIMEOUT_MS = 15000;
// 云端只负责接收；电脑端成功读取后通过本地服务持久化最近 7 次完整发送。
const KEEP_COUNT = 7;

let sdkPromise;
let appPromise;
let authPromise;
let appSource;
let authSource;

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
  if (window.cloudbase && appSource !== window.cloudbase) {
    appSource = window.cloudbase;
    appPromise = Promise.resolve(appSource.init({ env: ENV_ID, region: REGION }));
    authPromise = null;
    authSource = null;
  }
  if (!appPromise) appPromise = loadSdk().then(cloudbase => { appSource = cloudbase; return cloudbase.init({ env: ENV_ID, region: REGION }); });
  return appPromise;
}

async function auth() {
  const app = await cloudBaseApp();
  if (!authPromise || authSource !== appSource) {
    authSource = appSource;
    authPromise = Promise.resolve(app.auth());
  }
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

function itemKey(item) {
  const normalized = normalizeItem(item);
  return String(normalized._id || "");
}

function retainLatest(items) {
  const byKey = new Map();
  for (const item of items.map(normalizeItem)) {
    if (!item || item.status === "expired") continue;
    if (!itemKey(item)) continue;
    byKey.set(itemKey(item), item);
  }
  return [...byKey.values()]
    .sort((left, right) => {
      const time = Number(right.received_at || 0) - Number(left.received_at || 0);
      return time || String(right._id || "").localeCompare(String(left._id || ""));
    })
    .slice(0, KEEP_COUNT);
}

async function readLocalSnapshot() {
  const response = await withTimeout(fetch("/api/phone-inbox/local", { cache: "no-store" }), "PHONE_INBOX_LOCAL_READ_TIMEOUT");
  let payload = {};
  try { payload = await response.json(); } catch (_) {}
  if (!response.ok) {
    const error = new Error(payload.error || "Local phone inbox is unavailable.");
    error.code = payload.code || "PHONE_INBOX_LOCAL_READ_FAILED";
    throw error;
  }
  return { ...payload, items: retainLatest(Array.isArray(payload.items) ? payload.items : []) };
}

export async function localItems() {
  return (await readLocalSnapshot()).items;
}

export async function readCache() {
  // Compatibility export for older page bundles.  Durable state is now the
  // backend file; browser storage is intentionally never an inbox authority.
  return localItems();
}

export async function signIn(username, password) {
  const current = await auth();
  await withTimeout(current.signIn({ username: String(username || "").trim(), password: String(password || "") }), "PHONE_INBOX_AUTH_TIMEOUT");
  return listRecent();
}

export async function listRecent() {
  const local = await readLocalSnapshot();
  try {
    const { uid } = await requireLogin();
    const inbox = await collection();
    // Filter by account in CloudBase, then apply the deterministic ordering
    // locally.  This avoids making inbox delivery depend on a remote
    // received_at index while retaining the same latest-first rule.
    const result = await withTimeout(inbox.where({ owner_uid: uid }).limit(QUERY_LIMIT).get(), "PHONE_INBOX_READ_TIMEOUT");
    // The backend owns dedupe, ordering, persistence, and the seven-item
    // retention rule.  Send the complete query result to that one service.
    const cloudItems = Array.isArray(result.data) ? result.data : [];
    const response = await withTimeout(fetch("/api/phone-inbox/sync", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ items: cloudItems })
    }), "PHONE_INBOX_LOCAL_WRITE_TIMEOUT");
    let payload = {};
    try { payload = await response.json(); } catch (_) {}
    if (!response.ok) {
      const error = new Error(payload.error || "Local phone inbox could not be saved.");
      error.code = payload.code || "PHONE_INBOX_LOCAL_WRITE_FAILED";
      throw error;
    }
    return retainLatest(Array.isArray(payload.items) ? payload.items : []);
  } catch (error) {
    // At-least-once retry: keep the durable snapshot visible, but preserve the
    // cloud/network error so the page can report that sync will retry.
    error.localItems = local.items;
    throw error;
  }
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
  const response = await withTimeout(fetch("/api/phone-inbox/remove", {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ id })
  }), "PHONE_INBOX_LOCAL_WRITE_TIMEOUT");
  let payload = {};
  try { payload = await response.json(); } catch (_) {}
  if (!response.ok) {
    const error = new Error(payload.error || "Local phone inbox could not remove the item.");
    error.code = payload.code || "PHONE_INBOX_LOCAL_DELETE_FAILED";
    throw error;
  }
  return retainLatest(Array.isArray(payload.items) ? payload.items : []);
}

export const recentDays = RECENT_DAYS;
