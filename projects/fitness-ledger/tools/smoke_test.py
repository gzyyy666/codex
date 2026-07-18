import copy
import json
import pathlib
import runpy
import tempfile


namespace = runpy.run_path(pathlib.Path(__file__).resolve().parents[1] / "stable_app.pyw")
temp_dir = pathlib.Path(tempfile.mkdtemp())
namespace["DATA_CHECK_STATE_FILE"] = temp_dir / "data_check_state.json"

raw = """2099-06-25

weight: 68.35

calories: 1780
protein: 135
carbs: 175
fat: 47

training: chest + shoulders

1. Nordic Flat Press
   17.5kg x 10 x 3
   20kg x 8 x 2

2. Cable Fly
   7.5kg x 12 x 3

3. Hammer Shoulder Press
   20kg x 10 x 3
   notes: controlled test note
"""


class DummyWindow:
    def destroy(self):
        pass


app = namespace["FitnessTrackerApp"]()
app.withdraw()
for method_name in ("acknowledge_selected_data_issue", "reset_acknowledged_data_issues", "refresh_data_check", "latest_day_status"):
    getattr(app, method_name).__func__.__globals__["DATA_CHECK_STATE_FILE"] = namespace["DATA_CHECK_STATE_FILE"]
app.data_check_state = {"acknowledged": {}}
globals_dict = app.commit_pending.__globals__
globals_dict["DATA_FILE"] = temp_dir / "tracker.json"
globals_dict["BACKUP_DIR"] = temp_dir / "backups"
globals_dict["MOVEMENT_DICTIONARY_FILE"] = temp_dir / "movement_dictionary.json"
globals_dict["messagebox"].showinfo = lambda *_args, **_kwargs: None
globals_dict["messagebox"].askyesno = lambda *_args, **_kwargs: True

app.database = copy.deepcopy(app.database)
namespace["write_json"](globals_dict["DATA_FILE"], app.database)
namespace["write_json"](globals_dict["MOVEMENT_DICTIONARY_FILE"], app.movement_dictionary)
app.command_service = namespace["LedgerCommandService"](
    globals_dict["DATA_FILE"],
    globals_dict["MOVEMENT_DICTIONARY_FILE"],
    globals_dict["BACKUP_DIR"],
    app.parse_for_shared_service,
)
before = (
    len(app.database["daily_records"]),
    len(app.database["diet_records"]),
    len(app.database["training_sessions"]),
)
app.pending = app.parse_entry(raw)
parsed_movements = app.pending["training"]["movements"]
assert len(parsed_movements) == 3
assert [len(movement["sets"]) for movement in parsed_movements] == [2, 1, 1]
assert parsed_movements[2]["notes"] == "controlled test note"

app.raw_text.insert("1.0", raw)
app.commit_pending(DummyWindow())
after = (
    len(app.database["daily_records"]),
    len(app.database["diet_records"]),
    len(app.database["training_sessions"]),
)
assert after == tuple(value + 1 for value in before)
assert app.database["training_sessions"][-1]["Notes"] == ""

day_number = app.database["training_sessions"][-1]["No."]
assert day_number == before[2] + 1
names = [
    movement["movement_id"]
    for movement in app.database["movements"].values()
    if any(record.get("training_day") == day_number for record in movement.get("history", []))
]
for expected in (
    "CHEST_001",
    "CHEST_005",
    "SHOULDER_005",
):
    assert expected in names

assert list(globals_dict["BACKUP_DIR"].glob("undo_tracker_*.json"))
app.undo_last_save()
assert (
    len(app.database["daily_records"]),
    len(app.database["diet_records"]),
    len(app.database["training_sessions"]),
) == before
assert not list(globals_dict["BACKUP_DIR"].glob("undo_tracker_*.json"))
assert list(globals_dict["BACKUP_DIR"].glob("undone_tracker_*.json"))

