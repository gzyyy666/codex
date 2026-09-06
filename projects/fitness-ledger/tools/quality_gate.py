"""Small, local-only quality gate for the Fitness Ledger review candidate.

The gate reports evidence; it does not install dependencies, contact external
services, or treat an unavailable optional tool as a passing check.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
TOOLS = PROJECT / "tools"
CORE_TESTS = [
    "f02_f06_regression_test.py",
    "analysis_export_materializer_test.py",
    "analysis_export_request_protocol_test.py",
    "analysis_export_protocol_web_test.py",
    "fail_closed_write_test.py",
    "security_boundary_test.py",
    "movement_instance_progress_core_test.py",
    "movement_lifecycle_core_test.py",
    "unified_edit_chain_test.py",
]

# This is the previously established local-safe matrix.  Browser, model and
# real-formal-data tests are intentionally not part of this command.
FULL_SAFE_TESTS = [
    "analysis_evaluation_test.py", "analysis_evidence_contract_test.py",
    "analysis_export_materializer_test.py", "analysis_export_protocol_web_test.py",
    "analysis_export_request_protocol_test.py", "analysis_export_test.py",
    "analysis_foundation_contract_test.py", "analysis_preview_review_ui_test.py",
    "analysis_preview_service_test.py", "archive_navigation_test.py",
    "auto_sync_outcome_test.py", "build_identity_test.py", "cloud_sync_nav_test.py",
    "cloud_sync_status_test.py", "cloud_sync_test.py", "custom_movement_merge_test.py",
    "data_module_cloud_extension_test.py", "data_module_engine_test.py",
    "data_module_generic_contract_test.py", "data_module_self_service_test.py",
    "data_module_static_test.py", "data_module_web_candidate_test.py",
    "f02_f06_regression_test.py", "formal_local_semantic_hint_adapter_test.py",
    "formal_local_semantic_hint_web_test.py", "formal_readonly_export_binding_test.py",
    "freeform_candidates_exact_match_test.py", "intelligent_export_adapter_test.py",
    "intelligent_export_core_test.py", "intelligent_export_date_test.py",
    "intelligent_export_error_test.py", "intelligent_export_query_scope_test.py",
    "intelligent_export_review_evidence_test.py", "intelligent_export_selection_test.py",
    "intelligent_export_web_test.py", "intent_command_parser_test.py",
    "intent_compiler_test.py", "intent_end_to_end_scope_test.py",
    "intent_executor_safety_test.py", "intent_semantic_validator_test.py",
    "ledger_web_read_test.py", "llm_entry_prompt_regression_test.py",
    "mini_program_test.py", "mobile_desktop_sync_contract_test.py",
    "mobile_viewer_smoke_test.py", "movement_identity_ux_test.py",
    "movement_instance_progress_core_test.py", "movement_lifecycle_core_test.py",
    "movement_progress_cache_test.py", "movement_target_scope_test.py",
    "natural_language_import_test.py", "notes_semantics_core_test.py",
    "phone_inbox_persistence_test.py", "project_status_test.py",
    "pure_core_multipart_invariant_test.py", "pwa_production_bundle_test.py",
    "pwa_static_test.py", "save_semantics_test.py", "silent_health_test.py",
    "unified_edit_chain_test.py",
]

KNOWN_NOT_CONFIGURED = {
    "formal_readonly_export_binding_test.py": "FITNESS_LEDGER_FORMAL_DIR is not supplied; no formal data test is run by this local gate.",
}


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def result(name: str, status: str, **details: object) -> dict:
    return {"name": name, "status": status, **details}


def run_command(name: str, args: list[str], timeout: int = 120) -> dict:
    started = time.perf_counter()
    safe_env = os.environ.copy()
    # This gate is candidate-local.  Never pass a caller's formal-directory
    # override to a test subprocess unless a separately authorized formal test
    # invocation is being performed outside this command.
    safe_env.pop("FITNESS_LEDGER_FORMAL_DIR", None)
    try:
        completed = subprocess.run(
            args, cwd=PROJECT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, env=safe_env,
        )
    except subprocess.TimeoutExpired as exc:
        return result(name, "FAIL", exit_code=None, seconds=round(time.perf_counter() - started, 3),
                      timeout=True, stdout=(exc.stdout or "")[-1200:], stderr=(exc.stderr or "")[-1200:])
    except OSError as exc:
        return result(name, "FAIL", exit_code=None, seconds=round(time.perf_counter() - started, 3),
                      error=str(exc))
    status = "PASS" if completed.returncode == 0 else "FAIL"
    return result(name, status, exit_code=completed.returncode,
                  seconds=round(time.perf_counter() - started, 3),
                  stdout=completed.stdout[-1200:], stderr=completed.stderr[-1200:])


def environment_gate() -> dict:
    details = {
        "python": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "project": str(PROJECT),
        "formal_dir_supplied": False,
    }
    if not (PROJECT / "ledger_commands.py").is_file():
        return result("environment", "FAIL", **details, error="ledger_commands.py is missing")
    details["node"] = shutil.which("node") or ""
    return result("environment", "PASS", **details)


def syntax_gate() -> dict:
    checks = [run_command("python_compileall", [sys.executable, "-m", "compileall", "-q", "."])]
    js_files = [
        PROJECT / "web_desktop" / "app.js",
        PROJECT / "web_desktop" / "static" / "app.js",
        PROJECT / "mobile_viewer" / "static" / "app.js",
        PROJECT / "mini_program" / "cloudfunctions" / "ledgerWebRead" / "index.js",
    ]
    if command_exists("node"):
        for path in js_files:
            if path.is_file():
                checks.append(run_command(f"node_check:{path.relative_to(PROJECT)}", ["node", "--check", str(path)]))
    else:
        checks.append(result("node_syntax", "NOT_CONFIGURED", reason="node executable is unavailable"))
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return result("syntax", status, checks=checks)


def tests_gate(name: str, tests: list[str]) -> dict:
    checks = []
    for test in tests:
        if test in KNOWN_NOT_CONFIGURED:
            checks.append(result(test, "NOT_CONFIGURED", reason=KNOWN_NOT_CONFIGURED[test]))
            continue
        path = TOOLS / test
        if not path.is_file():
            checks.append(result(test, "NOT_CONFIGURED", reason="test file is absent"))
            continue
        checks.append(run_command(test, [sys.executable, str(path)], timeout=180))
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return result(name, status, checks=checks)


def optional_tool_gate() -> dict:
    checks = []
    for label, executable, args, reason in (
        ("ruff", "ruff", ["ruff", "check", "ledger_commands.py", "cloud_sync", "mobile_viewer", "tools"], "ruff is not installed"),
        ("pip_audit", "pip-audit", ["pip-audit", "--local"], "pip-audit is not installed; no network audit is attempted"),
        ("mypy", "mypy", ["mypy", "ledger_commands.py"], "mypy is not installed and no project typing configuration was supplied"),
    ):
        if not command_exists(executable):
            checks.append(result(label, "NOT_CONFIGURED", reason=reason))
            continue
        checks.append(run_command(label, args, timeout=180))
    return result("optional_tooling", "PASS" if all(c["status"] in {"PASS", "NOT_CONFIGURED"} for c in checks) else "FAIL", checks=checks)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-safe", action="store_true", help="run the established local-safe matrix")
    parser.add_argument("--output", type=Path, help="write JSON report to this path")
    args = parser.parse_args()
    gates = [environment_gate(), syntax_gate(), tests_gate("core_regression", CORE_TESTS), optional_tool_gate()]
    if args.full_safe:
        gates.append(tests_gate("full_safe_matrix", FULL_SAFE_TESTS))
    overall = "PASS"
    if any(gate["status"] == "FAIL" for gate in gates):
        overall = "FAIL"
    report = {
        "schema": 1,
        "project": str(PROJECT),
        "python": sys.executable,
        "full_safe_requested": args.full_safe,
        "overall": overall,
        "gates": gates,
        "status_legend": {
            "PASS": "executed and passed",
            "FAIL": "executed and failed",
            "SKIPPED": "deliberately not selected by this invocation",
            "NOT_CONFIGURED": "required environment/tool is absent; not counted as a pass",
        },
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
