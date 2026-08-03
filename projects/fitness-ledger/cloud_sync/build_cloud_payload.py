from __future__ import annotations
import json
import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
from fitness_ledger_core.cloud_payload import build_cloud_payload, stable_json_hash
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


def source_metadata(tracker: dict, dictionary: dict) -> dict:
    """Return the canonical version and latest date of the formal local sources."""
    dates = {
        str(row.get("Date") or row.get("date") or "")[:10]
        for collection in ("daily_records", "diet_records", "training_sessions")
        for row in tracker.get(collection, []) or []
        if str(row.get("Date") or row.get("date") or "")[:10]
    }
    return {
        "source_fingerprint": stable_json_hash({
            "tracker": tracker,
            "movement_dictionary": dictionary,
        }),
        "latest_record_date": max(dates, default=""),
    }


def resolve_source_files() -> tuple[Path, Path]:
    """Resolve the same formal data directory used by the desktop web service.

    The repository keeps only a small fixture under ``data/``.  The running
    desktop application may point at the user's formal ledger through
    ``FITNESS_LEDGER_FORMAL_DIR``; payload generation must use that same source
    or a one-click sync could publish stale fixture data.
    """
    configured_root = str(os.environ.get("FITNESS_LEDGER_FORMAL_DIR", "")).strip()
    if configured_root:
        formal_root = Path(configured_root).expanduser()
        formal_data_root = formal_root / "data" if (formal_root / "data").is_dir() else formal_root
        tracker = formal_data_root / "tracker.json"
        dictionary = formal_data_root / "movement_dictionary.json"
        if tracker.is_file() and dictionary.is_file():
            return tracker, dictionary
    return PROJECT_DIR / "data" / "tracker.json", PROJECT_DIR / "data" / "movement_dictionary.json"

def main() -> Path:
    tracker_path, dictionary_path = resolve_source_files()
    views = LedgerViewModels(tracker_path, dictionary_path)
    tracker, dictionary = views.snapshot()
    source = source_metadata(tracker, dictionary)
    quality = collect_issues(
        tracker,
        dictionary,
        load_stable_module(),
        tracker_path.parent / "data_check_state.json",
    )
    payload = build_cloud_payload(views, data_quality=quality)
    output = PROJECT_DIR / "cloud_sync" / "out" / "fitness_ledger_cloud_payload.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    import_dir = output.parent / "cloudbase_import"
    import_dir.mkdir(parents=True, exist_ok=True)
    for stale in (*import_dir.glob("fl_*.json"), *import_dir.glob("fl_*.jsonl")):
        stale.unlink()
    for name, rows in payload.items():
        content = "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
        (import_dir / f"{name}.json").write_text(
            f"{content}\n" if content else "",
            encoding="utf-8",
        )
    (import_dir / "manifest.json").write_text(
        json.dumps({
            "schema": payload["fl_meta"][0]["schema"],
            "generated_at": payload["fl_meta"][0]["generated_at"],
            "sync_version": payload["fl_meta"][0].get("sync_version", ""),
            "payload_hash": payload["fl_meta"][0].get("payload_hash", ""),
            "latest_record_date": payload["fl_meta"][0]["latest_record_date"],
            "source_fingerprint": source["source_fingerprint"],
            "collections": {name: len(rows) for name, rows in payload.items()},
            "collection_counts": payload["fl_meta"][0].get("collection_counts", {}),
            "collection_hashes": payload["fl_meta"][0].get("collection_hashes", {}),
            "raw_text_policy": payload["fl_meta"][0].get("raw_text_policy", ""),
            "empty_collections": [name for name, rows in payload.items() if not rows],
            "import_files": [f"{name}.json" for name in payload],
            "upload_order": [name for name in payload if name != "fl_meta"] + ["fl_meta"],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output)
    for name, rows in payload.items(): print(f"{name}: {len(rows)}")
    return output

if __name__ == "__main__": main()
