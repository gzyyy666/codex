"""Generate a formal Web deployment identity manifest from a real Git checkout.

The caller must explicitly pass ``--push-verified`` after independently
confirming that the deployment commit was pushed to ``origin/main``.  This
tool never fetches, pushes, merges, tags, or writes project data.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def git(args: list[str], repo: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        shell=False,
    )
    return result.stdout.strip()


def build_manifest(repo: Path, *, push_verified: bool, tag: str = "") -> dict:
    commit = git(["rev-parse", "HEAD"], repo)
    branch = git(["symbolic-ref", "--short", "HEAD"], repo)
    main_sha = git(["rev-parse", "main"], repo)
    origin_sha = git(["rev-parse", "origin/main"], repo)
    if not all((commit, branch, main_sha, origin_sha)):
        raise RuntimeError("HEAD, branch, main and origin/main are all required.")
    if push_verified and commit != origin_sha:
        raise RuntimeError("--push-verified requires HEAD to equal origin/main.")
    return {
        "schema_version": 1,
        "mode": "formal",
        "commit_sha": commit,
        "branch": branch,
        "main_sha": main_sha,
        "origin_main_sha": origin_sha,
        "push_verified": bool(push_verified),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **({"tag": tag} if tag else {}),
    }


def atomic_write(path: Path, payload: dict) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a formal Fitness Ledger Web runtime build manifest.")
    parser.add_argument("--output", required=True, type=Path, help="Manifest output path")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Git checkout to inspect")
    parser.add_argument("--push-verified", action="store_true", help="Explicitly confirm HEAD was pushed to origin/main")
    parser.add_argument("--tag", default="", help="Optional annotated/release tag")
    args = parser.parse_args()
    manifest = build_manifest(args.repo.resolve(), push_verified=args.push_verified, tag=args.tag.strip())
    atomic_write(args.output, manifest)
    print(json.dumps({"output": str(args.output.resolve()), "commit_sha": manifest["commit_sha"], "push_verified": manifest["push_verified"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