# Save again, then overwrite the same date without creating duplicate primary records.
app.pending = app.parse_entry(raw)
app.raw_text.insert("1.0", raw)
app.commit_pending(DummyWindow())
saved_counts = (
    len(app.database["daily_records"]),
    len(app.database["diet_records"]),
    len(app.database["training_sessions"]),
)
app.choose_duplicate_action = lambda *_args, **_kwargs: "overwrite"
replacement = raw.replace("weight: 68.35", "weight: 68.10")
app.pending = app.parse_entry(replacement)
app.raw_text.insert("1.0", replacement)
app.commit_pending(DummyWindow())
assert (
    len(app.database["daily_records"]),
    len(app.database["diet_records"]),
    len(app.database["training_sessions"]),
) == saved_counts
same_day_body = [row for row in app.database["daily_records"] if str(row.get("Date"))[:10] == "2099-06-25"]
assert len(same_day_body) == 1
assert same_day_body[0]["Weight (kg)"] == 68.10
assert any(record.get("superseded") for record in app.database["raw_entries"] if record.get("date") == "2099-06-25")

# Same-day additional training does not duplicate Body or Diet.
primary_counts = (len(app.database["daily_records"]), len(app.database["diet_records"]))
training_count = len(app.database["training_sessions"])
app.choose_duplicate_action = lambda *_args, **_kwargs: "append_training"
app.pending = app.parse_entry(raw)
app.raw_text.insert("1.0", raw)
app.commit_pending(DummyWindow())
assert (len(app.database["daily_records"]), len(app.database["diet_records"])) == primary_counts
assert len(app.database["training_sessions"]) == training_count + 1
assert app.database["training_sessions"][-1]["save_mode"] == "append_training"
assert app.database["training_sessions"][-1]["Notes"].startswith("同日追加训练。")

# A reviewed unknown movement can map to an existing dictionary entry without creating CUSTOM data.
mapping_raw = """2099-06-26
training: chest
1. 测试映射动作
10 x 10 x 1
"""
custom_before = len([item for item in app.movement_dictionary["movements"] if item["movement_id"].startswith("CUSTOM_")])
app.pending = app.parse_entry(mapping_raw)
app.open_review_window()
mapping_controls = app.review_movement_widgets[0]
mapping_controls["action"].set("Map to existing movement")
mapping_target = next(
    value for value in mapping_controls["mapping"].cget("values") if str(value).startswith("CHEST_001 | ")
)
mapping_controls["mapping"].set(mapping_target)
assert app.apply_review_edits()
mapped = app.pending["training"]["movements"][0]
assert mapped["_review_action"] == "map"
assert mapped["_mapped_movement_id"] == "CHEST_001"
mapped["display_name"] = "诺德士挂片推一"
for child in app.winfo_children():
    if isinstance(child, namespace["tk"].Toplevel):
        child.destroy()
app.raw_text.insert("1.0", mapping_raw)
app.commit_pending(DummyWindow())
custom_after = len([item for item in app.movement_dictionary["movements"] if item["movement_id"].startswith("CUSTOM_")])
assert custom_after == custom_before
assert "测试映射动作" in app.movement_definitions_by_id["CHEST_001"]["aliases"]

# Movement history records can be edited safely.
mapped_history = next(
    history
    for movement in app.database["movements"].values()
    if movement.get("movement_id") == "CHEST_001"
    for history in movement.get("history", [])
    if history.get("date") == "2099-06-26"
)
assert app.save_movement_history_records(
    [
        (
            mapped_history,
            {
                "order": "2",
                "sets_text": "12.5 × 8 × 3",
                "notes": "手工修正记录",
                "raw": "手工修正原始细节",
                "duration_minutes": "",
                "incline": "",
                "speed": "",
                "heart_rate": "",
            },
        )
    ]
)
assert mapped_history["order"] == 2
assert mapped_history["sets"] == [{"weight": 12.5, "reps": 8, "sets": 3}]
assert mapped_history["notes"] == "手工修正记录"

