"""Aggregate entry point for the strict Intent/Scope/Fallback test layers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from intent_compiler_test import main as compiler_main
from intent_end_to_end_scope_test import main as scope_main
from intent_executor_safety_test import main as safety_main
from intelligent_export_adapter_test import main as adapter_main


def main() -> None:
    adapter_main()
    compiler_main()
    scope_main()
    safety_main()
    print("FITNESS_LEDGER_INTENT_SEMANTIC_VALIDATOR_OK")


if __name__ == "__main__":
    main()
