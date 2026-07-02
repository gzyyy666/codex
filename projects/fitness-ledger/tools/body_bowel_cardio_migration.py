import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "tracker.json"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    temp.replace(path)


def section(text: str, labels: tuple[str, ...], stop_labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(label) for label in stop_labels)
    match = re.search(
        rf"(?ms)^(?:{label_pattern})\s*[:：]\s*(.*?)(?=^(?:{stop_pattern})\s*[:：]|\Z)",
        text,
        re.I,
    )
    return match.group(1).strip() if match else ""


def one_line(value: str) -> str:
    return "\n".join(line.strip() for line in str(value or "").splitlines() if line.strip())


def ensure_body_record(data: dict, record_date: str) -> dict:
    for record in data.get("daily_records", []):
        if str(record.get("Date", ""))[:10] == record_date:
            return record
    record = {"id": record_date, "Date": record_date, "source": "manual repair"}
    data.setdefault("daily_records", []).append(record)
    return record


data = read_json(DATA)
raw_by_date = {
    str(item.get("date", ""))[:10]: item.get("text", "")
    for item in data.get("raw_entries", [])
    if str(item.get("date", ""))[:10] in {"2026-06-25", "2026-06-26"}
}
training_by_date = {
    str(item.get("Date", ""))[:10]: item
    for item in data.get("training_sessions", [])
    if str(item.get("Date", ""))[:10] in {"2026-06-25", "2026-06-26"}
}
diet_by_date = {
    str(item.get("Date", ""))[:10]: item
    for item in data.get("diet_records", [])
    if str(item.get("Date", ""))[:10] in {"2026-06-25", "2026-06-26"}
}

for record_date in ("2026-06-25", "2026-06-26"):
    raw = raw_by_date.get(record_date, "")
    body = ensure_body_record(data, record_date)
    training = training_by_date.get(record_date, {})
    diet = diet_by_date.get(record_date, {})

    body.setdefault("Context", "")
    body.setdefault("Bowel Movement", "")
    body["Training"] = training.get("Split", "") or section(raw, ("training", "训练"), ("cardio", "有氧", "diet", "饮食", "notes", "备注")).splitlines()[0].strip()
    body["Cardio"] = "跑步机爬坡"
    body["Notes"] = one_line(section(raw, ("notes", "备注"), ()))

    diet_section = section(raw, ("diet", "饮食"), ("notes", "备注"))
    if diet and diet_section:
        diet["Food Summary"] = one_line(diet_section)
        diet["Notes"] = ""

    training_section = section(raw, ("training", "训练"), ("cardio", "有氧", "diet", "饮食", "notes", "备注"))
    if training and training_section:
        lines = training_section.splitlines()
        if lines:
            training["Split"] = lines[0].strip() or training.get("Split", "")
            training["Raw Record"] = "\n".join(lines[1:]).strip()
        training["Notes"] = ""

write_json(DATA, data)
print("BODY_BOWEL_CARDIO_MIGRATION_OK")
