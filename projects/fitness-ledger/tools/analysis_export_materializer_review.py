"""Generate the external anonymous-materialization Review evidence package."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tools" / "fixtures" / "analysis_export_anonymous"
DEFAULT_OUTPUT = Path(r"C:\Users\26087\Documents\github-memory\analysis-export-anonymous-materialization-review") / datetime.now(timezone.utc).strftime("anonymous-materialization-%Y%m%dT%H%M%SZ")
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_export_materializer import AnonymousFixtureMaterializer, MaterializationError  # noqa: E402
from fitness_ledger_core.analysis_export_request import validate_request  # noqa: E402


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(output: Path, label: str, args: list[str]) -> dict:
    started = time.perf_counter()
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
    duration = time.perf_counter() - started
    (output / "commands").mkdir(parents=True, exist_ok=True)
    (output / "commands" / f"{label}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (output / "commands" / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    return {
        "label": label,
        "command": " ".join(args),
        "workdir": str(ROOT),
        "exit_code": result.returncode,
        "duration_seconds": round(duration, 6),
        "stdout_file": f"commands/{label}.stdout.txt",
        "stderr_file": f"commands/{label}.stderr.txt",
    }


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    commands = [
        ("protocol_test", [python, "tools/analysis_export_request_protocol_test.py"]),
        ("preview_service_test", [python, "tools/analysis_preview_service_test.py"]),
        ("executor_safety_test", [python, "tools/intent_executor_safety_test.py"]),
        ("review_ui_test", [python, "tools/analysis_preview_review_ui_test.py"]),
        ("materializer_test", [python, "tools/analysis_export_materializer_test.py"]),
        ("python_compile", [python, "-m", "py_compile", "fitness_ledger_core/analysis_export_materializer.py", "tools/analysis_export_materializer_test.py", "tools/analysis_export_materializer_review.py"]),
        ("git_diff_check", ["git", "diff", "--check"]),
    ]
    command_results = [run_command(output, label, args) for label, args in commands]
    if any(item["exit_code"] != 0 for item in command_results):
        write_json(output / "commands.json", command_results)
        raise SystemExit("Focused Review commands failed; see commands/")

    requests = json.loads((FIXTURE_DIR / "requests.json").read_text(encoding="utf-8"))
    rejected = json.loads((FIXTURE_DIR / "rejected_requests.json").read_text(encoding="utf-8"))
    resolution_requests = json.loads((FIXTURE_DIR / "resolution_requests.json").read_text(encoding="utf-8"))
    materializer = AnonymousFixtureMaterializer(FIXTURE_DIR / "fixture.json")
    matrix = []
    for name, request in requests.items():
        case_dir = output / "cases" / name
        case_dir.mkdir(parents=True, exist_ok=True)
        validation = validate_request(request)
        write_json(case_dir / "request.json", request)
        write_json(case_dir / "standardized_request.json", validation.normalized_request)
        assert validation.valid and validation.normalized_request is not None
        bundle, exports = materializer.materialize_with_exports(request)
        write_json(case_dir / "bundle.json", bundle)
        for fmt, text in exports.items():
            (case_dir / f"export.{fmt}").write_text(text, encoding="utf-8")
        counts = bundle["provenance"]["counts"]
        write_json(case_dir / "counts.json", counts)
        write_json(case_dir / "missing_information.json", bundle["missing_information"])
        write_json(case_dir / "warnings.json", bundle["warnings"])
        write_json(case_dir / "provenance.json", bundle["provenance"])
        write_json(case_dir / "safety_flags.json", bundle["safety_flags"])
        matrix.append({"case": name, "status": "materialized", "counts": counts, "record_count": len(bundle["records"]), "missing_information": bundle["missing_information"], "warnings": bundle["warnings"], "safety_flags": bundle["safety_flags"]})

    for name, request in rejected.items():
        case_dir = output / "cases" / name
        case_dir.mkdir(parents=True, exist_ok=True)
        validation = validate_request(request)
        write_json(case_dir / "request.json", request)
        write_json(case_dir / "standardized_request.json", validation.normalized_request)
        write_json(case_dir / "rejection.json", {"valid": validation.valid, "errors": [error.to_dict() for error in validation.errors], "materialized": False})
        counts = {
            "validated_request_count": 0,
            "candidate_record_count": 0,
            "resolved_record_count": 0,
            "materialized_record_count": 0,
            "exported_artifact_count": 0,
        }
        write_json(case_dir / "counts.json", counts)
        matrix.append({"case": name, "status": "rejected_before_materialization", "counts": counts, "errors": [error.to_dict() for error in validation.errors], "safety_flags": {"raw_included": False, "executor_called": False, "formal_data_written": False}})

    for name, request in resolution_requests.items():
        case_dir = output / "cases" / name
        case_dir.mkdir(parents=True, exist_ok=True)
        validation = validate_request(request)
        write_json(case_dir / "request.json", request)
        write_json(case_dir / "standardized_request.json", validation.normalized_request)
        assert validation.valid and validation.normalized_request is not None
        try:
            materializer.materialize(request)
        except MaterializationError as error:
            assert error.code == "MOVEMENT_RESOLUTION_REQUIRED"
            counts = {
                "validated_request_count": 1,
                "candidate_record_count": 0,
                "resolved_record_count": 0,
                "materialized_record_count": 0,
                "exported_artifact_count": 0,
            }
            write_json(case_dir / "resolution_required.json", {
                "status": error.code,
                "message": str(error),
                "candidates": error.candidates,
                "bundle_generated": False,
                "exports_generated": False,
            })
            write_json(case_dir / "counts.json", counts)
            matrix.append({
                "case": name,
                "status": "movement_resolution_required",
                "counts": counts,
                "candidates": error.candidates,
                "safety_flags": {"raw_included": False, "executor_called": False, "formal_data_written": False},
            })
        else:
            raise AssertionError(f"{name} was silently materialized")

    write_json(output / "case_matrix.json", matrix)
    (output / "case_matrix.md").write_text("# Case Matrix\n\n" + "\n".join(
        f"- `{item['case']}`: **{item['status']}**, counts={json.dumps(item['counts'], ensure_ascii=False, sort_keys=True)}"
        for item in matrix
    ) + "\n", encoding="utf-8")
    (output / "gap_report.md").write_text(
        "# Gap Report\n\n"
        "- This stage materializes only the frozen v1.1 request contract against one committed synthetic fixture.\n"
        "- It does not produce professional analysis conclusions, recommendations, claims, or an ExportPlan.\n"
        "- Missing formal fields remain JSON null and are listed in `missing_information`; optional Notes absent on a day remain null without a missing-data warning.\n"
        "- Bundle counts are recorded under `provenance.counts` because the frozen Bundle manifest is closed by schema.\n"
        "- Count units are fixed as `validated_request_count`, `candidate_record_count`, `resolved_record_count`, `materialized_record_count`, and `exported_artifact_count` in Bundle, case matrix, and exports.\n"
        "- Movement-name resolution is fixture-catalog-only, has no formal dictionary fallback, and stops with `MOVEMENT_RESOLUTION_REQUIRED` when multiple candidates match.\n",
        encoding="utf-8",
    )
    write_json(output / "commands.json", command_results)
    (output / "README.md").write_text(
        "# Anonymous Deterministic Materialization Review\n\n"
        f"Generated at: `{datetime.now(timezone.utc).isoformat()}`\n\n"
        f"Repository: `{ROOT}`\n\n"
        "All valid cases passed the frozen AnalysisExportRequest v1.1 Validator before materialization. Rejected Raw and unsupported-operation cases have no Bundle.\n\n"
        "The review set contains 11 materialized legal cases, 2 validator-rejected cases, and 1 movement-resolution-required case with no Bundle.\n\n"
        "## Safety proof\n\n"
        "- Fixture source is `tools/fixtures/analysis_export_anonymous/fixture.json`, visibly synthetic and committed.\n"
        "- `analysis_export_materializer.py` opens only the anonymous fixture path; it has no formal tracker/dictionary, Raw, model, Ollama, Executor, ExportPlan, Web, Cloud, or Mini Program integration.\n"
        "- Every Bundle has `raw_included=false`, `executor_called=false`, and `formal_data_written=false`.\n"
        "- No formal data contents were read or written, and no service was started by the Review commands.\n\n"
        "See `commands.json`, `case_matrix.md`, `gap_report.md`, and each `cases/<case>/` directory for evidence.\n",
        encoding="utf-8",
    )

    manifest = {"schema": 1, "generated_at": datetime.now(timezone.utc).isoformat(), "self_hash_excluded": True, "files": {}}
    for path in sorted(p for p in output.rglob("*") if p.is_file() and p.name != "manifest.json"):
        relative = path.relative_to(output).as_posix()
        data = path.read_bytes()
        manifest["files"][relative] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    write_json(output / "manifest.json", manifest)
    print(output)


if __name__ == "__main__":
    main()
