import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "tracker.json"
DICTIONARY = ROOT / "data" / "movement_dictionary.json"
BACKUPS = ROOT / "data" / "backups"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: dict) -> None:
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(path)


def backup(path: Path, prefix: str, stamp: str) -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    target = BACKUPS / f"{prefix}_{stamp}.json"
    shutil.copy2(path, target)
    return target


def merge_tracker_rows(tracker: dict, movement_id: str, preferred_key: str) -> dict:
    matches = [
        (key, movement)
        for key, movement in tracker.get("movements", {}).items()
        if movement.get("movement_id") == movement_id
    ]
    if not matches:
        raise RuntimeError(f"Missing tracker movement: {movement_id}")
    canonical_key, canonical = next(
        ((key, movement) for key, movement in matches if key == preferred_key),
        matches[0],
    )
    histories = []
    history_ids = set()
    aliases = []
    for _key, movement in matches:
        for alias in movement.get("aliases", []):
            if alias and alias not in aliases:
                aliases.append(alias)
        for history in movement.get("history", []):
            history_id = history.get("id")
            identity = history_id or (
                history.get("date"),
                history.get("training_day"),
                history.get("order"),
                history.get("raw"),
            )
            if identity in history_ids:
                continue
            history_ids.add(identity)
            history["movement_id"] = movement_id
            histories.append(history)
    canonical["aliases"] = aliases
    canonical["history"] = sorted(
        histories,
        key=lambda row: (str(row.get("date", "")), int(row.get("order") or 0)),
    )
    tracker["movements"] = {
        key: movement
        for key, movement in tracker.get("movements", {}).items()
        if movement.get("movement_id") != movement_id or key == canonical_key
    }
    tracker["movements"][canonical_key] = canonical
    return canonical


tracker = read(DATA)
dictionary = read(DICTIONARY)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
tracker_backup = backup(DATA, "before_leg_merge_tracker", stamp)
dictionary_backup = backup(DICTIONARY, "before_leg_merge_dictionary", stamp)

leg_extension = merge_tracker_rows(tracker, "LEG_001", "legextensionquads")
leg_curl = merge_tracker_rows(tracker, "LEG_002", "legcurlhamstrings")

dictionary["movements"] = [
    definition
    for definition in dictionary.get("movements", [])
    if definition.get("movement_id") not in {"CUSTOM_003", "CUSTOM_004"}
]

extension_record = next(
    (record for record in leg_extension.get("history", []) if str(record.get("date", ""))[:10] == "2026-06-25"),
    None,
)
curl_record = next(
    (record for record in leg_curl.get("history", []) if str(record.get("date", ""))[:10] == "2026-06-25"),
    None,
)
if not extension_record or not curl_record:
    raise RuntimeError("Missing 2026-06-25 leg extension/curl records")

extension_sets = extension_record.get("sets", [])
curl_sets = curl_record.get("sets", [])
if extension_sets != [{"weight": 100.0, "reps": 12, "sets": 3}]:
    extension_record.setdefault("raw_original", extension_record.get("raw", ""))
    extension_record["sets"] = curl_sets
    extension_record["raw"] = "4. 腿屈伸\n100kg × 12 × 3"
    extension_record["corrected_at"] = stamp
    extension_record["correction"] = "User-confirmed swap with leg curl on 2026-06-25."
if curl_sets != [{"weight": 90.0, "reps": 12, "sets": 3}]:
    curl_record.setdefault("raw_original", curl_record.get("raw", ""))
    curl_record["sets"] = extension_sets
    curl_record["raw"] = "3. 腿弯举\n90kg × 12 × 3"
    curl_record["corrected_at"] = stamp
    curl_record["correction"] = "User-confirmed swap with leg extension on 2026-06-25."

definitions = {
    definition.get("movement_id"): definition
    for definition in dictionary.get("movements", [])
    if definition.get("movement_id")
}
history_by_day = {}
for movement in tracker.get("movements", {}).values():
    for history in movement.get("history", []):
        day = history.get("training_day")
        if day in (None, ""):
            continue
        history_by_day.setdefault(int(day), []).append((movement, history))
for session in tracker.get("training_sessions", []):
    try:
        day = int(session.get("No."))
    except (TypeError, ValueError):
        continue
    records = sorted(history_by_day.get(day, []), key=lambda item: int(item[1].get("order") or 0))
    if records:
        session["Standardized Summary"] = "；".join(
            f"第{history.get('order')}个动作："
            f"{definitions.get(history.get('movement_id') or movement.get('movement_id'), {}).get('display_name') or movement.get('name', '')}"
            for movement, history in records
        )

write(DATA, tracker)
write(DICTIONARY, dictionary)
print(f"tracker_backup={tracker_backup}")
print(f"dictionary_backup={dictionary_backup}")
print("LEG_MOVEMENT_MERGE_OK")
