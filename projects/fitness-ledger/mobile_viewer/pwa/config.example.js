// Copy this file to config.js only when the deployed PWA needs a non-default API.
// Never place CloudBase secrets, AppSecret, private keys, or personal data here.
window.FL_PWA_CONFIG = {
  // Same-origin /api routes are the safe default for the local Flask viewer.
  apiBaseUrl: "/api",
  credentials: "include",
  appName: "每日健身"
};
