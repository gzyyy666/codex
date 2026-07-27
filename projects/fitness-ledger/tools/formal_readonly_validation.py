"""Run the Formal Read-only Validation stage and build an external Review ZIP."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
    started = time.perf_counter()
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
    duration = time.perf_counter() - started
    command_dir = output / "commands"
    command_dir.mkdir(parents=True, exist_ok=True)
    (command_dir / f"{label}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (command_dir / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    return {
        "label": label,
        "command": args,
        "workdir": str(ROOT),
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


def _write_full_bundle(bundle_dir: Path, name: str, bundle: dict[str, Any], exports: dict[str, str]) -> None:
    case_dir = bundle_dir / name
    case_dir.mkdir(parents=True, exist_ok=True)
    write_json(case_dir / "bundle.json", bundle)
    for fmt, content in exports.items():
        (case_dir / f"export.{fmt}").write_text(content, encoding="utf-8")


def _git_info(review_dir: Path, reviewed_commit: str | None) -> dict[str, Any]:
    def capture(args: list[str]) -> str:
        return subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace").strip()

    info = {
        "repository": str(ROOT),
        "baseline_commit": BASELINE_COMMIT,
        "reviewed_commit": reviewed_commit or capture(["git", "rev-parse", "HEAD"]),
        "branch": capture(["git", "branch", "--show-current"]),
        "head": capture(["git", "rev-parse", "HEAD"]),
        "main": capture(["git", "rev-parse", "refs/heads/main"]),
        "origin_main": capture(["git", "rev-parse", "refs/remotes/origin/main"]),
        "status_porcelain": capture(["git", "status", "--short", "--branch"]),
        "diff_stat": capture(["git", "diff", "--stat", f"{BASELINE_COMMIT}..HEAD"]),
        "python": sys.version,
        "platform": platform.platform(),
    }
    write_json(review_dir / "git_environment.json", info)
    return info


def _write_patch(review_dir: Path, reviewed_commit: str | None) -> None:
    commit = reviewed_commit or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    patch = subprocess.check_output(["git", "diff", "--binary", BASELINE_COMMIT, commit], cwd=ROOT)
    (review_dir / "reviewed.patch").write_bytes(patch)


def _write_manifest(review_dir: Path) -> dict[str, Any]:
    manifest = {"schema": 1, "self_hash_excluded": True, "files": {}}
    for path in sorted(item for item in review_dir.rglob("*") if item.is_file() and item.name != "manifest.json"):
        relative = path.relative_to(review_dir).as_posix()
        payload = path.read_bytes()
        manifest["files"][relative] = {"size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    write_json(review_dir / "manifest.json", manifest)
    return manifest


def _zip_review(review_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in review_dir.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(review_dir).as_posix())


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

    source = FormalReadOnlyDataSource(args.formal_dir / "tracker.json", args.formal_dir / "movement_dictionary.json")
    before = source.before_fingerprints
    write_json(review_dir / "formal_files_before.json", before)

    command_results = [
        run_command(review_dir, "compile", [sys.executable, "-m", "py_compile", "fitness_ledger_core/formal_readonly_data_source.py", "tools/formal_readonly_validation.py"]),
        run_command(review_dir, "request_protocol_regression", [sys.executable, "tools/analysis_export_request_protocol_test.py"]),
        run_command(review_dir, "anonymous_materializer_regression", [sys.executable, "tools/analysis_export_materializer_test.py"]),
        run_command(review_dir, "analysis_export_regression", [sys.executable, "tools/analysis_export_test.py"]),
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
        _write_full_bundle(bundle_dir, name, bundle, exports)
        evidence = _evidence_for_case(name, request, bundle, source)
        write_json(case_dir / "evidence.json", evidence)
        matrix.append(evidence)

    after = source.file_fingerprints()
    write_json(review_dir / "formal_files_after.json", after)
    assert before == after
    write_json(review_dir / "formal_file_hash_comparison.json", {"identical": before == after, "before": before, "after": after})
    write_json(review_dir / "case_matrix.json", matrix)
    (review_dir / "case_matrix.md").write_text(
        "# Formal Read-only Case Matrix\n\n" + "\n".join(
            f"- {item['case']}: **{item['status']}**, counts={json.dumps(item['counts'], ensure_ascii=False, sort_keys=True)}"
            for item in matrix
        ) + "\n",
        encoding="utf-8",
    )
    write_json(review_dir / "commands.json", command_results)
    git_info = _git_info(review_dir, args.reviewed_commit)
    _write_patch(review_dir, args.reviewed_commit)
    (review_dir / "safety_proof.md").write_text(
        "# Safety Proof\n\n"
        "- Formal inputs were exactly the two explicit JSON files recorded in formal_files_before.json.\n"
        "- The adapter projects only structured Body, Diet, Training, movement history, and movement dictionary fields needed by Request v1.1.\n"
        "- No formal file write, formatting, repair, synchronization, Web/UI start, model, Ollama, or Executor command is present in the command log.\n"
        "- Every generated Bundle has raw_included=false, executor_called=false, and formal_data_written=false.\n"
        "- Full formal Bundle JSON/Markdown artifacts are outside this Review directory and are not included in the Review ZIP.\n"
        "- formal_file_hash_comparison.json proves exact equality of path, size, SHA-256, and modification time before and after execution.\n"
        "- Anonymous Request Validator and Materializer regression tests passed before formal cases.\n",
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
        "bundle_artifacts_directory": str(bundle_dir),
        "review_directory": str(review_dir),
    }
    materialized_case_count = sum(item["status"] == "materialized" for item in matrix)
    resolution_case_count = sum(item["status"] == "movement_resolution_required" for item in matrix)
    write_json(review_dir / "review_report.json", report)
    (review_dir / "REVIEW_REPORT.md").write_text(
        "# Fitness Ledger Formal Read-only Validation\n\n"
        f"- Decision: {report['decision']}\n"
        f"- Baseline: {BASELINE_COMMIT}\n"
        f"- Reviewed commit: {report['reviewed_commit']}\n"
        f"- Formal files unchanged: {report['formal_files_unchanged']}\n"
        f"- Raw read: {report['raw_read']}\n"
        f"- Formal data written: {report['formal_data_written']}\n"
        f"- Model/Ollama/Executor called: {report['model_ollama_executor_called']}\n"
        f"- Cases: {report['case_count']} ({materialized_case_count} materialized, {resolution_case_count} resolution-required)\n\n"
        "Full formal Bundle outputs are stored outside the Review package under the path recorded above.\n",
        encoding="utf-8",
    )
    manifest = _write_manifest(review_dir)
    zip_path = run_root.with_suffix(".zip")
    _zip_review(review_dir, zip_path)
    print(json.dumps({"review_zip": str(zip_path), "bundles": str(bundle_dir), "manifest_files": len(manifest["files"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
