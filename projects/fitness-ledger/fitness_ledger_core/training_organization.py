"""Session-level training organization and movement-level progress taxonomy.

The tracker stores facts; this module adds a small, deterministic read/write
organization layer around those facts.  A session theme describes how one
training session was named or organized.  A movement category describes the
long-term progress bucket for one formal movement.  They are intentionally
different concepts and the migration never infers a session theme from a
movement body area.
"""

from __future__ import annotations

import copy
import re
from typing import Any


SCHEMA_VERSION = "fitness-ledger-training-organization-v1"

# Session Themes are user data, not a built-in body-part taxonomy. Existing
# ledgers obtain their initial themes from stored session labels; an empty/new
# ledger intentionally starts with no theme and can still record a session.
DEFAULT_SESSION_THEMES: tuple[dict, ...] = ()

THEME_COLOR_KEYS = ("ember", "teal", "violet", "blue", "amber", "rose", "indigo", "green")

DEFAULT_MOVEMENT_CATEGORIES = (
    {"category_id": "chest", "display_name": "Chest", "active": True, "sort_order": 10, "system": True},
    {"category_id": "shoulders", "display_name": "Shoulders", "active": True, "sort_order": 20, "system": True},
    {"category_id": "back", "display_name": "Back", "active": True, "sort_order": 30, "system": True},
    {"category_id": "legs", "display_name": "Legs", "active": True, "sort_order": 40, "system": True},
    {"category_id": "glutes", "display_name": "Glutes", "active": False, "sort_order": 50, "system": True},
    {"category_id": "arms", "display_name": "Arms", "active": True, "sort_order": 60, "system": True},
    {"category_id": "core", "display_name": "Core", "active": True, "sort_order": 70, "system": True},
    {"category_id": "cardio", "display_name": "Cardio", "active": False, "sort_order": 80, "system": True},
)

MUSCLE_GROUP_TO_CATEGORY = {
    "chest": "chest",
    "pecs": "chest",
    "back": "back",
    "lats": "back",
    "pull": "back",
    "shoulder": "shoulders",
    "shoulders": "shoulders",
    "delt": "shoulders",
    "delts": "shoulders",
    "legs": "legs",
    "leg": "legs",
    "lower": "legs",
    "glute": "glutes",
    "glutes": "glutes",
    "臀": "glutes",
    "arms": "arms",
    "arm": "arms",
    "biceps": "arms",
    "triceps": "arms",
    "手臂": "arms",
    "core": "core",
    "腹": "core",
    "cardio": "cardio",
    "aerobic": "cardio",
    "有氧": "cardio",
}


