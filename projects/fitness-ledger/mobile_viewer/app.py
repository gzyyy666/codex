from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory, url_for

from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore, DataModuleEngine
from fitness_ledger_core.record_relations import movement_items
from fitness_ledger_core.training_organization import normalize_training_organization

from .data_access import BASE_DIR, LedgerDataAccess, format_set_line


PWA_DIR = Path(__file__).resolve().parent / "pwa"

PWA_BODY_PARTS = {
    "shoulders": {"label": "肩", "labelEn": "SHOULDERS", "tone": "amber", "groups": ("shoulder", "肩")},
    "chest": {"label": "胸", "labelEn": "CHEST", "tone": "coral", "groups": ("chest", "胸")},
    "back": {"label": "背", "labelEn": "BACK", "tone": "teal", "groups": ("back", "背")},
    "legs": {"label": "腿", "labelEn": "LEGS", "tone": "violet", "groups": ("leg", "lower", "hip", "腿", "臀")},
    "arms": {"label": "手臂", "labelEn": "ARMS", "tone": "cyan", "groups": ("arm", "biceps", "triceps", "手臂")},
    "glutes": {"label": "臀", "labelEn": "GLUTES", "tone": "rose", "groups": ("glute", "臀")},
    "core": {"label": "核心", "labelEn": "CORE", "tone": "amber", "groups": ("core", "腹", "核心")},
    "cardio": {"label": "有氧", "labelEn": "CARDIO", "tone": "blue", "groups": ("cardio", "aerobic", "有氧")},
}


def _pwa_training_organization(data_access: LedgerDataAccess) -> dict:
    normalized, _ = normalize_training_organization(data_access._tracker(), data_access._cache.get("dictionary", {}) if data_access._cache else {})
    organization = normalized.get("training_organization", {})
    return {"session_themes": [item for item in organization.get("session_themes", []) if item.get("active", True)], "movement_categories": organization.get("movement_categories", [])}


def _empty_data_module_contract() -> dict:
    return {
        "schema": "fitness-ledger-mini-module-contract-v1",
        "page_required": False,
        "renderers": [],
        "modules": [],
    }


def _data_module_registry_path(data_access: LedgerDataAccess, configured: Path | None = None) -> Path | None:
    candidates = [configured] if configured else []
    environment_path = str(os.environ.get("FITNESS_LEDGER_DATA_MODULE_REGISTRY", "")).strip()
    if environment_path:
        candidates.append(Path(environment_path))
    candidates.extend([
        data_access.tracker_file.parent / "data_module_definitions.json",
        BASE_DIR / "data" / "data_module_definitions.json",
    ])
    return next((path for path in candidates if path and path.is_file()), None)


def _pwa_data_module_contract(data_access: LedgerDataAccess, configured: Path | None = None) -> dict:
    """Build the same sanitized read contract used by Cloud without exposing raw text."""
    registry_path = _data_module_registry_path(data_access, configured)
    if registry_path is None:
        return _empty_data_module_contract()
    try:
        store = DataModuleDefinitionStore(registry_path)
        categories, modules, issues = store.load(strict=True)
        engine = DataModuleEngine(
            modules,
            data_access.tracker_file,
            data_access.dictionary_file,
            category_registry=categories,
            definition_issues=issues,
        )
        return engine.build_mini_program_contract(history_limit=1000)
    except Exception:
        # The phone viewer is read-only.  A damaged optional registry must not
        # take down the existing body, diet, and training archives.
        return _empty_data_module_contract()


def _pwa_set_summary(sets: list[dict]) -> str:
    return " · ".join(format_set_line(item) for item in sets or [])


def _pwa_relation_context(session: dict, item: dict, item_by_instance_id: dict[str, dict], catalog: dict[str, dict]) -> list[dict]:
    """Enrich persisted session relations for compact movement projections."""
    item_id = str(item.get("movement_instance_id") or item.get("id") or "")
    if not item_id:
        return []
    result = []
    for relation in session.get("organization_relations", []) or []:
        if not isinstance(relation, dict):
            continue
        relation_members = [str(value) for value in relation.get("members", []) or []]
        if item_id not in relation_members:
            continue
        enriched = dict(relation)
        enriched["member_order"] = relation_members.index(item_id) + 1
        enriched["member_count"] = len(relation_members)
        enriched["co_members"] = []
        for relation_order, member_id in enumerate(relation_members, start=1):
            if member_id == item_id:
                continue
            member = item_by_instance_id.get(member_id, {})
            member_definition = catalog.get(str(member.get("movement_id") or ""), {})
            member_sets = member.get("sets") if isinstance(member.get("sets"), list) else []
            enriched["co_members"].append({
                "movement_id": member.get("movement_id", ""),
                "movement_name": member.get("display_name") or member_definition.get("display_name", ""),
                "movement_instance_id": member_id,
                "relation_order": relation_order,
                "order_in_session": member.get("order_in_session") or member.get("order", ""),
                "sets_lines": [_pwa_set_summary(member_sets)] if member_sets else [],
            })
        result.append(enriched)
    return result


