// Copy this file to config.js only when the deployed PWA needs a non-default API.
// Never place CloudBase secrets, AppSecret, private keys, or personal data here.
window.FL_PWA_CONFIG = {
  // Local development uses the Flask adapter. Production should use the
  // reviewed HTTPS gateway URL and set requireWebAuth to true.
  apiBaseUrl: "/api",
  credentials: "include",
  envId: "cloud1-d9g35v5s1a904a8ad",
  region: "ap-shanghai",
  requireWebAuth: false,
  appName: "每日健身"
};