# Adding an alias later restores matching movements that were previously kept only in raw skipped data.
reconcile_raw = """2099-06-29
training: chest
1. 历史未分配下拉
35 x 12 x 2
notes: 别名回填测试
"""
raw_before_reconcile = reconcile_raw
app.database["raw_entries"].append(
    {
        "date": "2099-06-29",
        "text": reconcile_raw,
        "skipped_movements": ["历史未分配下拉"],
        "save_mode": "overwrite",
    }
)
app.database["training_sessions"].append({"No.": 999, "Date": "2099-06-29"})
namespace["write_json"](globals_dict["DATA_FILE"], app.database)
target_definition = app.movement_definitions_by_id["CHEST_001"]
target_tracker = app.tracker_movement_by_id("CHEST_001")
target_values = dict(target_definition)
target_values["aliases"] = [*target_definition.get("aliases", []), "历史未分配下拉"]
assert app.save_movement_definition(target_tracker, target_definition, target_values)
reconciled_raw = next(row for row in app.database["raw_entries"] if row.get("date") == "2099-06-29")
assert reconciled_raw["text"] == raw_before_reconcile
assert "历史未分配下拉" not in reconciled_raw.get("skipped_movements", [])
reconciled_history = next(
    history
    for history in app.tracker_movement_by_id("CHEST_001").get("history", [])
    if history.get("date") == "2099-06-29"
)
assert reconciled_history["sets"] == [{"weight": 35.0, "reps": 12, "sets": 2}]
assert reconciled_history["notes"] == "别名回填测试"
assert reconciled_history["source"] == "alias reconciliation"

# Add, rename, and delete a temporary custom movement; raw text remains preserved.
custom_raw = """2099-06-27
training: test
1. 临时待删除动作
20 x 10 x 2
"""
app.pending = app.parse_entry(custom_raw)
custom_movement = app.pending["training"]["movements"][0]
custom_movement["_review_action"] = "add"
custom_movement["display_name"] = "临时待删除动作"
custom_movement["_muscle_group"] = "Other"
app.raw_text.insert("1.0", custom_raw)
app.commit_pending(DummyWindow())
temporary_definition = app.movement_definitions_by_alias[namespace["normalize_name"]("临时待删除动作")]
temporary_id = temporary_definition["movement_id"]
temporary_tracker = next(
    movement for movement in app.database["movements"].values() if movement.get("movement_id") == temporary_id
)
assert app.save_movement_definition(
    temporary_tracker,
    temporary_definition,
    {
        "display_name": "临时重命名动作",
        "english_name": "Temporary Movement",
        "aliases": "临时待删除动作",
        "muscle_group": "测试",
        "category": "Strength",
        "equipment": "",
        "notes": "测试词典编辑",
    },
)
assert app.movement_definitions_by_id[temporary_id]["display_name"] == "临时重命名动作"
assert app.toggle_movement_definition(temporary_definition)
assert temporary_definition["active"] is False
app.refresh_movements()
assert all(
    movement.get("movement_id") != temporary_id
    for movement in app.movement_rows_by_item.values()
)
assert namespace["normalize_name"]("临时重命名动作") in app.movement_definitions_by_alias
app.pending = app.parse_entry("2099-06-28\ntraining: test\n1. 另一个待映射动作\n10 x 10 x 1")
app.open_review_window()
mapping_values = app.review_movement_widgets[0]["mapping"].cget("values")
assert not any(str(value).startswith(f"{temporary_id} | ") for value in mapping_values)
for child in app.winfo_children():
    if isinstance(child, namespace["tk"].Toplevel):
        child.destroy()
raw_count_before_delete = len(app.database["raw_entries"])
assert app.delete_movement_definition(temporary_id)
assert temporary_id not in app.movement_definitions_by_id
assert all(movement.get("movement_id") != temporary_id for movement in app.database["movements"].values())
assert len(app.database["raw_entries"]) == raw_count_before_delete

json.loads((temp_dir / "tracker.json").read_text(encoding="utf-8"))
app.destroy()
print("FITNESS_LEDGER_SMOKE_TEST_OK")
