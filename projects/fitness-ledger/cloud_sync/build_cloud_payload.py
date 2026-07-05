from __future__ import annotations
import json
import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
from fitness_ledger_core.cloud_payload import build_cloud_payload
from fitness_ledger_core.data_quality_view import collect_issues
from fitness_ledger_core.shared_view_models import LedgerViewModels


def load_stable_module():
    module_name = "fitness_ledger_cloud_stable_app"
    loader = SourceFileLoader(module_name, str(PROJECT_DIR / "stable_app.pyw"))
    spec = importlib.util.spec_from_loader(module_name, loader)
    if spec is None:
        raise RuntimeError("Unable to load Fitness Ledger rules.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    loader.exec_module(module)
    return module

def main() -> Path:
    views = LedgerViewModels(PROJECT_DIR / "data" / "tracker.json", PROJECT_DIR / "data" / "movement_dictionary.json")
    tracker, dictionary = views.snapshot()
    quality = collect_issues(
        tracker,
        dictionary,
        load_stable_module(),
        PROJECT_DIR / "data" / "data_check_state.json",
    )
    payload = build_cloud_payload(views, data_quality=quality)
    output = PROJECT_DIR / "cloud_sync" / "out" / "fitness_ledger_cloud_payload.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    import_dir = output.parent / "cloudbase_import"
    import_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in payload.items():
        (import_dir / f"{name}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (import_dir / "manifest.json").write_text(
        json.dumps({
            "schema": payload["fl_meta"][0]["schema"],
            "generated_at": payload["fl_meta"][0]["generated_at"],
            "collections": {name: len(rows) for name, rows in payload.items()},
            "upload_order": [name for name in payload if name != "fl_meta"] + ["fl_meta"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output)
    for name, rows in payload.items(): print(f"{name}: {len(rows)}")
    return output

if __name__ == "__main__": main()
