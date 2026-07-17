from __future__ import annotations

import json
import hashlib
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from .custom_metric_quality import collect_custom_metric_issues


def issue_key(issue: dict) -> str:
    fields = (
        "severity", "date", "area", "issue", "action",
        "target_type", "target_id", "movement_id",
    )
    return json.dumps(
        {field: str(issue.get(field, "")) for field in fields},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _read_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        value = {"acknowledged": {}}
    acknowledged = value.get("acknowledged", {}) if isinstance(value, dict) else {}
    return {"acknowledged": acknowledged if isinstance(acknowledged, dict) else {}}


def collect_issues(database: dict, dictionary: dict, stable_module, state_file: Path) -> dict:
    """Reuse the desktop rules headlessly and add stable keys for Web routing."""
    checker = stable_module.FitnessTrackerApp.__new__(stable_module.FitnessTrackerApp)
    checker.database = database
    checker.movement_dictionary = dictionary
    checker.movement_definitions_by_id, checker.movement_definitions_by_alias = stable_module.movement_definition_index(
        dictionary
    )
    issues = [*checker.collect_data_issues(), *collect_custom_metric_issues(database)]
    acknowledged = _read_state(state_file)["acknowledged"]
    visible = []
    for issue in issues:
        item = dict(issue)
        item["issue_key"] = issue_key(item)
        item["acknowledged"] = item["issue_key"] in acknowledged
        if not item["acknowledged"]:
            visible.append(item)
    return {
        "issues": visible,
        "total": len(issues),
        "acknowledged_count": len(issues) - len(visible),
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
    }


_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
LOGGER = logging.getLogger(__name__)


def _source_fingerprint(paths: tuple[Path, ...], optional_paths: tuple[Path, ...] = ()) -> str:
    digest = hashlib.sha256()
    for path in (*paths, *optional_paths):
        digest.update(str(path.resolve()).encode("utf-8"))
        if path in optional_paths and not path.exists():
            digest.update(b"MISSING")
            continue
        stat = path.stat()
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


class SilentHealthCheck:
    """Read-only Data Check summary cached by the two formal source files."""

    def __init__(self, data_file: Path, dictionary_file: Path, stable_module, state_file: Path | None = None) -> None:
        self.paths = (Path(data_file), Path(dictionary_file))
        self.state_file = Path(state_file) if state_file else None
        self.stable_module = stable_module
        self._lock = threading.RLock()
        self._cached_fingerprint = ""
        self._cached_result: dict | None = None

    def _check(self, fingerprint: str) -> dict:
        database = json.loads(self.paths[0].read_text(encoding="utf-8"))
        dictionary = json.loads(self.paths[1].read_text(encoding="utf-8"))
        checker = self.stable_module.FitnessTrackerApp.__new__(self.stable_module.FitnessTrackerApp)
        checker.database = database
        checker.movement_dictionary = dictionary
        checker.movement_definitions_by_id, checker.movement_definitions_by_alias = self.stable_module.movement_definition_index(
            dictionary
        )
        issues = [*checker.collect_data_issues(), *collect_custom_metric_issues(database)]
        if self.state_file is not None:
            acknowledged = _read_state(self.state_file)["acknowledged"]
            issues = [item for item in issues if issue_key(item) not in acknowledged]
        severities = [str(item.get("severity", "")).lower() for item in issues]
        highest = max(severities, key=lambda value: _SEVERITY_RANK.get(value, 0), default="")
        return {
            "status": "NEEDS_REVIEW" if issues else "OK",
            "issue_count": len(issues),
            "highest_severity": highest.upper() if highest else None,
            "data_fingerprint": fingerprint,
            "checked_at": datetime.now().replace(microsecond=0).isoformat(),
            "destination": "checks",
        }

    def summary(self) -> dict:
        started = time.perf_counter()
        try:
            optional_paths = (self.state_file,) if self.state_file is not None else ()
            fingerprint = _source_fingerprint(self.paths, optional_paths)
            with self._lock:
                if fingerprint == self._cached_fingerprint and self._cached_result is not None:
                    return {**self._cached_result, "cached": True, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
                result = self._check(fingerprint)
                # Do not cache a result across a concurrent formal save.
                if _source_fingerprint(self.paths, optional_paths) != fingerprint:
                    fingerprint = _source_fingerprint(self.paths, optional_paths)
                    result = self._check(fingerprint)
                self._cached_fingerprint = fingerprint
                self._cached_result = result
                return {**result, "cached": False, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}
        except Exception:
            LOGGER.exception("Silent archive health check failed")
            return {
                "status": "UNAVAILABLE",
                "issue_count": None,
                "highest_severity": None,
                "data_fingerprint": None,
                "checked_at": datetime.now().replace(microsecond=0).isoformat(),
                "destination": "checks",
                "cached": False,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }


def acknowledge_issue(state_file: Path, key: str) -> dict:
    state = _read_state(state_file)
    state["acknowledged"][str(key)] = datetime.now().replace(microsecond=0).isoformat()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    temp = state_file.with_name(f"{state_file.name}.tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(state_file)
    return {"acknowledged": True, "issue_key": str(key)}
