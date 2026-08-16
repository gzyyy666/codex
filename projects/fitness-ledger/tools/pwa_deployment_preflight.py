"""Validate the tracked PWA bundle before static hosting deployment."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PWA = ROOT / "mobile_viewer" / "pwa"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deployment",
        action="store_true",
        help="also fail when config.js still points at the local same-origin API",
    )
    args = parser.parse_args()

    required = [
        "index.html",
        "manifest.webmanifest",
        "app.js",
        "data-modules.js",
        "api.js",
        "config.js",
        "styles.css",
        "sw.js",
        "share.html",
        "share.css",
        "share.js",
        "icons/fitness-ledger.png",
    ]
    missing = [item for item in required if not (PWA / item).is_file()]
    if missing:
        print(f"PWA_PREFLIGHT_FAIL missing={missing}")
        return 1

    manifest = json.loads((PWA / "manifest.webmanifest").read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    if manifest.get("display") != "standalone":
        errors.append("manifest.display must be standalone")
    if manifest.get("start_url") != "./" or manifest.get("scope") != "./":
        errors.append("manifest start_url/scope must remain relative ./")
    if not manifest.get("icons"):
        errors.append("manifest.icons is empty")
    share_target = manifest.get("share_target") or {}
    if share_target.get("action") != "./index.html" or share_target.get("method") != "GET":
        errors.append("manifest.share_target must point to the in-app index.html GET entry")
    share_entry = (PWA / "share.html").read_text(encoding="utf-8")
    if "window.location.replace" not in share_entry or "./index.html" not in share_entry:
        errors.append("legacy share.html must redirect into the in-app index.html flow")

    html = (PWA / "index.html").read_text(encoding="utf-8")
    config = (PWA / "config.js").read_text(encoding="utf-8")
    source = "\n".join(
        (PWA / item).read_text(encoding="utf-8")
        for item in ("index.html", "app.js", "data-modules.js", "api.js", "config.js", "styles.css", "sw.js", "share.html", "share.js")
    )
    forbidden = ("AppSecret", "SecretId", "SecretKey", "TENCENTCLOUD_SECRET", "wx.cloud")
    found_forbidden = [token for token in forbidden if token in source]
    if found_forbidden:
        errors.append(f"secret/platform token in browser bundle: {found_forbidden}")
    candidate_tokens = ["share-review.html", "模拟手机分享", "anonymous-review-fixture", "share_inbox.json"]
    leaked_candidates = [token for token in candidate_tokens if token in source]
    if leaked_candidates:
        errors.append(f"candidate share-review trace in formal bundle: {leaked_candidates}")
    if not re.search(r'<meta[^>]+name="viewport"', html, re.IGNORECASE):
        errors.append("viewport meta tag is missing")
    if re.search(r'apiBaseUrl\s*:\s*["\']?/api["\']?', config):
        warnings.append("config.js still points to the local/same-origin /api adapter")
        if args.deployment:
            errors.append("deployment config needs a reviewed HTTPS Web API gateway")
    if re.search(r'requireWebAuth\s*:\s*false', config, re.IGNORECASE) and args.deployment:
        errors.append("deployment config must require Web authentication")
    if args.deployment and not re.search(r'envId\s*:\s*["\']cloud1-[^"\']+["\']', config):
        errors.append("deployment config must contain the reviewed CloudBase environment id")

    if errors:
        print("PWA_PREFLIGHT_FAIL")
        for item in errors:
            print(f"- {item}")
        return 1
    print("PWA_STATIC_BUNDLE_OK")
    for item in warnings:
        print(f"PWA_PREFLIGHT_WARNING - {item}")
    if warnings:
        print("PWA_FUNCTIONAL_DEPLOYMENT_BLOCKED until Web API/auth is configured")
    else:
        print("PWA_DEPLOYMENT_CONFIG_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
