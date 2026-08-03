from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory, url_for

from .data_access import BASE_DIR, LedgerDataAccess, format_set_line


PWA_DIR = Path(__file__).resolve().parent / "pwa"

PWA_BODY_PARTS = {
    "shoulders": {"label": "肩", "labelEn": "SHOULDERS", "tone": "amber", "groups": ("shoulder", "肩")},
    "chest": {"label": "胸", "labelEn": "CHEST", "tone": "coral", "groups": ("chest", "胸")},
    "back": {"label": "背", "labelEn": "BACK", "tone": "teal", "groups": ("back", "背")},
    "legs": {"label": "腿", "labelEn": "LEGS", "tone": "violet", "groups": ("leg", "lower", "hip", "腿", "臀")},
    "arms": {"label": "手臂", "labelEn": "ARMS", "tone": "cyan", "groups": ("arm", "biceps", "triceps", "手臂")},
}


def _pwa_set_summary(sets: list[dict]) -> str:
    return " · ".join(format_set_line(item) for item in sets or [])


def _pwa_movement_catalog(data_access: LedgerDataAccess) -> list[dict]:
    result = []
    for item in data_access._movements_by_id().values():
        row = asdict(item)
        row["body_parts"] = [
            part_id for part_id, part in PWA_BODY_PARTS.items()
            if any(group.lower() in str(item.muscle_group or "").lower() for group in part["groups"])
        ]
        result.append(row)
    return result


