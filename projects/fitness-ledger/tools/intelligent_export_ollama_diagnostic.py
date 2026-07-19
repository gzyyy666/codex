"""Opt-in real Ollama diagnostics with structural, privacy-safe output."""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fitness_ledger_core.intelligent_export import IntelligentExportService
from fitness_ledger_core.local_model_adapter import OllamaNativeAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels

PROMPTS = [
    "\u770b\u770b\u6211\u6700\u8fd1\u51cf\u8102\u600e\u4e48\u6837\uff0c\u8bad\u7ec3\u6709\u6ca1\u6709\u53d7\u5f71\u54cd",
    "\u5206\u6790\u6700\u8fd1\u4f4e\u78b3\u662f\u5426\u5bfc\u81f4\u80f8\u90e8\u8bad\u7ec3\u8868\u73b0\u4e0b\u964d",
    "\u5bfc\u51fa\u5173\u4e8e\u5367\u63a8\u6700\u8fd1\u4e00\u6bb5\u65f6\u95f4\u6700\u6709\u4ef7\u503c\u7684\u6570\u636e",
    "\u770b\u770b\u8fd9\u51e0\u4e2a\u6708\u80a9\u90e8\u8bad\u7ec3\u662f\u5426\u6709\u8fdb\u6b65",
]

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--enable", action="store_true"); parser.add_argument("--formal-dir", default=os.environ.get("FITNESS_LEDGER_FORMAL_DIR", "")); parser.add_argument("--repeat", type=int, default=1); args = parser.parse_args()
    if not args.enable: print(json.dumps({"status": "skipped", "reason": "pass --enable"})); return
    root = Path(args.formal_dir); tracker, dictionary = root / "data" / "tracker.json", root / "data" / "movement_dictionary.json"
    if not tracker.is_file() or not dictionary.is_file(): print(json.dumps({"status": "skipped", "reason": "formal data directory not supplied"})); return
    adapter = OllamaNativeAdapter(); health = adapter.health_check()
    if not health.get("available"): print(json.dumps({"status": "blocked", "layer": "health_check", "health": health}, ensure_ascii=False)); return
    views = LedgerViewModels(tracker, dictionary)
    for index, prompt in enumerate(PROMPTS, 1):
        rows = []
        for run_no in range(max(1, args.repeat)):
            started = time.monotonic()
            try:
                result = IntelligentExportService(views, adapter, overall_timeout=180).run(prompt, "concise"); trace = result.get("trace", {})
                rows.append({"run": run_no + 1, "status": result.get("status"), "fallback_reason": result.get("fallback", {}).get("fallback_reason", ""), "repaired": trace.get("repaired", False), "duration_ms": trace.get("duration_ms", int((time.monotonic() - started) * 1000)), "adapter": trace.get("adapter", ""), "model": trace.get("model", ""), "selected_modules": len(result.get("plan", {}).get("selected_modules", [])), "selected_movements": len(result.get("plan", {}).get("selected_movements", [])), "selected_notes": len(result.get("plan", {}).get("notes_selection", [])), "validation_error": trace.get("error_code", "")})
            except Exception as exc:
                rows.append({"run": run_no + 1, "status": "exception", "error_code": type(exc).__name__, "error": str(exc)[:160]})
        print(json.dumps({"request_label": index, "runs": rows}, ensure_ascii=False))

if __name__ == "__main__": main()
