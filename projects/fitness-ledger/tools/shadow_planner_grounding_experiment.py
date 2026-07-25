"""Run reproducible anonymous Shadow Planner v1/v2 experiments.

Runtime traces must be written outside the repository and are never staged.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_foundation import CapabilityRegistryV1  # noqa: E402
from fitness_ledger_core.data_catalog import DataCatalogBuilder  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from fitness_ledger_core.shadow_planner import (  # noqa: E402
    SHADOW_POLICY_VERSION,
    SHADOW_SYSTEM_PROMPT,
    ShadowEvaluationMatrix,
)
from fitness_ledger_core.shadow_planner_evaluation import (  # noqa: E402
    ANALYSIS_DETAILS_SYSTEM_PROMPT,
    CAPABILITY_SELECTION_SYSTEM_PROMPT,
    TWO_STAGE_PROMPT_VERSION,
    TWO_STAGE_REQUEST_SCHEMA_VERSION,
    compare_report_values,
    run_grounding_benchmark,
    select_minimal_fix,
)
from intelligent_export_core_test import fixture  # noqa: E402


MATRIX = ROOT / "tools" / "fixtures" / "intelligent_export_shadow_matrix.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("v1", "v2"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def ensure_external_output(path: Path) -> Path:
    result = path.resolve()
    if result == ROOT or ROOT in result.parents:
        raise SystemExit("runtime traces must be outside the repository")
    result.mkdir(parents=True, exist_ok=True)
    return result


def main() -> None:
    args = parse_args()
    output_dir = ensure_external_output(args.output_dir)
    matrix = ShadowEvaluationMatrix.load(MATRIX)
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-shadow-experiment-") as name:
        tracker, dictionary = fixture(Path(name))
        views = LedgerViewModels(tracker, dictionary)
        catalog = DataCatalogBuilder(views).build()
        if args.phase == "v1":
            report = run_grounding_benchmark(
                matrix,
                views,
                catalog,
                CapabilityRegistryV1(),
                SHADOW_POLICY_VERSION,
                SHADOW_SYSTEM_PROMPT,
                "v1-reproduced",
            )
        else:
            v1_output = output_dir / "shadow_planner_v1_trace.json"
            if not v1_output.is_file():
                raise SystemExit(f"v1 trace is required before v2: {v1_output}")
            v1_report = json.loads(v1_output.read_text(encoding="utf-8"))
            selected_fix = select_minimal_fix(v1_report)
            if selected_fix["strategy"] != "TWO_STAGE_SCHEMA":
                raise SystemExit(f"v2 schema fix was not selected by v1 evidence: {selected_fix}")
            report = run_grounding_benchmark(
                matrix,
                views,
                catalog,
                CapabilityRegistryV1(),
                TWO_STAGE_PROMPT_VERSION,
                CAPABILITY_SELECTION_SYSTEM_PROMPT + "\n" + ANALYSIS_DETAILS_SYSTEM_PROMPT,
                "v2-two-stage-schema",
                strategy="two_stage_schema",
                request_schema_version=TWO_STAGE_REQUEST_SCHEMA_VERSION,
            )
    output = output_dir / f"shadow_planner_{args.phase}_trace.json"
    output.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    comparison_output = None
    comparison = None
    if args.phase == "v2":
        comparison = compare_report_values(v1_report, report.to_dict())
        if not all(
            comparison[key]
            for key in ("same_holdout", "same_model", "same_model_digest")
        ):
            raise SystemExit("v1/v2 comparison identity check failed")
        comparison_output = output_dir / "shadow_planner_v1_v2_comparison.json"
        comparison_output.write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "phase": args.phase,
                "output": str(output),
                "comparison_output": str(comparison_output) if comparison_output else None,
                "model": report.model,
                "model_digest": report.model_digest,
                "holdout_hash": report.holdout_hash,
                "metrics": report.metrics["holdout"],
                "failure_counts": report.failure_counts,
                "decision": comparison["decision"] if comparison else None,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
