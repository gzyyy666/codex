"""Anonymous tests for runtime build identity and the Web endpoint."""

from __future__ import annotations

import json
import sys
import tempfile
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from web_desktop.backend.build_identity import collect_build_info  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


def fake_git(mapping):
    def runner(args, _cwd):
        key = tuple(args[1:])
        if key not in mapping:
            raise RuntimeError("git unavailable")
        return mapping[key]

    return runner


def test_preview_clean_and_dirty() -> None:
    mapping = {
        ("rev-parse", "--show-toplevel"): ".",
        ("rev-parse", "HEAD"): "a" * 40,
        ("symbolic-ref", "--short", "HEAD"): "feat/review",
        ("rev-parse", "main"): "a" * 40,
        ("rev-parse", "origin/main"): "a" * 40,
        ("status", "--porcelain"): "",
        ("describe", "--tags", "--exact-match", "HEAD"): "",
    }
    clean = collect_build_info(Path("."), runner=fake_git(mapping), server_started_at="started")
    assert clean["status"] == "PREVIEW" and clean["dirty"] is False
    mapping[("status", "--porcelain")] = " M web_desktop/app.js"
    dirty = collect_build_info(Path("."), runner=fake_git(mapping), server_started_at="started")
    assert dirty["status"] == "PREVIEW" and dirty["dirty"] is True
    assert dirty["status"] != "PUBLISHED"


def test_formal_manifest_states() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        manifest = root / "runtime_build_info.json"
        payload = {
            "schema_version": 1,
            "mode": "formal",
            "commit_sha": "b" * 40,
            "branch": "main",
            "main_sha": "b" * 40,
            "origin_main_sha": "b" * 40,
            "push_verified": True,
            "generated_at": "2026-07-18T00:00:00Z",
        }
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        assert collect_build_info(root, manifest_path=manifest)["status"] == "PUBLISHED"
        payload["push_verified"] = False
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        assert collect_build_info(root, manifest_path=manifest)["status"] == "UNVERIFIED"
        manifest.write_text("{broken", encoding="utf-8")
        assert collect_build_info(root, manifest_path=manifest)["status"] == "UNKNOWN"


def test_unknown_git_and_endpoint() -> None:
    unknown = collect_build_info(Path("."), runner=lambda *_: (_ for _ in ()).throw(RuntimeError("no git")))
    assert unknown["status"] == "UNKNOWN"
    service = LedgerWebService(build_info_override={"mode": "preview", "status": "PREVIEW", "commit_sha": "c" * 40, "short_sha": "c" * 7, "branch": "review", "dirty": False})
    server = create_server("127.0.0.1", 0, service)
    try:
        server_url = f"http://127.0.0.1:{server.server_port}/api/build-info"
        server_thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        request = urllib.request.urlopen(server_url, timeout=2)
        assert request.headers.get("Cache-Control") == "no-store"
        body = json.loads(request.read().decode("utf-8"))
        assert body["commit_sha"] == "c" * 40
        assert "C:\\Users" not in json.dumps(body)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    test_preview_clean_and_dirty()
    test_formal_manifest_states()
    test_unknown_git_and_endpoint()
    print("build identity tests passed")
