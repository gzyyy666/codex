"""Opt-in, read-only Ollama smoke test for the Core MVP.

The script is skipped unless ``--enable`` is supplied.  It never starts or
reconfigures Ollama and prints only structural counts, never private Notes or
Raw text.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.intelligent_export import IntelligentExportService
from fitness_ledger_core.local_model_adapter import OllamaNativeAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enable", action="store_true", help="perform the opt-in HTTP smoke test")
    parser.add_argument("--formal-dir", default=os.environ.get("FITNESS_LEDGER_FORMAL_DIR", ""))
    args = parser.parse_args()
    if not args.enable:
        print("OLLAMA_SMOKE_SKIPPED (pass --enable explicitly)")
        return
    root = Path(args.formal_dir) if args.formal_dir else ROOT
    tracker, dictionary = root / "data" / "tracker.json", root / "data" / "movement_dictionary.json"
    if not tracker.is_file() or not dictionary.is_file():
        print("OLLAMA_SMOKE_SKIPPED (no explicit data directory)")
        return
    adapter = OllamaNativeAdapter()
    health = adapter.health_check()
    if not health.get("available"):
        print(f"OLLAMA_SMOKE_SKIPPED ({health.get('code', 'unavailable')})")
        return
    result = IntelligentExportService(LedgerViewModels(tracker, dictionary), adapter).run("请复盘最近四周的体重、饮食和训练变化", "concise")
    print({"status": result.get("status"), "adapter": result.get("trace", {}).get("adapter", ""), "model": result.get("trace", {}).get("model", ""), "repaired": result.get("trace", {}).get("repaired", False), "fallback": result.get("status") == "fallback"})


if __name__ == "__main__":
    main()
