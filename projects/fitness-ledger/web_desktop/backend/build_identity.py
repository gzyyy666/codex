"""Safe runtime identity for the Fitness Ledger Web service.

The preview path reads Git without fetching or writing.  Formal deployments
read a deployment manifest written by the release workflow.  This module
deliberately returns a small, path-free public shape for the browser.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


REQUIRED_MANIFEST_FIELDS = (
    "schema_version",
    "mode",
    "commit_sha",
    "branch",
    "main_sha",
    "origin_main_sha",
    "push_verified",
    "generated_at",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _default_runner(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=3,
        check=True,
        shell=False,
    )
    return result.stdout.strip()


def _run(runner: Callable[[list[str], Path], str], args: list[str], cwd: Path) -> str:
    return runner(args, cwd)


def _public(
    *,
    mode: str,
    status: str,
    source: str,
    commit_sha: str = "",
    branch: str = "",
    main_sha: str = "",
    origin_main_sha: str = "",
    push_verified: bool | None = None,
    generated_at: str = "",
    server_started_at: str = "",
    dirty: bool | None = None,
    tag: str = "",
) -> dict:
    return {
        "mode": mode,
        "status": status,
        "source": source,
        "commit_sha": commit_sha,
        "short_sha": commit_sha[:7] if commit_sha else "",
        "branch": branch,
        "main_sha": main_sha,
        "origin_main_sha": origin_main_sha,
        "push_verified": push_verified,
        "generated_at": generated_at,
        "server_started_at": server_started_at,
        "dirty": dirty,
        "tag": tag,
    }


def unknown(server_started_at: str = "", source: str = "unknown") -> dict:
    return _public(
        mode="unknown",
        status="UNKNOWN",
        source=source,
        server_started_at=server_started_at,
    )


def _valid_manifest(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if any(field not in payload for field in REQUIRED_MANIFEST_FIELDS):
        return False
    if payload.get("schema_version") != 1 or payload.get("mode") != "formal":
        return False
    if not all(isinstance(payload.get(field), str) and payload.get(field).strip() for field in REQUIRED_MANIFEST_FIELDS if field != "push_verified" and field != "schema_version"):
        return False
    return isinstance(payload.get("push_verified"), bool)


def _from_manifest(path: Path, server_started_at: str) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return unknown(server_started_at, "deployment_manifest")
    if not _valid_manifest(payload):
        return unknown(server_started_at, "deployment_manifest")
    commit = payload["commit_sha"].strip()
    origin = payload["origin_main_sha"].strip()
    published = payload["push_verified"] is True and commit == origin
    return _public(
        mode="formal",
        status="PUBLISHED" if published else "UNVERIFIED",
        source="deployment_manifest",
        commit_sha=commit,
        branch=payload["branch"].strip(),
        main_sha=payload["main_sha"].strip(),
        origin_main_sha=origin,
        push_verified=payload["push_verified"],
        generated_at=payload["generated_at"].strip(),
        server_started_at=server_started_at,
        dirty=False,
        tag=str(payload.get("tag") or "").strip(),
    )


def _git_snapshot(project_root: Path, server_started_at: str, runner: Callable[[list[str], Path], str]) -> dict:
    try:
        commit = _run(runner, ["git", "rev-parse", "HEAD"], project_root)
        branch = _run(runner, ["git", "symbolic-ref", "--short", "HEAD"], project_root)
    except Exception:
        return unknown(server_started_at, "worktree")
    if not commit:
        return unknown(server_started_at, "worktree")
    if not branch:
        branch = "DETACHED"
    try:
        main_sha = _run(runner, ["git", "rev-parse", "main"], project_root)
    except Exception:
        main_sha = ""
    try:
        origin_sha = _run(runner, ["git", "rev-parse", "origin/main"], project_root)
    except Exception:
        origin_sha = ""
    try:
        dirty = bool(_run(runner, ["git", "status", "--porcelain"], project_root))
    except Exception:
        dirty = None
    try:
        tag = _run(runner, ["git", "describe", "--tags", "--exact-match", "HEAD"], project_root)
    except Exception:
        tag = ""
    return _public(
        mode="preview",
        status="PREVIEW",
        source="worktree",
        commit_sha=commit,
        branch=branch,
        main_sha=main_sha,
        origin_main_sha=origin_sha,
        push_verified=False,
        server_started_at=server_started_at,
        dirty=dirty,
        tag=tag,
    )


def collect_build_info(
    project_root: Path,
    *,
    server_started_at: str = "",
    manifest_path: Path | None = None,
    runner: Callable[[list[str], Path], str] | None = None,
) -> dict:
    """Return safe build identity without mutating the project or Git state."""

    started = server_started_at or _now()
    root = Path(project_root).resolve()
    manifest = Path(manifest_path) if manifest_path else root / "web_desktop" / "runtime_build_info.json"
    command = runner or _default_runner
    try:
        _run(command, ["git", "rev-parse", "--show-toplevel"], root)
    except Exception:
        return _from_manifest(manifest, started)
    return _git_snapshot(root, started, command)
