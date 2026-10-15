"""Serve a read-only Web/PWA review using anonymous temporary records."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mobile_viewer.app import create_app
from mobile_viewer.data_access import LedgerDataAccess
from web_desktop.backend.server import LedgerWebService, create_server
from werkzeug.serving import make_server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--web-port", type=int, default=8776)
    parser.add_argument("--pwa-port", type=int, default=5056)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-training-review-") as folder:
        temp = Path(folder)
        tracker = temp / "tracker.json"
        dictionary = temp / "movement_dictionary.json"
        themes = [{"theme_id": "custom-cn", "display_name": "出差训练", "active": True},
                  {"theme_id": "custom-en", "display_name": "Travel Circuit", "active": True},
                  {"theme_id": "push", "display_name": "Push", "active": True}]
        sessions = []
        for index, theme in enumerate(themes[:2], start=1):
            session_id = f"review-session-{index}"
            sessions.append({"id": session_id, "No.": index, "Date": "2099-01-01", "session_sequence": index,
                "Split": theme["display_name"], "session_theme_ids": [theme["theme_id"]],
                "session_theme_id": theme["theme_id"], "session_theme_name": theme["display_name"],
                "Standardized Summary": f"第 {index} 次训练 · 模拟动作", "movement_items": [{
                    "id": f"review-history-{index}", "movement_id": "REVIEW_PRESS", "display_name": "模拟推举",
                    "training_session_id": session_id, "date": "2099-01-01", "order": 1,
                    "sets": [] if index == 2 else [{"weight": 10, "reps": 8, "sets": 3}],
                    "exclude_from_progress": index == 2, "notes": "匿名验收记录"}],
                "Notes": "模拟记录，不是你的正式训练数据。"})
        database = {"daily_records": [{"id": "review-body", "Date": "2099-01-01", "Weight (kg)": 70, "Notes": "匿名验收记录"}],
            "diet_records": [], "training_sessions": sessions, "raw_entries": [], "movements": {},
            "training_organization": {"session_theme_catalog_locked": True, "session_themes": themes, "movement_categories": []}}
        tracker.write_text(json.dumps(database, ensure_ascii=False), encoding="utf-8")
        dictionary.write_text(json.dumps({"version": "1.0", "movements": [{"movement_id": "REVIEW_PRESS", "display_name": "模拟推举", "english_name": "Review Press", "muscle_group": "Shoulders", "active": True}]}), encoding="utf-8")
        service = LedgerWebService(tracker, dictionary, temp / "backups", build_info_override={"status": "PREVIEW", "mode": "preview", "short_sha": "training-review"})
        web = create_server(port=args.web_port, service=service)
        def reject_post(handler):
            handler.send_json({"error": "验收预览使用模拟记录，不保存修改。"}, 403)
        web.RequestHandlerClass.do_POST = reject_post
        pwa_app = create_app(LedgerDataAccess(tracker, dictionary))
        @pwa_app.before_request
        def read_only():
            from flask import request
            if request.method != "GET":
                return {"error": "验收预览不保存修改。"}, 403
        pwa = make_server("127.0.0.1", args.pwa_port, pwa_app, threaded=True)
        for server in (web, pwa):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"Web review: http://127.0.0.1:{args.web_port}/#training", flush=True)
        print(f"PWA review: http://127.0.0.1:{args.pwa_port}/pwa/#record?date=2099-01-01&from=body", flush=True)
        print("Anonymous temporary data; no formal or cloud writes.", flush=True)
        try:
            threading.Event().wait()
        finally:
            for server in (web, pwa):
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    main()
