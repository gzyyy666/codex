from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
CONFIG_FILE = PROJECT / "PROJECT_STATUS_CONFIG.json"
TEXT_SUFFIXES = {
    ".css", ".html", ".js", ".json", ".md", ".py", ".pyw", ".txt",
    ".wxml", ".wxss", ".xml", ".yaml", ".yml",
}


def run_git(root: Path, *args: str, text: bool = True) -> str | bytes:
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=text,
        encoding="utf-8" if text else None,
    ).strip() if text else subprocess.check_output(
        ["git", "-C", str(root), *args],
    )


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def file_metadata(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False}
    data = path.read_bytes()
    stat = path.stat()
    return {
        "exists": True,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "mtime_utc": datetime.fromtimestamp(
            stat.st_mtime, timezone.utc
        ).isoformat(),
    }


def normalize_text(data: bytes) -> bytes:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def same_deployed_content(relative_path: str, source: bytes, target: bytes) -> bool:
    if Path(relative_path).suffix.lower() in TEXT_SUFFIXES:
        return normalize_text(source) == normalize_text(target)
    return source == target


def deployment_state(git_root: Path, formal: Path, config: dict) -> dict:
    prefix = str(config["project_prefix"]).replace("\\", "/").rstrip("/")
    included = tuple(
        str(item).replace("\\", "/").lstrip("/")
        for item in config.get("deployment_include_prefixes", [])
    )
    excluded = tuple(
        str(item).replace("\\", "/").lstrip("/")
        for item in config.get("excluded_deployment_prefixes", [])
    )
    archive = run_git(git_root, "archive", "--format=tar", "main", prefix, text=False)
    compared = 0
    missing: list[str] = []
    different: list[str] = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle.getmembers():
            if not member.isfile():
                continue
            relative = member.name.removeprefix(f"{prefix}/")
            if (
                relative == member.name
                or (included and not relative.startswith(included))
                or relative.startswith(excluded)
            ):
                continue
            source_file = bundle.extractfile(member)
            source = source_file.read() if source_file else b""
            target = formal / Path(relative)
            compared += 1
            if not target.is_file():
                missing.append(relative)
                continue
            if not same_deployed_content(relative, source, target.read_bytes()):
                different.append(relative)
    return {
        "status": "CURRENT" if not missing and not different else "DRIFT",
        "compared_files": compared,
        "missing": missing,
        "different": different,
    }


def service_state(url: str) -> dict:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/api/health", timeout=1.5) as response:
            return {"available": response.status == 200, "status": response.status, "url": url}
    except (OSError, urllib.error.URLError):
        return {"available": False, "status": None, "url": url}