def normalize_label(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").casefold())


def _safe_order(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def theme_color_key(theme_id: Any) -> str:
    """Return a stable generic color slot without inferring training meaning."""
    value = str(theme_id or "theme").encode("utf-8")
    checksum = sum((index + 1) * byte for index, byte in enumerate(value))
    return THEME_COLOR_KEYS[checksum % len(THEME_COLOR_KEYS)]


def _merge_catalog(defaults: tuple[dict, ...], existing: Any, id_key: str) -> list[dict]:
    rows = existing if isinstance(existing, list) else []
    by_id = {
        str(item.get(id_key, "")).strip(): copy.deepcopy(item)
        for item in rows
        if isinstance(item, dict) and str(item.get(id_key, "")).strip()
    }
    merged: list[dict] = []
    for index, default in enumerate(defaults):
        row = copy.deepcopy(default)
        row.update(by_id.pop(str(default[id_key]), {}))
        row[id_key] = str(default[id_key])
        row["display_name"] = str(row.get("display_name") or default["display_name"]).strip()
        row["active"] = bool(row.get("active", True))
        row["sort_order"] = _safe_order(row.get("sort_order"), (index + 1) * 10)
        row["system"] = bool(default.get("system", False))
        merged.append(row)
    for index, row in enumerate(by_id.values(), start=1):
        row["display_name"] = str(row.get("display_name") or row.get(id_key) or "未命名").strip()
        row["active"] = bool(row.get("active", True))
        row["sort_order"] = _safe_order(row.get("sort_order"), 1000 + index * 10)
        row.setdefault("system", False)
        merged.append(row)
    if id_key == "theme_id":
        for row in merged:
            row["focus_rank"] = max(0, _safe_order(row.get("focus_rank"), 0))
            row["pinned"] = bool(row.get("pinned", False) or row["focus_rank"] > 0)
            row["color_key"] = str(row.get("color_key") or theme_color_key(row.get(id_key))).strip()
            # The old artwork encoded one person's five-day split. Keep the
            # compatibility key, but make the catalog itself image-free.
            row["artwork_key"] = ""
    return sorted(merged, key=lambda item: (int(item["sort_order"]), normalize_label(item["display_name"]), str(item[id_key])))


def movement_category_id(definition: dict | None, item: dict | None = None) -> str | None:
    definition = definition or {}
    item = item or {}
    explicit = str(item.get("movement_category_id") or definition.get("movement_category_id") or definition.get("progress_category_id") or "").strip()
    if explicit:
        return explicit
    group = str(definition.get("muscle_group") or item.get("muscle_group") or "").strip().casefold()
    if group in MUSCLE_GROUP_TO_CATEGORY:
        return MUSCLE_GROUP_TO_CATEGORY[group]
    return None


def _theme_id_for_label(label: str, themes: list[dict]) -> str | None:
    key = normalize_label(label)
    if not key:
        return None
    for theme in themes:
        names = [theme.get("display_name"), *(theme.get("aliases") or [])]
        if key in {normalize_label(name) for name in names if str(name or "").strip()}:
            return str(theme.get("theme_id") or "")
    return None


def _ensure_theme_for_legacy_label(themes: list[dict], label: str, preferred_id: str = "") -> str:
    label = str(label or "").strip()
    if not label:
        return ""
    existing = _theme_id_for_label(label, themes)
    if existing:
        return existing
    base = str(preferred_id or "").strip() or f"theme:{normalize_label(label) or 'custom'}"
    theme_id = base
    used = {str(item.get("theme_id")) for item in themes}
    index = 2
    while theme_id in used:
        theme_id = f"{base}:{index}"
        index += 1
    themes.append({
        "theme_id": theme_id,
        "display_name": label,
        "active": True,
        "sort_order": 1000 + len(themes) * 10,
        "artwork_key": "",
        "color_key": theme_color_key(theme_id),
        "focus_rank": 0,
        "pinned": False,
        "system": False,
    })
    return theme_id


def normalize_training_organization(database: dict, dictionary: dict) -> tuple[dict, bool]:
    """Normalize organization metadata and derived order fields in memory.

    The function is intentionally deterministic for old data: it uses the
    existing session Split/title and stored movement order, never current time
    and never a body-area combination to invent a session theme.
    """
    changed = False
    config = database.get("training_organization")
    config = copy.deepcopy(config) if isinstance(config, dict) else {}
    themes = _merge_catalog(DEFAULT_SESSION_THEMES, config.get("session_themes"), "theme_id")
    categories = _merge_catalog(DEFAULT_MOVEMENT_CATEGORIES, config.get("movement_categories"), "category_id")
    definitions = {
        str(item.get("movement_id")): item
        for item in dictionary.get("movements", []) or []
        if isinstance(item, dict) and str(item.get("movement_id", "")).strip()
    }
    sessions = database.get("training_sessions", [])
    sessions = sessions if isinstance(sessions, list) else []
    by_date: dict[str, list[dict]] = {}
    for session in sessions:
        label = str(
            session.get("session_theme_name")
            or session.get("Session Theme")
            or session.get("Split")
            or session.get("training_title")
            or ""
        ).strip()
        stored_theme_id = str(session.get("session_theme_id") or "").strip()
        theme_id = stored_theme_id or _theme_id_for_label(label, themes) or ""
        theme = next((item for item in themes if item.get("theme_id") == theme_id), None)
        if theme is None and label:
            theme_id = _ensure_theme_for_legacy_label(themes, label, stored_theme_id)
            theme = next(item for item in themes if item.get("theme_id") == theme_id)
        if session.get("session_theme_id") != theme_id:
            session["session_theme_id"] = theme_id
            changed = True
        theme_name = str(theme.get("display_name") if theme else "")
        if session.get("session_theme_name") != theme_name:
            session["session_theme_name"] = theme_name
            changed = True
        by_date.setdefault(str(session.get("Date") or "")[:10], []).append(session)

    for date_value, date_sessions in by_date.items():
        date_sessions.sort(key=lambda row: (_safe_order(row.get("No."), 999999), str(row.get("id", ""))))
        for session_index, session in enumerate(date_sessions, start=1):
            if session.get("session_sequence") != session_index:
                session["session_sequence"] = session_index
                changed = True
            category_counters: dict[str, int] = {}
            items = session.get("movement_items", [])
            if not isinstance(items, list):
                items = []
                session["movement_items"] = items
                changed = True
            indexed = list(enumerate(item for item in items if isinstance(item, dict)))
            indexed.sort(key=lambda pair: (_safe_order(pair[1].get("order_in_session", pair[1].get("order")), pair[0] + 1)) )
            for fallback_index, item in indexed:
                order_in_session = _safe_order(item.get("order_in_session", item.get("order")), fallback_index + 1)
                if item.get("order_in_session") != order_in_session:
                    item["order_in_session"] = order_in_session
                    changed = True
                if item.get("order") in (None, ""):
                    item["order"] = order_in_session
                    changed = True
                definition = definitions.get(str(item.get("movement_id") or ""))
                category_id = movement_category_id(definition, item)
                if "movement_category_id" not in item or item.get("movement_category_id") != category_id:
                    item["movement_category_id"] = category_id
                    changed = True
                if category_id:
                    category_counters[category_id] = category_counters.get(category_id, 0) + 1
                    relative = category_counters[category_id]
                else:
                    relative = None
                if "order_in_category" not in item or item.get("order_in_category") != relative:
                    item["order_in_category"] = relative
                    changed = True

    normalized = {
        "schema": SCHEMA_VERSION,
        "session_themes": themes,
        "movement_categories": categories,
    }
    if database.get("training_organization") != normalized:
        database["training_organization"] = normalized
        changed = True
    if database.get("training_organization_schema_version") != SCHEMA_VERSION:
        database["training_organization_schema_version"] = SCHEMA_VERSION
        changed = True
    return database, changed


def organization_catalog(database: dict, dictionary: dict) -> dict:
    normalized, _changed = normalize_training_organization(copy.deepcopy(database), dictionary)
    config = normalized["training_organization"]
    return {
        "schema": SCHEMA_VERSION,
        "session_themes": copy.deepcopy(config["session_themes"]),
        "movement_categories": copy.deepcopy(config["movement_categories"]),
    }


def active_category_ids(database: dict, dictionary: dict) -> set[str]:
    return {
        str(item.get("category_id"))
        for item in organization_catalog(database, dictionary)["movement_categories"]
        if item.get("active", True)
    }
