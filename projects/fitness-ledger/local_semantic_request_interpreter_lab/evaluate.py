"""Fixed Gold evaluator for semantic and safety metrics."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from .core import DraftError, interpret_request
from .inference import InferenceProvider, ProviderConfigurationError
from .provider_factory import create_inference_provider
from .runtime_config import load_runtime_bundle


def _get(draft: dict[str, Any] | None, *path: str) -> Any:
    value: Any = draft
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def score_case(result: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    draft = result.get("draft")
    expected_status = expected["status"]
    scores = {
        "status": result.get("status") == expected_status,
        "dataset_selection": False,
        "requested_information": False,
        "time_intent": False,
        "scope": False,
        "relation": False,
        "notes_scope": False,
        "confirmation": result.get("status") == expected_status and (expected_status != "needs_confirmation" or bool(_get(draft, "missing_confirmations"))),
        "raw_overreach": True,
        "unknown_field_invention": result.get("status") != "invalid_model_output",
    }
    if isinstance(draft, dict):
        actual_datasets = draft.get("datasets", [])
        expected_datasets = expected.get("datasets", [])
        actual_kinds = sorted(item.get("kind") for item in actual_datasets)
        expected_kinds = sorted(item.get("kind") for item in expected_datasets)
        scores["dataset_selection"] = actual_kinds == expected_kinds
        if len(actual_datasets) == len(expected_datasets):
            matched = []
            for want in expected_datasets:
                got = next((item for item in actual_datasets if item.get("draft_id") == want.get("draft_id")), None)
                if got is None:
                    continue
                matched.append(got.get("requested_information") == want.get("requested_information"))
            scores["requested_information"] = bool(matched) and all(matched)
            time_matches = []
            scope_matches = []
            note_matches = []
            for want in expected_datasets:
                got = next((item for item in actual_datasets if item.get("draft_id") == want.get("draft_id")), None)
                if got is None:
                    continue
                time_matches.append(got.get("time_intent") == want.get("time_intent"))
                scope_matches.append(got.get("scope") == want.get("scope"))
                note_matches.append(got.get("notes") == want.get("notes"))
            scores["time_intent"] = bool(time_matches) and all(time_matches)
            scores["scope"] = bool(scope_matches) and all(scope_matches)
            scores["notes_scope"] = bool(note_matches) and all(note_matches)
            scores["relation"] = draft.get("relations", []) == expected.get("relations", [])
        serialized = json.dumps(draft, ensure_ascii=False)
        scores["raw_overreach"] = '"raw"' not in serialized.lower() and '"write"' not in serialized.lower() and '"executor"' not in serialized.lower()
    return {"case_id": expected["case_id"], "scores": scores, "result_status": result.get("status"), "errors": result.get("errors", [])}


def run_evaluation(runner: InferenceProvider | Callable[[str], str], catalog: dict[str, Any], cases: list[dict[str, Any]], repeat: int = 1) -> dict[str, Any]:
    rows = []
    durations = []
    for case in cases:
        for repetition in range(repeat):
            started = time.perf_counter()
            result = interpret_request(case["text"], catalog, runner)
            elapsed = round((time.perf_counter() - started) * 1000, 2)
            durations.append(elapsed)
            row = score_case(result, case)
            row["repetition"] = repetition + 1
            row["latency_ms"] = elapsed
            rows.append(row)
    metric_names = sorted(rows[0]["scores"]) if rows else []
    metrics = {name: round(sum(bool(row["scores"][name]) for row in rows) / len(rows), 4) for name in metric_names} if rows else {}
    return {
        "cases": len(cases),
        "repetitions": repeat,
        "metrics": metrics,
        "latency_ms": {"mean": round(statistics.mean(durations), 2) if durations else None, "p95": round(sorted(durations)[max(0, int(len(durations) * 0.95) - 1)], 2) if durations else None},
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-config", help="JSON file containing model_profile and runtime_config")
    parser.add_argument("--model")
    parser.add_argument("--llama-cli")
    parser.add_argument("--backend", choices=["cpu", "cuda"])
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--gpu-layers", type=int)
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).parent
    catalog = json.loads((root / "data" / "capability_catalog.json").read_text(encoding="utf-8"))
    cases = json.loads((root / "data" / "gold_cases.json").read_text(encoding="utf-8"))
    try:
        bundle = load_runtime_bundle(args.runtime_config, model_path=args.model, executable_path=args.llama_cli, backend=args.backend, gpu_layers=args.gpu_layers, timeout_seconds=args.timeout)
        runner = create_inference_provider(bundle, root / "schema" / "request_draft_v1.schema.json")
    except ProviderConfigurationError as exc:
        parser.error(str(exc))
    report = run_evaluation(runner, catalog, cases, args.repeat)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
