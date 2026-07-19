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
    "看看我最近减脂怎么样，训练有没有受影响",
    "分析最近低碳是否导致胸部训练表现下降",
    "导出关于卧推最近一段时间最有价值的数据",
    "看看这几个月肩部训练是否有进步",
]

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enable", action="store_true")
    ap.add_argument("--formal-dir", default=os.environ.get("FITNESS_LEDGER_FORMAL_DIR", ""))
    ap.add_argument("--repeat", type=int, default=1)
    args = ap.parse_args()
    if not args.enable:
        print(json.dumps({"status": "skipped", "reason": "pass --enable"})); return
    root = Path(args.formal_dir)
    tracker, dictionary = root / "data" / "tracker.json", root / "data" / "movement_dictionary.json"
    if not tracker.is_file() or not dictionary.is_file():
        print(json.dumps({"status": "skipped", "reason": "formal data directory not supplied"})); return
    adapter = OllamaNativeAdapter(); health = adapter.health_check()
    if not health.get("available"):
        print(json.dumps({"status": "skipped", "health": health}, ensure_ascii=False)); return
    views = LedgerViewModels(tracker, dictionary)
    for prompt in PROMPTS:
        rows = []
        for run_no in range(max(1, args.repeat)):
            started = time.monotonic()
            try:
                result = IntelligentExportService(views, adapter, overall_timeout=180).run(prompt, "concise")
                trace = result.get("trace", {})
                rows.append({"run": run_no + 1, "status": result.get("status"), "fallback_reason": result.get("fallback", {}).get("fallback_reason", ""), "repaired": trace.get("repaired", False), "duration_ms": trace.get("duration_ms", int((time.monotonic()-started)*1000)), "adapter": trace.get("adapter", ""), "model": trace.get("model", ""), "selected_modules": len(result.get("plan", {}).get("selected_modules", [])), "selected_movements": len(result.get("plan", {}).get("selected_movements", [])), "selected_notes": len(result.get("plan", {}).get("notes_selection", [])), "validation_error": trace.get("error_code", "")})
            except Exception as exc:
                rows.append({"run": run_no + 1, "status": "exception", "error_code": type(exc).__name__, "error": str(exc)[:160]})
        print(json.dumps({"request_label": PROMPTS.index(prompt) + 1, "runs": rows}, ensure_ascii=False))

if __name__ == "__main__": main()