def build_state() -> dict:
    config = read_json(CONFIG_FILE)
    git_root = Path(
        os.environ.get("FITNESS_LEDGER_MAIN_WORKTREE")
        or config["main_worktree"]
    )
    formal = Path(
        os.environ.get("FITNESS_LEDGER_FORMAL_DIR")
        or config["formal_directory"]
    )
    current_root = Path(run_git(PROJECT, "rev-parse", "--show-toplevel"))
    branch = run_git(current_root, "branch", "--show-current")
    head = run_git(current_root, "rev-parse", "HEAD")
    main = run_git(git_root, "rev-parse", "main")
    origin_main = run_git(git_root, "rev-parse", "origin/main")
    ahead_behind = run_git(git_root, "rev-list", "--left-right", "--count", "origin/main...main").split()
    status_lines = [
        line for line in run_git(current_root, "status", "--porcelain").splitlines()
        if line
    ]
    changed_vs_main = [
        line for line in run_git(current_root, "diff", "--name-status", "main...HEAD").splitlines()
        if line
    ]

    out = formal / "cloud_sync" / "out"
    manifest = read_json(out / "cloudbase_import" / "manifest.json")
    report = read_json(out / "fitness_ledger_cloud_sync_report.json")
    sync = read_json(out / "sync_state.json")
    payload_hash = manifest.get("payload_hash", "")
    sync_hash = sync.get("payload_hash", "")
    cloud_status = (
        "LOCAL_NEWER"
        if payload_hash and payload_hash != sync_hash
        else sync.get("status") or report.get("status") or "UNKNOWN"
    )

    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": str(PROJECT),
        "git": {
            "worktree": str(current_root),
            "branch": branch,
            "head": head,
            "main": main,
            "origin_main": origin_main,
            "main_ahead": int(ahead_behind[1]),
            "main_behind": int(ahead_behind[0]),
            "clean": not status_lines,
            "status": status_lines,
            "changed_vs_main": changed_vs_main,
            "stash": run_git(git_root, "stash", "list").splitlines(),
            "worktrees": run_git(git_root, "worktree", "list").splitlines(),
        },
        "formal": {
            "directory": str(formal),
            "exists": formal.is_dir(),
            "tracker": file_metadata(formal / "data" / "tracker.json"),
            "movement_dictionary": file_metadata(
                formal / "data" / "movement_dictionary.json"
            ),
            "deployment": deployment_state(git_root, formal, config)
            if formal.is_dir()
            else {"status": "MISSING"},
        },
        "cloud_sync": {
            "status": cloud_status,
            "manifest_payload_hash": payload_hash,
            "synced_payload_hash": sync_hash,
            "manifest_latest_record_date": manifest.get("latest_record_date", ""),
            "synced_latest_record_date": sync.get("latest_record_date", ""),
            "last_report_status": report.get("status", ""),
            "last_report_finished_at": report.get("finished_at", ""),
            "cloud_verified": bool(
                (sync.get("cloud_verification") or {}).get("verified")
            ),
        },
        "service": service_state(str(config.get("service_url", ""))),
    }


def write_outputs(state: dict, handoff: bool) -> dict:
    config = read_json(CONFIG_FILE)
    state_dir = Path(
        os.environ.get("FITNESS_LEDGER_STATE_DIR")
        or config["shared_state_directory"]
    )
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "project-runtime-state.json"
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result = {"state_file": str(state_path)}
    if handoff:
        git_state = state["git"]
        handoff_payload = {
            "schema": 1,
            "generated_at": state["generated_at"],
            "branch": git_state["branch"],
            "head": git_state["head"],
            "main": git_state["main"],
            "origin_main": git_state["origin_main"],
            "clean": git_state["clean"],
            "changed_vs_main": git_state["changed_vs_main"],
            "formal_deployment": state["formal"]["deployment"],
            "cloud_sync": state["cloud_sync"],
            "ready_for_git_integration": (
                git_state["clean"]
                and git_state["branch"] != "main"
                and bool(git_state["changed_vs_main"])
            ),
        }
        handoff_path = state_dir / "task-handoff.json"
        handoff_path.write_text(
            json.dumps(handoff_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result["handoff_file"] = str(handoff_path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report live Fitness Ledger Git, formal deployment, data, service, and Cloud Sync state."
    )
    parser.add_argument("--json", action="store_true", help="Print the complete JSON state.")
    parser.add_argument("--write", action="store_true", help="Write the shared runtime-state file.")
    parser.add_argument("--handoff", action="store_true", help="Write the shared task handoff file.")
    args = parser.parse_args()
    state = build_state()
    outputs = write_outputs(state, args.handoff) if args.write or args.handoff else {}
    if args.json:
        print(json.dumps({**state, "outputs": outputs}, ensure_ascii=False, indent=2))
        return
    print(
        f"Git {state['git']['branch']} {state['git']['head'][:12]} "
        f"(main {state['git']['main'][:12]}, origin {state['git']['origin_main'][:12]})"
    )
    print(
        f"Formal {state['formal']['deployment']['status']} · "
        f"Cloud {state['cloud_sync']['status']} · "
        f"Service {'UP' if state['service']['available'] else 'DOWN'}"
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
