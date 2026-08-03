"""Static contract checks for the read-only mobile workbench PWA."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PWA = ROOT / "mobile_viewer" / "pwa"


def main() -> None:
    required = [
        PWA / "index.html",
        PWA / "manifest.webmanifest",
        PWA / "app.js",
        PWA / "api.js",
        PWA / "styles.css",
        PWA / "sw.js",
        PWA / "icons" / "fitness-ledger.png",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise AssertionError(f"missing PWA files: {missing}")

    manifest = json.loads((PWA / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "./"
    assert manifest["scope"] == "./"
    assert manifest["icons"]

    source = "\n".join(path.read_text(encoding="utf-8") for path in required if path.suffix in {".html", ".js", ".css"})
    app_source = (PWA / "app.js").read_text(encoding="utf-8")
    for route in ("reference", "training", "status", "body", "diet", "record", "movement"):
        assert f'"{route}"' in app_source, f"missing Mini Program route: {route}"
    assert "NOTE_KEY" in app_source
    assert "home-page" not in app_source and "plan-grid" not in app_source
    forbidden = ["wx.cloud", "AppSecret", "FITNESS_LEDGER_ALLOWED_OPENIDS", "POST", "PUT", "DELETE"]
    violations = [token for token in forbidden if token in source]
    if violations:
        raise AssertionError(f"PWA must stay read-only and credential-free: {violations}")

    service_worker = (PWA / "sw.js").read_text(encoding="utf-8")
    assert 'includes("/api/")' in service_worker
    print("PWA static contract: PASS")


if __name__ == "__main__":
    main()