def _pwa_body_area(data_access: LedgerDataAccess, part_id: str) -> dict | None:
    part = PWA_BODY_PARTS.get(part_id)
    if not part:
        return None
    tracker = data_access._tracker()
    catalog = {item["movement_id"]: item for item in _pwa_movement_catalog(data_access)}
    movement_ids = {
        movement_id for movement_id, item in catalog.items()
        if any(group.lower() in str(item.get("muscle_group") or "").lower() for group in part["groups"])
    }
    history_by_id: dict[str, list[dict]] = {}
    for movement in tracker.get("movements", {}).values():
        movement_id = str(movement.get("movement_id") or "")
        if movement_id not in movement_ids:
            continue
        history_by_id[movement_id] = sorted(
            [dict(item) for item in movement.get("history", []) or []],
            key=lambda item: str(item.get("date") or ""), reverse=True,
        )
    movement_cards = []
    for movement_id in movement_ids:
        history = history_by_id.get(movement_id, [])
        if not history:
            continue
        definition = catalog[movement_id]
        compact = []
        for item in history:
            metrics = item.get("metrics") or {}
            sets = item.get("sets") or []
            compact.append({
                "date": str(item.get("date") or "")[:10],
                "order": item.get("order") or 0,
                "sets": sets,
                "summary": _pwa_set_summary(sets),
                "notes": str(item.get("notes") or ""),
                "max_weight": float(metrics.get("max_weight") or 0),
                "total_reps": int(metrics.get("total_reps") or 0),
                "volume": float(metrics.get("volume") or 0),
            })
        best = max(compact, key=lambda item: (item["max_weight"], item["volume"], item["total_reps"]))
        movement_cards.append({
            "movement_id": movement_id,
            "display_name": definition.get("display_name") or movement_id,
            "english_name": definition.get("english_name") or "",
            "muscle_group": definition.get("muscle_group") or "",
            "pinned": bool(definition.get("pinned")),
            "focus_rank": int(definition.get("focus_rank") or 0),
            "sessions": len(compact),
            "latest": compact[0],
            "previous": compact[1] if len(compact) > 1 else None,
            "best": best,
            "recent": compact[:3],
        })
    movement_cards.sort(key=lambda item: (not item["pinned"], item["focus_rank"] or 9999, -item["sessions"], item["display_name"]))
    history_rows = []
    for movement_id, records in history_by_id.items():
        for record in records:
            history_rows.append((str(record.get("date") or "")[:10], movement_id, record))
    sessions_by_date = {}
    training_by_date = {str(item.get("Date") or "")[:10]: item for item in tracker.get("training_sessions", [])}
    for date_value, movement_id, record in history_rows:
        session = sessions_by_date.setdefault(date_value, {"date": date_value, "related_movements": [], "records": []})
        name = catalog.get(movement_id, {}).get("display_name") or movement_id
        if name not in session["related_movements"]:
            session["related_movements"].append(name)
        session["records"].append(record)
    sessions = []
    for date_value in sorted(sessions_by_date, reverse=True):
        session = sessions_by_date[date_value]
        training = training_by_date.get(date_value, {})
        sessions.append({
            "id": date_value,
            "date": date_value,
            "split": training.get("Split") or f"{part['label']}训练",
            "title": training.get("Split") or f"{part['label']}训练",
            "related_count": len(session["related_movements"]),
            "related_movements": session["related_movements"],
            "movement_summary": training.get("Standardized Summary") or "暂无完整动作摘要",
            "full_summary": training.get("Standardized Summary") or "暂无完整动作摘要",
            "notes": training.get("Notes") or "",
        })
    return {
        "id": part_id,
        "label": part["label"],
        "labelEn": part["labelEn"],
        "tone": part["tone"],
        "session_count": len(sessions),
        "movement_count": len(movement_cards),
        "latest_date": sessions[0]["date"] if sessions else "",
        "movements": movement_cards,
        "sessions": sessions[:12],
    }


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    data_access = LedgerDataAccess()
    app.config["DATA_ACCESS"] = data_access

    @app.context_processor
    def inject_globals():
        return {
            "nav_items": [
                ("Home", url_for("home")),
                ("Today", url_for("today")),
                ("Movement", url_for("movement")),
                ("Search", url_for("search")),
            ]
        }

    @app.get("/viewer-assets/<path:filename>")
    def viewer_assets(filename: str):
        return send_from_directory(BASE_DIR / "assets", filename)

    @app.get("/pwa/")
    @app.get("/pwa")
    def pwa_index():
        return send_from_directory(PWA_DIR, "index.html")

    @app.get("/pwa/<path:filename>")
    def pwa_assets(filename: str):
        return send_from_directory(PWA_DIR, filename)

    @app.get("/")
    def home():
        today_summary = data_access.get_today_summary()
        recent_dates = data_access.all_dates()[:6]
        return render_template("home.html", today=today_summary, recent_dates=recent_dates)

    @app.get("/today")
    def today():
        entry_date = request.args.get("date") or data_access.latest_date()
        detail = data_access.get_record_detail(entry_date)
        return render_template("today.html", detail=detail)

    @app.get("/record/<entry_date>")
    def record_detail(entry_date: str):
        detail = data_access.get_record_detail(entry_date)
        if not detail["date"]:
            abort(404)
        return render_template("record_detail.html", detail=detail)

    @app.get("/movement")
    def movement():
        query = request.args.get("q", "").strip()
        history_limit = max(3, min(int(request.args.get("limit", "5") or 5), 12))
        history = data_access.get_movement_history(query, limit=history_limit) if query else {"movement": None, "history": []}
        suggestions = data_access.find_movement_candidates(query, limit=10) if query else []
        return render_template("movement.html", query=query, history=history, suggestions=suggestions, limit=history_limit)

    @app.get("/search")
    def search():
        query = request.args.get("q", "").strip()
        scope = request.args.get("scope", "30d")
        results = data_access.search_records(query, scope=scope) if query else {"query": "", "scope": scope, "records": [], "movements": []}
        return render_template("search.html", results=results)

    @app.get("/api/today")
    def api_today():
        return jsonify(data_access.get_today_summary())

    @app.get("/api/pwa/read")
    def api_pwa_read():
        """Local adapter using the same action vocabulary as Mini Program ledger.call."""
        action = request.args.get("action", "").strip()
        if action == "status":
            return jsonify({"ok": True, "data": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "latest_record_date": data_access.latest_date(),
                "schema": "local-readonly-viewer",
            }})
        if action in {"whoami", "getOpenId"}:
            return jsonify({"ok": True, "data": {"openid": "", "appid": "", "env": "local"}})
        if action == "bodyAreas":
            areas = [_pwa_body_area(data_access, part_id) for part_id in PWA_BODY_PARTS]
            return jsonify({"ok": True, "data": [
                {key: area[key] for key in ("id", "label", "labelEn", "tone", "session_count", "movement_count", "latest_date")}
                for area in areas if area
            ]})
        if action == "bodyArea":
            area = _pwa_body_area(data_access, request.args.get("part", ""))
            return jsonify({"ok": bool(area), "data": area} if area else {"ok": False, "code": "INVALID_BODY_PART", "message": "未识别训练部位。"})
        if action == "movementCatalog":
            return jsonify({"ok": True, "data": _pwa_movement_catalog(data_access)})
        if action == "bodyRecords":
            rows = sorted(data_access._tracker().get("daily_records", []), key=lambda item: str(item.get("Date") or ""), reverse=True)
            return jsonify({"ok": True, "data": rows[:max(1, min(int(request.args.get("limit", "30")), 50))]})
        if action == "dietRecords":
            rows = sorted(data_access._tracker().get("diet_records", []), key=lambda item: str(item.get("Date") or ""), reverse=True)
            return jsonify({"ok": True, "data": rows[:max(1, min(int(request.args.get("limit", "30")), 50))]})
        if action == "trainingRecords":
            rows = sorted(data_access._tracker().get("training_sessions", []), key=lambda item: str(item.get("Date") or ""), reverse=True)
            return jsonify({"ok": True, "data": rows[:200]})
        if action == "recordDetail":
            detail = data_access.get_record_detail(request.args.get("date", ""))
            return jsonify({"ok": True, "data": {
                "date": detail["date"],
                "body": [detail["body"]] if detail["body"] else [],
                "diet": [detail["diet"]] if detail["diet"] else [],
                "training": detail["training"],
            }})
        if action == "trainingDayDetail":
            detail = data_access.get_training_by_date(request.args.get("date", ""))
            session = detail["sessions"][0] if detail["sessions"] else None
            catalog = {item["movement_id"]: item for item in _pwa_movement_catalog(data_access)}
            movements = []
            for index, item in enumerate(session.get("movements", []) if session else []):
                definition = catalog.get(item.get("movement_id", ""), {})
                movements.append({
                    "movement_id": item.get("movement_id", ""),
                    "movement_name": item.get("display_name", ""),
                    "english_name": definition.get("english_name", ""),
                    "muscle_group": definition.get("muscle_group", ""),
                    "order": item.get("order") or index + 1,
                    "sets": item.get("sets", []),
                    "notes": item.get("notes", ""),
                })
            return jsonify({"ok": True, "data": {
                "date": detail["date"],
                "session": ({"id": detail["date"], "date": detail["date"], "split": session["split"], "summary": session["standardized_summary"], "notes": session["notes"]} if session else None),
                "movements": movements,
            }})
        if action == "movement":
            movement_id = request.args.get("movementId", "")
            row = next((item for item in _pwa_movement_catalog(data_access) if item.get("movement_id") == movement_id), None)
            return jsonify({"ok": True, "data": row})
        if action == "movementHistory":
            movement_id = request.args.get("movementId", "")
            definition = next((item for item in data_access._movements_by_id().values() if item.movement_id == movement_id), None)
            history = data_access.get_movement_history(definition.display_name if definition else movement_id, limit=20)
            return jsonify({"ok": True, "data": history.get("history", [])})
        if action == "search":
            return jsonify({"ok": True, "data": data_access.search_records(request.args.get("query", ""), scope="all")})
        return jsonify({"ok": False, "code": "UNKNOWN_ACTION", "message": "未知只读操作。"}), 400

    @app.get("/api/training/<entry_date>")
    def api_training(entry_date: str):
        return jsonify(data_access.get_training_by_date(entry_date))

    @app.get("/api/search")
    def api_search():
        return jsonify(data_access.search_records(request.args.get("q", ""), scope=request.args.get("scope", "30d")))

    @app.get("/api/movement/<path:movement_name>")
    def api_movement(movement_name: str):
        limit = max(1, min(int(request.args.get("limit", "5") or 5), 20))
        return jsonify(data_access.get_movement_history(movement_name, limit=limit))

    return app


def main() -> None:
    app = create_app()
    app.run(host="0.0.0.0", port=5055, debug=False)


if __name__ == "__main__":
    main()
