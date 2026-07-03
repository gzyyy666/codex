from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


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
    issues = checker.collect_data_issues()
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


def acknowledge_issue(state_file: Path, key: str) -> dict:
    state = _read_state(state_file)
    state["acknowledged"][str(key)] = datetime.now().replace(microsecond=0).isoformat()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    temp = state_file.with_name(f"{state_file.name}.tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(state_file)
    return {"acknowledged": True, "issue_key": str(key)}
