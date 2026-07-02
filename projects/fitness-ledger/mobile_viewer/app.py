from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory, url_for

from .data_access import BASE_DIR, LedgerDataAccess


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