def _pwa_session_theme_names(record: dict, organization: dict) -> list[str]:
    """Resolve only persisted session-theme ids/names; never infer from Split."""
    themes = organization.get("session_themes", []) if organization else []
    by_id = {str(item.get("theme_id")): str(item.get("display_name") or item.get("theme_id") or "") for item in themes}
    ids = [str(record.get("session_theme_id") or "").strip()]
    ids.extend(str(value).strip() for value in (record.get("session_theme_ids") or []))
    names: list[str] = []
    for theme_id in ids:
        if theme_id and theme_id in by_id and by_id[theme_id] not in names:
            names.append(by_id[theme_id])
    persisted_name = str(record.get("session_theme_name") or "").strip()
    if persisted_name and persisted_name not in names:
        names.append(persisted_name)
    return names


def _pwa_training_session_detail(data_access: LedgerDataAccess, session_id: str, entry_date: str = "") -> dict:
    """Return one persisted training session, preserving same-day siblings."""
    tracker = data_access._tracker()
    sessions = tracker.get("training_sessions", []) or []
    requested_id = str(session_id or "").strip()
    session = next((item for item in sessions if str(item.get("id") or "") == requested_id), None)
    if session is None and not requested_id:
        # Compatibility for old shared links only. The PWA list never uses this path.
        session = next((item for item in sessions if str(item.get("Date") or "")[:10] == str(entry_date or "")[:10]), None)
    if session is None:
        return {"date": str(entry_date or "")[:10], "session": None, "movements": []}

    organization = _pwa_training_organization(data_access)
    catalog = {item["movement_id"]: item for item in _pwa_movement_catalog(data_access)}
    raw_items = list(session.get("movement_items", []) or [])
    raw_items.sort(key=lambda item: (int(item.get("order_in_session") or item.get("order") or 9999), str(item.get("movement_item_id") or item.get("movement_id") or "")))
    item_by_instance_id = {str(item.get("movement_instance_id") or item.get("id") or ""): item for item in raw_items}

    movements = []
    for index, item in enumerate(raw_items):
        movement_id = str(item.get("movement_id") or "")
        definition = catalog.get(movement_id, {})
        sets = item.get("sets") if isinstance(item.get("sets"), list) else []
        summary = str(item.get("summary") or item.get("summary_text") or "").strip() or _pwa_set_summary(sets) or "暂无组数记录"
        movements.append({
            "movement_id": movement_id,
            "movement_name": str(item.get("display_name") or definition.get("display_name") or movement_id or "未命名动作"),
            "english_name": definition.get("english_name", ""),
            "muscle_group": definition.get("muscle_group", ""),
            "order_in_session": item.get("order_in_session") or item.get("order") or index + 1,
            "sets": sets,
            "summary": summary,
            "notes": str(item.get("notes") or ""),
            "training_session_id": str(session.get("id") or ""),
            "organization_relations": _pwa_relation_context(session, item, item_by_instance_id, catalog),
        })
    theme_ids = [str(value) for value in (session.get("session_theme_ids") or []) if str(value).strip()]
    primary_theme_id = str(session.get("session_theme_id") or "").strip()
    if primary_theme_id and primary_theme_id not in theme_ids:
        theme_ids.insert(0, primary_theme_id)
    return {
        "date": str(session.get("Date") or "")[:10],
        "session": {
            "id": str(session.get("id") or ""),
            "date": str(session.get("Date") or "")[:10],
            "session_sequence": session.get("session_sequence") or 1,
            "session_theme_id": primary_theme_id,
            "session_theme_ids": theme_ids,
            "theme_names": _pwa_session_theme_names(session, organization),
            "split": str(session.get("Split") or ""),
            "summary": str(session.get("Standardized Summary") or session.get("Summary") or ""),
            "notes": str(session.get("Notes") or ""),
            "movement_count": len(movements),
        },
        "movements": movements,
    }


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
    sessions_by_id = {str(session.get("id") or ""): session for session in tracker.get("training_sessions", []) or [] if session.get("id")}
    sessions_by_date: dict[str, list[dict]] = {}
    for session in tracker.get("training_sessions", []) or []:
        sessions_by_date.setdefault(str(session.get("Date") or "")[:10], []).append(session)

    def history_session(item: dict) -> dict | None:
        session_id = str(item.get("training_session_id") or "")
        if session_id and session_id in sessions_by_id:
            return sessions_by_id[session_id]
        date_value = str(item.get("date") or "")[:10]
        candidates = sessions_by_date.get(date_value, [])
        instance_id = str(item.get("movement_instance_id") or item.get("id") or "")
        for candidate in candidates:
            if instance_id and any(str(row.get("movement_instance_id") or row.get("id") or "") == instance_id for row in candidate.get("movement_items", []) or []):
                return candidate
        return candidates[0] if len(candidates) == 1 else None

    history_by_id: dict[str, list[dict]] = {}
    for movement in tracker.get("movements", {}).values():
        movement_id = str(movement.get("movement_id") or "")
        if movement_id not in movement_ids:
            continue
        history_by_id[movement_id] = sorted(
            [dict(item) for item in movement_items(tracker, movement_id)],
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
            session = history_session(item)
            session_items = session.get("movement_items", []) if session else []
            item_by_instance_id = {str(row.get("movement_instance_id") or row.get("id") or ""): row for row in session_items if isinstance(row, dict)}
            compact.append({
                "date": str(item.get("date") or "")[:10],
                "training_session_id": str(item.get("training_session_id") or (session or {}).get("id") or ""),
                "order": item.get("order_in_session") or item.get("order") or 0,
                "sets": sets,
                "summary": _pwa_set_summary(sets),
                "notes": str(item.get("notes") or ""),
                "max_weight": float(metrics.get("max_weight") or 0),
                "total_reps": int(metrics.get("total_reps") or 0),
                "volume": float(metrics.get("volume") or 0),
                "organization_relations": _pwa_relation_context(session, item, item_by_instance_id, catalog) if session else [],
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
    session_rollups = {}
    for date_value, movement_id, record in history_rows:
        session_id = str(record.get("training_session_id") or "")
        key = session_id or f"date:{date_value}"
        session = session_rollups.setdefault(key, {"id": session_id or date_value, "date": date_value, "related_movements": [], "records": []})
        name = catalog.get(movement_id, {}).get("display_name") or movement_id
        if name not in session["related_movements"]:
            session["related_movements"].append(name)
        session["records"].append(record)
    sessions = []
    for session in sorted(session_rollups.values(), key=lambda item: (item["date"], item["id"]), reverse=True):
        training = sessions_by_id.get(str(session["id"]), {})
        sessions.append({
            "id": session["id"],
            "date": session["date"],
            "split": training.get("Split") or f"{part['label']}训练",
            "title": training.get("Split") or f"{part['label']}训练",
            "theme_names": _pwa_session_theme_names(training, _pwa_training_organization(data_access)) if training else [],
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


def _pwa_session_theme_area(data_access: LedgerDataAccess, theme_id: str) -> dict | None:
    organization = _pwa_training_organization(data_access)
    theme = next((item for item in organization["session_themes"] if str(item.get("theme_id")) == str(theme_id)), None)
    if not theme:
        return None
    tracker = data_access._tracker()
    session_rows = []
    session_ids = set()
    for session in tracker.get("training_sessions", []) or []:
        ids = {str(session.get("session_theme_id") or ""), *(str(value) for value in session.get("session_theme_ids", []) or [])}
        if str(theme_id) not in ids:
            continue
        session_id = str(session.get("id") or "")
        session_ids.add(session_id)
        items = [dict(item) for item in session.get("movement_items", []) or []]
        names = [str(item.get("display_name") or item.get("movement_id") or "") for item in items if item.get("movement_id")]
        session_rows.append({
            "id": session_id,
            "date": str(session.get("Date") or "")[:10],
            "theme_names": _pwa_session_theme_names(session, organization),
            "title": str(session.get("session_theme_name") or theme.get("display_name") or "训练"),
            "split": str(session.get("Split") or ""),
            "related_count": len(names),
            "related_movements": names,
            "movement_summary": str(session.get("Standardized Summary") or "暂无完整动作摘要"),
            "full_summary": str(session.get("Standardized Summary") or "暂无完整动作摘要"),
            "notes": str(session.get("Notes") or ""),
        })
    session_rows.sort(key=lambda item: (item["date"], item["id"]), reverse=True)
    catalog = {item["movement_id"]: item for item in _pwa_movement_catalog(data_access)}
    sessions_by_id = {str(session.get("id") or ""): session for session in tracker.get("training_sessions", []) or [] if session.get("id")}
    movement_ids = {str(item.get("movement_id")) for session in tracker.get("training_sessions", []) or [] if str(session.get("id") or "") in session_ids for item in session.get("movement_items", []) or [] if item.get("movement_id")}
    movement_cards = []
    for movement_id in movement_ids:
        definition = catalog.get(movement_id)
        if not definition:
            continue
        history = [dict(item) for item in movement_items(tracker, movement_id) if str(item.get("training_session_id") or "") in session_ids]
        history.sort(key=lambda item: (str(item.get("date") or ""), int(item.get("order") or 9999)), reverse=True)
        compact = []
        for item in history:
            session = sessions_by_id.get(str(item.get("training_session_id") or ""), {})
            session_items = session.get("movement_items", []) if session else []
            item_by_instance_id = {str(row.get("movement_instance_id") or row.get("id") or ""): row for row in session_items if isinstance(row, dict)}
            compact.append({
                "date": str(item.get("date") or "")[:10],
                "training_session_id": str(item.get("training_session_id") or ""),
                "order": item.get("order_in_session") or item.get("order") or 0,
                "sets": item.get("sets") or [],
                "summary": _pwa_set_summary(item.get("sets") or []),
                "notes": str(item.get("notes") or ""),
                "organization_relations": _pwa_relation_context(session, item, item_by_instance_id, catalog) if session else [],
            })
        if not compact:
            continue
        movement_cards.append({"movement_id": movement_id, "display_name": definition.get("display_name") or movement_id, "english_name": definition.get("english_name") or "", "muscle_group": definition.get("muscle_group") or "", "pinned": bool(definition.get("pinned")), "focus_rank": int(definition.get("focus_rank") or 0), "sessions": len({row["training_session_id"] or row["date"] for row in compact}), "latest": compact[0], "previous": compact[1] if len(compact) > 1 else None, "best": compact[0], "recent": compact[:3]})
    movement_cards.sort(key=lambda item: (not item["pinned"], item["focus_rank"] or 9999, -item["sessions"], item["display_name"]))
    return {"id": str(theme_id), "label": str(theme.get("display_name") or theme_id), "labelEn": str(theme.get("display_name") or theme_id).upper(), "theme": theme, "session_count": len(session_rows), "movement_count": len(movement_cards), "latest_date": session_rows[0]["date"] if session_rows else "", "movements": movement_cards, "sessions": session_rows[:12]}


def create_app(
    data_access: LedgerDataAccess | None = None,
    data_module_registry: Path | None = None,
) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    data_access = data_access or LedgerDataAccess()
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
        if filename == "config.js":
            # Flask is the trusted local adapter.  Keep the tracked production
            # config authenticated while making the documented localhost
            # preview work without a CloudBase login prompt.
            return app.response_class(
                "window.FL_PWA_CONFIG = { apiBaseUrl: '/api', credentials: 'same-origin', requireWebAuth: false, appName: '每日健身 · 本地预览' };\n",
                content_type="application/javascript; charset=utf-8",
            )
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
        if action == "trainingOrganization":
            return jsonify({"ok": True, "data": _pwa_training_organization(data_access)})
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
        if action == "sessionThemeArea":
            area = _pwa_session_theme_area(data_access, request.args.get("themeId", ""))
            return jsonify({"ok": bool(area), "data": area} if area else {"ok": False, "code": "INVALID_SESSION_THEME", "message": "未识别训练主题。"})
        if action == "movementCatalog":
            return jsonify({"ok": True, "data": _pwa_movement_catalog(data_access)})
        if action == "bodyRecords":
            rows = sorted(data_access._tracker().get("daily_records", []), key=lambda item: str(item.get("Date") or ""), reverse=True)
            return jsonify({"ok": True, "data": rows[:max(1, min(int(request.args.get("limit", "30")), 50))]})
        if action == "dietRecords":
            rows = sorted(data_access._tracker().get("diet_records", []), key=lambda item: str(item.get("Date") or ""), reverse=True)
            return jsonify({"ok": True, "data": rows[:max(1, min(int(request.args.get("limit", "30")), 50))]})
        if action == "dataModules":
            return jsonify({"ok": True, "data": _pwa_data_module_contract(data_access, data_module_registry)})
        if action == "trainingRecords":
            rows = sorted(data_access._tracker().get("training_sessions", []), key=lambda item: (str(item.get("Date") or ""), int(item.get("session_sequence") or 0), str(item.get("id") or "")), reverse=True)
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
            return jsonify({"ok": True, "data": _pwa_training_session_detail(data_access, request.args.get("sessionId", ""), request.args.get("date", ""))})
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
    # The local viewer reads private archive data and is intentionally
    # localhost-only.  LAN access must not be enabled by the default entrypoint.
    app.run(host="127.0.0.1", port=5055, debug=False)


if __name__ == "__main__":
    main()
