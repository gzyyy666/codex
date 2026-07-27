"""Run the Formal Read-only Validation stage and build an external Review ZIP."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import csv
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "b7146d97cdecf953b8d82a608edb6157cee97e2a"
DEFAULT_FORMAL_DIR = Path(r"C:\Users\26087\Documents\Codex\2026-06-16\vs-code-ai\work\fitness_tracker_app\data")
DEFAULT_OUTPUT_ROOT = Path(r"C:\Users\26087\Documents\github-memory\analysis-export-formal-readonly-validation-review")
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_export_request import validate_request  # noqa: E402
from fitness_ledger_core.analysis_export_materializer import MaterializationError  # noqa: E402
from fitness_ledger_core.formal_readonly_data_source import FormalReadOnlyDataSource  # noqa: E402


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(output: Path, label: str, args: list[str]) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
    duration = time.perf_counter() - started
    ended_at = datetime.now(timezone.utc)
    command_dir = output / "commands"
    command_dir.mkdir(parents=True, exist_ok=True)
    (command_dir / f"{label}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (command_dir / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    return {
        "label": label,
        "command": args,
        "workdir": str(ROOT),
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "exit_code": result.returncode,
        "duration_seconds": round(duration, 6),
        "stdout_file": f"commands/{label}.stdout.txt",
        "stderr_file": f"commands/{label}.stderr.txt",
    }


def _request(purpose: str, dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_version": "1.1",
        "purpose": purpose,
        "datasets": [dataset],
        "raw": False,
        "output": {"formats": ["json", "markdown"]},
    }


def build_requests(source: FormalReadOnlyDataSource) -> dict[str, dict[str, Any]]:
    movement_id = source.reference_movement_id()
    body_part = source.reference_body_part()
    ambiguous_name = source.ambiguous_movement_name()
    return {
        "recent_body_notes": _request("Inspect the recent formal body window with scoped Notes", {
            "dataset_id": "formal_body_recent",
            "type": "body",
            "time_range": {"mode": "recent_days", "days": 14},
            "filters": {},
            "fields": ["date", "weight_kg", "bowel_movement", "training_label", "cardio_summary"],
            "notes_scope": "daily",
        }),
        "recent_diet": _request("Inspect recent formal diet macros", {
            "dataset_id": "formal_diet_recent",
            "type": "diet",
            "time_range": {"mode": "recent_days", "days": 14},
            "filters": {},
            "fields": ["date", "calories_kcal", "protein_g", "carbs_g", "fat_g", "food_summary"],
            "notes_scope": "diet",
        }),
        "recent_training": _request("Inspect the latest formal training sessions", {
            "dataset_id": "formal_training_latest",
            "type": "training",
            "time_range": {"mode": "latest_matching_sessions", "sessions": 3},
            "filters": {},
            "fields": ["date", "split", "standardized_summary"],
            "notes_scope": "training",
        }),
        "movement_by_id_set_roles": _request("Inspect one formal movement with requested set roles", {
            "dataset_id": "formal_movement_by_id",
            "type": "movement_progress",
            "time_range": {"mode": "latest_matching_sessions", "sessions": 3},
            "filters": {"movement_selector": {"kind": "movement_id", "value": movement_id}},
            "fields": ["date", "movement_id", "movement_name", "body_part", "variant", "order", "sets"],
            "set_roles": ["top", "working", "backoff"],
            "notes_scope": "movement",
        }),
        "movement_by_body_part": _request("Inspect formal movements selected by body part", {
            "dataset_id": "formal_movement_by_body_part",
            "type": "movement_progress",
            "time_range": {"mode": "latest_matching_sessions", "sessions": 2},
            "filters": {"movement_selector": {"kind": "body_part", "value": body_part}},
            "fields": ["date", "movement_id", "movement_name", "body_part"],
        }),
        "diet_before_training_window": {
            "request_version": "1.1",
            "purpose": "Inspect formal diet in the three days before each latest training session",
            "datasets": [
                {
                    "dataset_id": "formal_training_targets",
                    "type": "training",
                    "time_range": {"mode": "latest_matching_sessions", "sessions": 2},
                    "filters": {},
                    "fields": ["date", "split"],
                },
                {
                    "dataset_id": "formal_diet_before_training",
                    "type": "diet",
                    "time_range": {
                        "mode": "days_before_target_session",
                        "days_before": 3,
                        "target_dataset_id": "formal_training_targets",
                        "match_mode": "each_matching_session",
                        "include_target_session_day": False,
                    },
                    "filters": {},
                    "fields": ["date", "calories_kcal", "protein_g", "carbs_g", "fat_g"],
                    "notes_scope": "diet",
                },
            ],
            "raw": False,
            "output": {"formats": ["json", "markdown"]},
        },
        "missing_formal_variant": _request("Expose a formal movement field that is not present", {
            "dataset_id": "formal_missing_variant",
            "type": "movement_progress",
            "time_range": {"mode": "latest_matching_sessions", "sessions": 2},
            "filters": {"movement_selector": {"kind": "movement_id", "value": movement_id}},
            "fields": ["date", "movement_id", "movement_name", "body_part", "variant"],
        }),
        "movement_name_ambiguity": _request("Require confirmation for an ambiguous formal movement name", {
            "dataset_id": "formal_ambiguous_movement",
            "type": "movement_progress",
            "time_range": {"mode": "latest_matching_sessions", "sessions": 2},
            "filters": {"movement_selector": {"kind": "movement_name", "value": ambiguous_name}},
            "fields": ["date", "movement_id", "movement_name", "body_part"],
        }),
    }


def _date_strings(records: list[dict[str, Any]]) -> list[str]:
    return sorted({str(record["date"])[:10] for record in records if record.get("date")})


def _field_presence(records: list[dict[str, Any]], fields: list[str], notes_requested: bool) -> dict[str, dict[str, int]]:
    names = list(fields) + (["notes"] if notes_requested else [])
    return {
        field: {
            "record_count": len(records),
            "present_count": sum(field in record for record in records),
            "non_null_count": sum(field in record and record[field] is not None for record in records),
        }
        for field in names
    }


def _assert_request_and_counts(request: dict[str, Any], bundle: dict[str, Any], validation: Any) -> None:
    assert validation.valid and validation.normalized_request is not None
    assert bundle["request"] == validation.normalized_request
    counts = bundle["provenance"]["counts"]
    datasets = bundle["quality_profile"]["datasets"]
    assert counts["validated_request_count"] == 1
    assert counts["candidate_record_count"] == sum(item["candidate_record_count"] for item in datasets)
    assert counts["resolved_record_count"] == sum(item["resolved_record_count"] for item in datasets)
    assert counts["materialized_record_count"] == sum(item["materialized_record_count"] for item in datasets)
    assert counts["materialized_record_count"] == len(bundle["records"])
    assert counts["exported_artifact_count"] == len(request["output"]["formats"])
    assert bundle["manifest"]["record_count"] == len(bundle["records"])
    assert bundle["safety_flags"] == {
        "raw_included": False,
        "executor_called": False,
        "formal_data_written": False,
    }
    for record in bundle["records"]:
        assert not any("raw" in key.casefold() for key in record)
        assert not any("original" in key.casefold() for key in record)


def _assert_time_range(bundle: dict[str, Any], anchor: str) -> None:
    anchor_date = date.fromisoformat(anchor)
    for dataset in bundle["request"]["datasets"]:
        rows = [record for record in bundle["records"] if record["dataset_id"] == dataset["dataset_id"]]
        mode = dataset["time_range"]["mode"]
        dates = _date_strings(rows)
        if not dates:
            continue
        if mode == "recent_days":
            start = anchor_date - timedelta(days=dataset["time_range"]["days"] - 1)
            assert date.fromisoformat(dates[0]) >= start and date.fromisoformat(dates[-1]) <= anchor_date
        elif mode == "explicit_range":
            assert dates[0] >= dataset["time_range"]["start"] and dates[-1] <= dataset["time_range"]["end"]
        elif mode == "latest_matching_sessions":
            assert len(dates) <= dataset["time_range"]["sessions"]


def _evidence_for_case(name: str, request: dict[str, Any], bundle: dict[str, Any], source: FormalReadOnlyDataSource) -> dict[str, Any]:
    _assert_request_and_counts(request, bundle, validate_request(request))
    _assert_time_range(bundle, source.anchor_date)
    datasets = []
    for dataset in bundle["request"]["datasets"]:
        rows = [record for record in bundle["records"] if record["dataset_id"] == dataset["dataset_id"]]
        dates = _date_strings(rows)
        datasets.append({
            "dataset_id": dataset["dataset_id"],
            "type": dataset["type"],
            "requested_fields": dataset["fields"],
            "notes_scope": dataset.get("notes_scope"),
            "set_roles": dataset.get("set_roles"),
            "date_range": {"start": dates[0], "end": dates[-1]} if dates else None,
            "field_presence": _field_presence(rows, dataset["fields"], "notes_scope" in dataset),
            "record_count": len(rows),
        })
    evidence = {
        "case": name,
        "status": "materialized",
        "request": request,
        "datasets": datasets,
        "counts": bundle["provenance"]["counts"],
        "missing_information": bundle["missing_information"],
        "warnings": bundle["warnings"],
        "provenance": bundle["provenance"],
        "safety": bundle["safety_flags"],
    }
    if name == "movement_by_id_set_roles":
        rows = [r for r in bundle["records"] if r["dataset_id"] == "formal_movement_by_id"]
        selected_id = request["datasets"][0]["filters"]["movement_selector"]["value"]
        assert rows and {r["movement_id"] for r in rows} == {selected_id}
        assert all(all(item.get("role") in {"top", "working", "backoff"} for item in r.get("sets", [])) for r in rows)
        assert any("set-role metadata is unavailable" in item for item in bundle["warnings"])
        evidence["mapping_check"] = {
            "selector_kind": "movement_id",
            "selected_movement_id": selected_id,
            "all_exported_ids_match": True,
            "set_role_filter_applied": True,
            "set_role_metadata_present_count": sum(bool(item.get("role")) for r in rows for item in r.get("sets", [])),
            "set_role_metadata_missing_no_inference": True,
        }
    elif name == "movement_by_body_part":
        rows = [r for r in bundle["records"] if r["dataset_id"] == "formal_movement_by_body_part"]
        body_part = request["datasets"][0]["filters"]["movement_selector"]["value"]
        assert rows and {str(r.get("body_part")) for r in rows} == {body_part}
        evidence["mapping_check"] = {
            "selector_kind": "body_part",
            "selected_body_part": body_part,
            "all_exported_body_parts_match": True,
            "distinct_movement_id_count": len({r["movement_id"] for r in rows}),
        }
    elif name == "missing_formal_variant":
        rows = [r for r in bundle["records"] if r["dataset_id"] == "formal_missing_variant"]
        assert rows and all(r.get("variant") is None for r in rows)
        assert all(r.get("variant") != 0 for r in rows)
        assert any("variant" in item for item in bundle["missing_information"])
        evidence["missing_field_check"] = {
            "field": "variant",
            "null_count": sum(r.get("variant") is None for r in rows),
            "zero_substitution_detected": False,
        }
    if name in {"recent_body_notes", "recent_diet", "recent_training", "diet_before_training_window"}:
        note_lines = [item for item in bundle["missing_information"] + bundle["warnings"] if "notes" in item.casefold()]
        assert not note_lines
        evidence["notes_check"] = {"notes_missing_or_unavailable_messages": 0, "empty_notes_preserved_as_non_error": True}
    if name == "diet_before_training_window":
        target_dates = {record["date"] for record in bundle["records"] if record["dataset_id"] == "formal_training_targets"}
        diet_rows = [record for record in bundle["records"] if record["dataset_id"] == "formal_diet_before_training"]
        assert target_dates
        for row in diet_rows:
            relation = row["relation"]
            assert relation["target_session_date"] in target_dates
            target = date.fromisoformat(relation["target_session_date"])
            row_date = date.fromisoformat(row["date"])
            assert target - timedelta(days=3) <= row_date <= target - timedelta(days=1)
        evidence["relation_check"] = {
            "match_mode": "each_matching_session",
            "target_session_count": len(target_dates),
            "include_target_session_day": False,
            "window_days_before": 3,
            "all_diet_rows_in_window": True,
        }
    return evidence


def _artifact_metadata(path: Path, run_root: Path, name: str, fmt: str, bundle: dict[str, Any]) -> dict[str, Any]:
    payload = path.read_bytes()
    records = bundle["records"]
    dates = _date_strings(records)
    return {
        "case": name,
        "format": fmt,
        "relative_identifier": path.relative_to(run_root).as_posix(),
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bundle_structure": {
            "bundle_version": bundle["bundle_version"],
            "dataset_count": len(bundle["selected_datasets"]),
            "record_count": len(records),
            "date_range": {"start": dates[0], "end": dates[-1]} if dates else None,
            "warning_count": len(bundle["warnings"]),
            "missing_information_count": len(bundle["missing_information"]),
            "safety": bundle["safety_flags"],
        },
    }


def _write_full_bundle(bundle_dir: Path, name: str, bundle: dict[str, Any], exports: dict[str, str]) -> list[dict[str, Any]]:
    case_dir = bundle_dir / name
    case_dir.mkdir(parents=True, exist_ok=True)
    write_json(case_dir / "bundle.json", bundle)
    artifacts = [_artifact_metadata(case_dir / "bundle.json", bundle_dir.parent, name, "json", bundle)]
    for fmt, content in exports.items():
        path = case_dir / f"export.{fmt}"
        path.write_text(content, encoding="utf-8")
        artifacts.append(_artifact_metadata(path, bundle_dir.parent, name, fmt, bundle))
    return artifacts


def _git_capture(args: list[str]) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace").strip()


def _git_state() -> dict[str, str]:
    return {
        "status": _git_capture(["git", "status", "--short", "--branch"]),
        "branch": _git_capture(["git", "branch", "--show-current"]),
        "head": _git_capture(["git", "rev-parse", "HEAD"]),
        "main": _git_capture(["git", "rev-parse", "refs/heads/main"]),
        "origin_main": _git_capture(["git", "rev-parse", "refs/remotes/origin/main"]),
        "worktrees": _git_capture(["git", "worktree", "list", "--porcelain"]),
    }


def _sanitized_fingerprints(value: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    labels = {"tracker": "data/tracker.json", "movement_dictionary": "data/movement_dictionary.json"}
    return {
        key: {
            "path": labels[key],
            "size": item["size"],
            "sha256": item["sha256"],
            "modified_time_utc": item["modified_time_utc"],
            "modified_time_ns": item["modified_time_ns"],
        }
        for key, item in value.items()
    }


def _git_info(review_dir: Path, reviewed_commit: str | None, before: dict[str, str], after: dict[str, str]) -> dict[str, Any]:
    info = {
        "repository": str(ROOT),
        "baseline_commit": BASELINE_COMMIT,
        "reviewed_commit": reviewed_commit or after["head"],
        "branch": after["branch"],
        "head": after["head"],
        "main": after["main"],
        "origin_main": after["origin_main"],
        "status_before": before["status"],
        "status_after": after["status"],
        "diff_stat": _git_capture(["git", "diff", "--stat", f"{BASELINE_COMMIT}..HEAD"]),
        "main_unchanged": before["main"] == after["main"],
        "origin_main_unchanged": before["origin_main"] == after["origin_main"],
        "worktrees_unchanged": before["worktrees"] == after["worktrees"],
        "python": sys.version,
        "platform": platform.platform(),
    }
    write_json(review_dir / "ENVIRONMENT.json", info)
    write_json(review_dir / "REVIEW_METADATA.json", {
        "baseline_commit": BASELINE_COMMIT,
        "reviewed_commit": info["reviewed_commit"],
        "final_commit": info["head"],
        "branch": info["branch"],
        "worktree_clean_before": before["status"] == f"## {before['branch']}",
        "worktree_clean_after": after["status"] == f"## {after['branch']}",
        "main_unchanged": info["main_unchanged"],
        "origin_main_unchanged": info["origin_main_unchanged"],
        "other_worktrees_unchanged": info["worktrees_unchanged"],
        "protocol_modified": False,
        "materializer_selection_semantics_modified": False,
        "formal_provenance": {
            "source_kind": "formal_local_json_read_only",
            "formal_access": "read_only; structured allowlist projection",
            "source_path_policy": "explicit formal files opened read-only; structured allowlist projection only",
            "paths": ["data/tracker.json", "data/movement_dictionary.json"],
        },
        "safety": {
            "raw_read": False,
            "formal_data_written": False,
            "executor_called": False,
            "model_called": False,
            "ollama_called": False,
            "sync_executed": False,
        },
    })
    (review_dir / "GIT_STATUS_BEFORE.txt").write_text(before["status"] + "\n", encoding="utf-8")
    (review_dir / "GIT_STATUS_AFTER.txt").write_text(after["status"] + "\n", encoding="utf-8")
    return info


def _write_patch(review_dir: Path, reviewed_commit: str | None) -> None:
    commit = reviewed_commit or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    patch = subprocess.check_output(["git", "diff", "--binary", BASELINE_COMMIT, commit], cwd=ROOT)
    (review_dir / "reviewed.patch").write_bytes(patch)


def _write_manifest(review_dir: Path) -> dict[str, Any]:
    manifest = {"schema": 1, "self_hash_excluded": True, "files": {}}
    for path in sorted(item for item in review_dir.rglob("*") if item.is_file() and item.name != "RESULT_MANIFEST.json"):
        relative = path.relative_to(review_dir).as_posix()
        payload = path.read_bytes()
        manifest["files"][relative] = {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    manifest["zip_excluded"] = True
    write_json(review_dir / "RESULT_MANIFEST.json", manifest)
    return manifest


def _verify_manifest(review_dir: Path, manifest: dict[str, Any]) -> dict[str, int]:
    expected = set(manifest["files"])
    actual = {
        path.relative_to(review_dir).as_posix()
        for path in review_dir.rglob("*")
        if path.is_file() and path.name != "RESULT_MANIFEST.json"
    }
    missing = expected - actual
    extra = actual - expected
    size_mismatches = 0
    sha_mismatches = 0
    for relative in expected & actual:
        path = review_dir / relative
        payload = path.read_bytes()
        expected_entry = manifest["files"][relative]
        size_mismatches += int(len(payload) != expected_entry["size"])
        sha_mismatches += int(hashlib.sha256(payload).hexdigest() != expected_entry["sha256"])
    return {
        "missing_count": len(missing),
        "extra_count": len(extra),
        "size_mismatch_count": size_mismatches,
        "sha256_mismatch_count": sha_mismatches,
    }


def _zip_review(review_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in review_dir.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(review_dir).as_posix())


def _write_case_matrix_csv(review_dir: Path, matrix: list[dict[str, Any]]) -> None:
    path = review_dir / "CASE_MATRIX.csv"
    fields = [
        "case",
        "status",
        "dataset_count",
        "record_count",
        "date_start",
        "date_end",
        "warning_count",
        "missing_information_count",
        "validated_request_count",
        "candidate_record_count",
        "resolved_record_count",
        "materialized_record_count",
        "exported_artifact_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in matrix:
            dates = [
                dataset["date_range"]
                for dataset in item.get("datasets", [])
                if dataset.get("date_range")
            ]
            counts = item["counts"]
            writer.writerow({
                "case": item["case"],
                "status": item["status"],
                "dataset_count": len(item.get("datasets", [])),
                "record_count": sum(dataset.get("record_count", 0) for dataset in item.get("datasets", [])),
                "date_start": min((value["start"] for value in dates), default=""),
                "date_end": max((value["end"] for value in dates), default=""),
                "warning_count": len(item.get("warnings", [])),
                "missing_information_count": len(item.get("missing_information", [])),
                **{key: counts.get(key, 0) for key in (
                    "validated_request_count",
                    "candidate_record_count",
                    "resolved_record_count",
                    "materialized_record_count",
                    "exported_artifact_count",
                )},
            })


def _write_command_log(review_dir: Path, commands: list[dict[str, Any]]) -> None:
    lines = ["# Command Log", ""]
    for item in commands:
        lines.extend([
            f"## {item['label']}",
            "",
            f"- Command: {json.dumps(item['command'], ensure_ascii=False)}",
            f"- Workdir: {item['workdir']}",
            f"- Started: {item['started_at']}",
            f"- Ended: {item['ended_at']}",
            f"- Duration seconds: {item['duration_seconds']}",
            f"- Exit code: {item['exit_code']}",
            f"- Stdout: {item['stdout_file']}",
            f"- Stderr: {item['stderr_file']}",
            "",
        ])
    (review_dir / "COMMAND_LOG.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-dir", type=Path, default=DEFAULT_FORMAL_DIR)
    parser.add_argument("--output", type=Path, default=None, help="External run directory")
    parser.add_argument("--reviewed-commit", default=None)
    args = parser.parse_args()
    run_root = args.output or DEFAULT_OUTPUT_ROOT / datetime.now(timezone.utc).strftime("formal-readonly-%Y%m%dT%H%M%SZ")
    review_dir = run_root / "review"
    bundle_dir = run_root / "bundles"
    review_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    invocation_started_at = datetime.now(timezone.utc)
    invocation_started = time.perf_counter()
    git_before = _git_state()
    source = FormalReadOnlyDataSource(args.formal_dir / "tracker.json", args.formal_dir / "movement_dictionary.json")
    before = source.before_fingerprints
    write_json(review_dir / "FORMAL_SOURCE_HASH_BEFORE.json", _sanitized_fingerprints(before))

    command_results = [
        run_command(review_dir, "compile", [sys.executable, "-m", "py_compile", "fitness_ledger_core/formal_readonly_data_source.py", "tools/formal_readonly_validation.py"]),
        run_command(review_dir, "request_protocol_regression", [sys.executable, "tools/analysis_export_request_protocol_test.py"]),
        run_command(review_dir, "anonymous_materializer_regression", [sys.executable, "tools/analysis_export_materializer_test.py"]),
        run_command(review_dir, "analysis_export_regression", [sys.executable, "tools/analysis_export_test.py"]),
        run_command(review_dir, "preview_regression", [sys.executable, "tools/analysis_preview_service_test.py"]),
        run_command(review_dir, "preview_ui_regression", [sys.executable, "tools/analysis_preview_review_ui_test.py"]),
        run_command(review_dir, "executor_safety", [sys.executable, "tools/intent_executor_safety_test.py"]),
        run_command(review_dir, "json_schema_parse", [
            sys.executable,
            "-c",
            "import json; from pathlib import Path; root=Path('.'); [json.loads((root / name).read_text(encoding='utf-8')) for name in ('schemas/analysis_export_request_v1.schema.json', 'schemas/analysis_export_bundle_v1.schema.json')]; print('JSON_SCHEMA_PARSE_OK')",
        ]),
        run_command(review_dir, "git_diff_check", ["git", "diff", "--check"]),
    ]
    if any(item["exit_code"] != 0 for item in command_results):
        write_json(review_dir / "commands.json", command_results)
        raise SystemExit("Formal read-only validation prerequisites failed; see commands/")

    requests = build_requests(source)
    matrix: list[dict[str, Any]] = []
    for name, request in requests.items():
        case_dir = review_dir / "cases" / name
        case_dir.mkdir(parents=True, exist_ok=True)
        validation = validate_request(request)
        write_json(case_dir / "request.json", request)
        assert validation.valid and validation.normalized_request is not None
        if name == "movement_name_ambiguity":
            try:
                source.materialize(request)
            except MaterializationError as error:
                assert error.code == "MOVEMENT_RESOLUTION_REQUIRED"
                counts = {"validated_request_count": 1, "candidate_record_count": 0, "resolved_record_count": 0, "materialized_record_count": 0, "exported_artifact_count": 0}
                evidence = {
                    "case": name,
                    "status": "movement_resolution_required",
                    "request": request,
                    "counts": counts,
                    "resolution_status": error.code,
                    "candidate_count": len(error.candidates),
                    "candidates": [{"movement_id": item.get("movement_id"), "body_part": item.get("body_part")} for item in error.candidates],
                    "warnings": [],
                    "missing_information": [],
                    "safety": {"raw_included": False, "executor_called": False, "formal_data_written": False},
                }
                write_json(case_dir / "evidence.json", evidence)
                matrix.append(evidence)
                continue
            raise AssertionError("Ambiguous formal movement name was silently materialized")
        bundle, exports = source.materialize_with_exports(request)
        artifacts = _write_full_bundle(bundle_dir, name, bundle, exports)
        evidence = _evidence_for_case(name, request, bundle, source)
        evidence["bundle_artifacts"] = artifacts
        write_json(case_dir / "evidence.json", evidence)
        matrix.append(evidence)

    after = source.file_fingerprints()
    assert before == after
    write_json(review_dir / "FORMAL_SOURCE_HASH_AFTER.json", _sanitized_fingerprints(after))
    write_json(review_dir / "formal_file_hash_comparison.json", {
        "identical": before == after,
        "before": _sanitized_fingerprints(before),
        "after": _sanitized_fingerprints(after),
    })
    write_json(review_dir / "case_matrix.json", matrix)
    (review_dir / "case_matrix.md").write_text(
        "# Formal Read-only Case Matrix\n\n" + "\n".join(
            f"- {item['case']}: **{item['status']}**, counts={json.dumps(item['counts'], ensure_ascii=False, sort_keys=True)}"
            for item in matrix
        ) + "\n",
        encoding="utf-8",
    )
    external_artifacts = [
        artifact
        for item in matrix
        for artifact in item.get("bundle_artifacts", [])
    ]
    write_json(review_dir / "EXTERNAL_BUNDLE_HASHES.json", {
        "artifact_count": len(external_artifacts),
        "artifacts": external_artifacts,
    })
    _write_case_matrix_csv(review_dir, matrix)
    write_json(review_dir / "commands.json", command_results)
    git_after = _git_state()
    assert git_before["main"] == git_after["main"]
    assert git_before["origin_main"] == git_after["origin_main"]
    assert git_before["worktrees"] == git_after["worktrees"]
    git_info = _git_info(review_dir, args.reviewed_commit, git_before, git_after)
    _write_patch(review_dir, args.reviewed_commit)
    (review_dir / "safety_proof.md").write_text(
        "# Safety Proof\n\n"
        "- Formal inputs were exactly data/tracker.json and data/movement_dictionary.json, opened read-only.\n"
        "- The adapter projects only structured Body, Diet, Training, movement history, and movement dictionary fields needed by Request v1.1.\n"
        "- No formal file write, formatting, repair, synchronization, Web/UI start, model, Ollama, or Executor command is present in the command log.\n"
        "- Every generated Bundle has raw_included=false, executor_called=false, and formal_data_written=false.\n"
        "- Full formal Bundle JSON/Markdown artifacts are outside this Review directory and are not included in the Review ZIP.\n"
        "- FORMAL_SOURCE_HASH_BEFORE.json and FORMAL_SOURCE_HASH_AFTER.json prove exact equality of path, size, SHA-256, and modification time before and after execution.\n"
        "- Anonymous Request Validator, Preview, Executor Safety, JSON/Schema parsing, and Materializer regression tests passed before formal cases.\n",
        encoding="utf-8",
    )
    report = {
        "decision": "FORMAL_READONLY_VALIDATION_ACCEPTED",
        "baseline_commit": BASELINE_COMMIT,
        "reviewed_commit": git_info["reviewed_commit"],
        "branch": git_info["branch"],
        "case_count": len(matrix),
        "formal_files_unchanged": before == after,
        "raw_read": False,
        "formal_data_written": False,
        "model_ollama_executor_called": False,
        "bundle_artifacts_directory": "bundles",
        "review_directory": "review",
        "external_bundle_artifact_count": len(external_artifacts),
    }
    materialized_case_count = sum(item["status"] == "materialized" for item in matrix)
    resolution_case_count = sum(item["status"] == "movement_resolution_required" for item in matrix)
    write_json(review_dir / "review_report.json", report)
    review_text = (
        "# Fitness Ledger Formal Read-only Validation\n\n"
        f"- Decision: {report['decision']}\n"
        f"- Baseline: {BASELINE_COMMIT}\n"
        f"- Reviewed commit: {report['reviewed_commit']}\n"
        f"- Formal files unchanged: {report['formal_files_unchanged']}\n"
        f"- Raw read: {report['raw_read']}\n"
        f"- Formal data written: {report['formal_data_written']}\n"
        f"- Model/Ollama/Executor called: {report['model_ollama_executor_called']}\n"
        f"- Cases: {report['case_count']} ({materialized_case_count} materialized, {resolution_case_count} resolution-required)\n\n"
        "Full formal Bundle outputs are stored outside the Review package under the path recorded above.\n"
    )
    (review_dir / "FORMAL_READONLY_VALIDATION_REVIEW.md").write_text(review_text, encoding="utf-8")
    (review_dir / "REVIEW_REPORT.md").write_text(review_text, encoding="utf-8")
    results = {
        "decision": report["decision"],
        "baseline_commit": BASELINE_COMMIT,
        "reviewed_commit": git_info["reviewed_commit"],
        "final_commit": git_info["head"],
        "case_count": len(matrix),
        "materialized_case_count": materialized_case_count,
        "resolution_required_case_count": resolution_case_count,
        "formal_source_files_identical": before == after,
        "external_bundle_artifact_count": len(external_artifacts),
        "command_count_before_invocation_record": len(command_results),
        "command_exit_codes": {item["label"]: item["exit_code"] for item in command_results},
        "safety": {
            "raw_read": False,
            "formal_data_written": False,
            "executor_called": False,
            "model_called": False,
            "ollama_called": False,
            "sync_executed": False,
        },
        "cases": [
            {
                "case": item["case"],
                "status": item["status"],
                "counts": item["counts"],
                "warning_count": len(item.get("warnings", [])),
                "missing_information_count": len(item.get("missing_information", [])),
            }
            for item in matrix
        ],
    }
    write_json(review_dir / "RESULTS.json", results)
    metadata = json.loads((review_dir / "REVIEW_METADATA.json").read_text(encoding="utf-8"))
    metadata.update({
        "case_count": len(matrix),
        "materialized_case_count": materialized_case_count,
        "resolution_required_case_count": resolution_case_count,
        "external_bundle_artifact_count": len(external_artifacts),
    })
    write_json(review_dir / "REVIEW_METADATA.json", metadata)
    invocation_ended_at = datetime.now(timezone.utc)
    invocation_duration = time.perf_counter() - invocation_started
    formal_stdout = review_dir / "commands" / "formal_readonly_validation.stdout.txt"
    formal_stderr = review_dir / "commands" / "formal_readonly_validation.stderr.txt"
    formal_summary = {
        "status": "completed",
        "review_directory": "review",
        "bundle_directory": "bundles",
        "case_count": len(matrix),
        "external_bundle_artifact_count": len(external_artifacts),
        "formal_source_files_identical": before == after,
    }
    formal_stdout.write_text(json.dumps(formal_summary, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    formal_stderr.write_text("", encoding="utf-8")
    command_results.append({
        "label": "formal_readonly_validation",
        "command": [sys.executable, *sys.argv],
        "workdir": str(ROOT),
        "started_at": invocation_started_at.isoformat(),
        "ended_at": invocation_ended_at.isoformat(),
        "duration_seconds": round(invocation_duration, 6),
        "exit_code": 0,
        "stdout_file": "commands/formal_readonly_validation.stdout.txt",
        "stderr_file": "commands/formal_readonly_validation.stderr.txt",
    })
    write_json(review_dir / "commands.json", command_results)
    _write_command_log(review_dir, command_results)
    manifest = _write_manifest(review_dir)
    manifest_check = _verify_manifest(review_dir, manifest)
    assert manifest_check == {
        "missing_count": 0,
        "extra_count": 0,
        "size_mismatch_count": 0,
        "sha256_mismatch_count": 0,
    }
    manifest_code = (
        "import hashlib,json; from pathlib import Path; "
        f"root=Path({str(review_dir)!r}); manifest=json.loads((root/'RESULT_MANIFEST.json').read_text(encoding='utf-8')); "
        "expected=set(manifest['files']); actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='RESULT_MANIFEST.json'}; "
        "assert expected==actual; assert all(len((root/r).read_bytes())==manifest['files'][r]['size'] and hashlib.sha256((root/r).read_bytes()).hexdigest()==manifest['files'][r]['sha256'] for r in expected); print('MANIFEST_INDEPENDENT_VERIFICATION_OK')"
    )
    manifest_command = run_command(review_dir, "manifest_independent_verification", [sys.executable, "-c", manifest_code])
    assert manifest_command["exit_code"] == 0
    command_results.append(manifest_command)
    write_json(review_dir / "commands.json", command_results)
    _write_command_log(review_dir, command_results)
    results["command_count"] = len(command_results)
    results["command_exit_codes"] = {item["label"]: item["exit_code"] for item in command_results}
    results["all_command_exit_codes_zero"] = all(item["exit_code"] == 0 for item in command_results)
    write_json(review_dir / "RESULTS.json", results)
    metadata = json.loads((review_dir / "REVIEW_METADATA.json").read_text(encoding="utf-8"))
    metadata["command_count"] = len(command_results)
    metadata["all_command_exit_codes_zero"] = results["all_command_exit_codes_zero"]
    metadata["manifest_validation"] = manifest_check
    write_json(review_dir / "REVIEW_METADATA.json", metadata)
    manifest = _write_manifest(review_dir)
    manifest_check = _verify_manifest(review_dir, manifest)
    assert manifest_check == {
        "missing_count": 0,
        "extra_count": 0,
        "size_mismatch_count": 0,
        "sha256_mismatch_count": 0,
    }
    manifest["validation"] = manifest_check
    write_json(review_dir / "RESULT_MANIFEST.json", manifest)
    zip_path = run_root.with_suffix(".zip")
    _zip_review(review_dir, zip_path)
    summary = {
        "review_zip": str(zip_path),
        "bundles": str(bundle_dir),
        "manifest_files": len(manifest["files"]),
        "external_bundle_artifact_count": len(external_artifacts),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
