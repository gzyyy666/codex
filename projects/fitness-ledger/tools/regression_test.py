import copy
import pathlib
import re
import runpy
import tempfile
from types import SimpleNamespace


namespace = runpy.run_path(pathlib.Path(__file__).resolve().parents[1] / "stable_app.pyw")
temp_dir = pathlib.Path(tempfile.mkdtemp())
namespace["DATA_CHECK_STATE_FILE"] = temp_dir / "data_check_state.json"
app = namespace["FitnessTrackerApp"]()
app.withdraw()
for method_name in ("acknowledge_selected_data_issue", "reset_acknowledged_data_issues", "refresh_data_check", "latest_day_status"):
    getattr(app, method_name).__func__.__globals__["DATA_CHECK_STATE_FILE"] = namespace["DATA_CHECK_STATE_FILE"]
app.data_check_state = {"acknowledged": {}}
raw_entries_before = copy.deepcopy(app.database.get("raw_entries", []))

dictionary = namespace["load_movement_dictionary"]()
assert len(dictionary["movements"]) >= 29
assert len({item["movement_id"] for item in dictionary["movements"]}) == len(dictionary["movements"])
assert all(movement.get("movement_id") for movement in app.database["movements"].values())
assert all(
    record.get("movement_id") == movement.get("movement_id")
    for movement in app.database["movements"].values()
    for record in movement.get("history", [])
)
assert not {"CUSTOM_003", "CUSTOM_004"} & {item["movement_id"] for item in dictionary["movements"]}
for movement_id, expected_sets in (
    ("LEG_001", [{"weight": 100.0, "reps": 12, "sets": 3}]),
    ("LEG_002", [{"weight": 90.0, "reps": 12, "sets": 3}]),
):
    matching = [movement for movement in app.database["movements"].values() if movement.get("movement_id") == movement_id]
    assert len(matching) == 1
    june_25 = next(record for record in matching[0]["history"] if record.get("date") == "2026-06-25")
    assert june_25["sets"] == expected_sets
    assert june_25.get("raw_original")


def has_horizontal_scrollbar(tree):
    parent = tree.master
    return any(
        isinstance(child, namespace["ttk"].Scrollbar) and str(child.cget("orient")) == "horizontal"
        for child in parent.winfo_children()
    )


assert tuple(app.body_table["columns"]) == (
    "date",
    "weight",
    "bowel",
    "training",
    "cardio",
    "notes",
)
assert tuple(app.diet_table["columns"]) == (
    "date",
    "calories",
    "protein",
    "carbs",
    "fat",
    "food",
    "notes",
)
assert tuple(app.training_table["columns"]) == (
    "day",
    "date",
    "split",
    "summary",
    "notes",
)
assert tuple(app.data_check_table["columns"]) == ("severity", "date", "area", "issue", "action", "open")
recent_dates = app.recent_record_dates(3)
assert 1 <= len(recent_dates) <= 3
assert app.today_status_title.get() == recent_dates[0]
assert "体重" in app.today_status_text.get()
assert len(app.recent_records_frame.winfo_children()) == len(recent_dates)
app.open_movement_dictionary_manager()
assert tuple(app.dictionary_manager_table["columns"]) == (
    "status",
    "display",
    "english",
    "muscle",
    "category",
    "equipment",
    "aliases",
    "id",
)
assert "date" not in app.dictionary_manager_table["columns"]
assert "history" not in app.dictionary_manager_table["columns"]
assert len(app.dictionary_manager_table.get_children()) == len(app.movement_dictionary["movements"])
dictionary_windows = [child for child in app.winfo_children() if isinstance(child, namespace["tk"].Toplevel)]
for window in dictionary_windows:
    window.destroy()
assert has_horizontal_scrollbar(app.body_table)
assert has_horizontal_scrollbar(app.diet_table)
assert has_horizontal_scrollbar(app.training_table)
assert has_horizontal_scrollbar(app.movement_table)
assert namespace["make_cell_preview"]("short", 10) == "short"
assert namespace["make_cell_preview"]("a very long table value", 12).endswith("...")
assert namespace["extract_bowel_movement"]("\u6392\u4fbf\uff1a\u6709") == "\u6709"
assert namespace["extract_bowel_movement"]("bowel: normal") == "normal"

body_before = len(app.body_table.get_children())
app.database["daily_records"].append({"Date": "", "Weight (kg)": None, "Notes": "invalid display row"})
app.refresh_body()
assert len(app.body_table.get_children()) == body_before
app.database["daily_records"].pop()

body_item = app.body_table.get_children()[0]
app.body_table.selection_set(body_item)
app.open_selected_body_detail()

matrix_columns = list(app.movement_table["columns"])
assert matrix_columns[0] == "movement"
assert matrix_columns[1:] == sorted(matrix_columns[1:])
assert matrix_columns[1:] == app.get_movement_matrix_dates()

matrix_rows = {
    app.movement_table.item(item, "values")[0]: app.movement_table.item(item, "values")
    for item in app.movement_table.get_children()
}
pulldown = matrix_rows["诺德士高拉"]
assert "Day 2" in pulldown[matrix_columns.index("2026-06-16")]
assert "Day 7" in pulldown[matrix_columns.index("2026-06-21")]
assert any(key[0] in app.movement_table.get_children() for key in app.matrix_cell_detail_map)

matrix_detail_key = next(iter(app.matrix_cell_detail_map))
matrix_item, matrix_column = matrix_detail_key
matrix_bbox = app.movement_table.bbox(matrix_item, matrix_column)
if matrix_bbox:
    app.open_movement_cell_detail(SimpleNamespace(x=matrix_bbox[0] + 2, y=matrix_bbox[1] + 2))

columns_before_search = tuple(app.movement_table["columns"])
app.movement_search.set("Flat")
assert tuple(app.movement_table["columns"]) == columns_before_search
assert len(app.movement_table.get_children()) == 1
assert app.movement_table.item(app.movement_table.get_children()[0], "values")[0] == "诺德士挂片推一"
assert app.matrix_cell_detail_map
assert all(key[0] in app.movement_table.get_children() for key in app.matrix_cell_detail_map)
app.movement_search.set("")

parsed = app.parse_entry(
    "6.25\ntraining: Chest\n"
    "1. 诺德士平板推 10kg x 10 x 3\n"
    "2. 挂片推一 15kg x 8 x 2"
)
assert [item["movement_id"] for item in parsed["training"]["movements"]] == ["CHEST_001", "CHEST_001"]
assert [item["display_name"] for item in parsed["training"]["movements"]] == ["诺德士挂片推一", "诺德士挂片推一"]

parsed_with_notes = app.parse_entry(
    "2026-06-27\ntraining: 背部\n"
    "1. 诺德士拉背拨片\n"
    "   100 × 12 × 1\n"
    "   notes: 感受好，最后力竭。\n"
    "2. 回归测试新动作\n"
    "   20 × 12 × 3"
)
assert parsed_with_notes["training"]["movements"][0]["notes"] == "感受好，最后力竭。"
namespace["messagebox"].askyesnocancel = lambda *_args, **_kwargs: True
approved = app.review_new_movements(parsed_with_notes["training"]["movements"])
assert namespace["normalize_name"]("回归测试新动作") in approved
assert namespace["normalize_name"]("诺德士拉背拨片") not in approved

unnumbered_input = """2026-06-29
weight: 68.20
training: 肩部、手臂
1.
Y举
5 × 10 × 1
7.5 × 10 × 3

哑铃飞鸟
7.5 × 15 × 1
10 × 12 × 3

俯身哑铃肩伸
5 × 20 × 2

龙门架后束飞鸟
5 × 10 × 1
器械反飞
40 × 12 × 1
50 × 15 × 1

绳索三头下压
15 × 15 × 2
15 × 12 × 1

肩伸位二头弯举
60 × 12 × 2
60 × 13 × 1

cardio:
跑步机有氧 30分钟
diet:
早餐：
燕麦 约50g
notes:
今日状态正常。"""
parsed_unnumbered = app.parse_entry(unnumbered_input)
assert [movement["display_name"] for movement in parsed_unnumbered["training"]["movements"]] == [
    "Y举",
    "哑铃飞鸟",
    "俯身哑铃肩伸",
    "龙门架后束飞鸟",
    "器械反飞",
    "绳索三头下压",
    "肩伸位二头弯举",
]
assert [movement["order"] for movement in parsed_unnumbered["training"]["movements"]] == list(range(1, 8))
assert all(movement["movement_id"] for movement in parsed_unnumbered["training"]["movements"])
assert app.review_new_movements(parsed_unnumbered["training"]["movements"]) == set()
assert parsed_unnumbered["body"]["cardio_summary"] == "跑步机有氧 30分钟"
assert all(movement["name"] not in {"Cardio", "有氧", "跑步机"} for movement in parsed_unnumbered["training"]["movements"])

back_with_inline_notes = """2026-06-30
weight: 68.35
排便: 否
calories: 1200
protein: 104
carbs: 129
fat: 27
training: 背部

引体向上
自重 × 12 × 1
自重 × 10 × 2
notes: 未完全力竭。
诺德士拉背拨片
120 × 12 × 1
120 × 11 × 1
110 × 12 × 1
诺德士高拉
120 × 12 × 1
130 × 12 × 1
130 × 10 × 1
悍马拉背一
15 × 12 × 1
20 × 12 × 1
22.5 × 12 × 1
悍马拉背二
20 × 12 × 1
25 × 12 × 2

cardio:
跑步机有氧 30分钟

diet:
早餐：
饺子 200g

notes:
今日背训状态异常。"""
parsed_back = app.parse_entry(back_with_inline_notes)
assert [movement["display_name"] for movement in parsed_back["training"]["movements"]] == [
    "引体向上",
    "诺德士拉背拨片",
    "诺德士高拉",
    "悍马拉背一",
    "悍马拉背二",
]
assert parsed_back["training"]["movements"][0]["notes"] == "未完全力竭。"
assert parsed_back["training"]["movements"][0]["sets"] == [
    {"weight": 0.0, "weight_text": "自重", "reps": 12, "sets": 1},
    {"weight": 0.0, "weight_text": "自重", "reps": 10, "sets": 2},
]
assert parsed_back["body"]["notes"] == "今日背训状态异常。"
assert parsed_back["body"]["cardio_summary"] == "跑步机有氧 30分钟"

for session in app.database["training_sessions"]:
    assert not re.search(r"\b(?:Shoulders|Back|Chest|Walk|Abs|Legs)\b", str(session.get("Split", "")), re.I)

recent_body = {record.get("Date"): record for record in app.database.get("daily_records", [])}
assert recent_body["2026-06-25"].get("Cardio") == "\u8dd1\u6b65\u673a\u722c\u5761"
assert "\u8dd1\u6b65\u673a\u722c\u5761" in recent_body["2026-06-26"].get("Cardio", "")

diet_item = app.diet_table.get_children()[0]
app.diet_table.selection_set(diet_item)
app.open_selected_diet_detail()
training_item = app.training_table.get_children()[0]
app.training_table.selection_set(training_item)
app.open_selected_training_detail()
app.open_selected_training_raw_detail()
detail_windows = [child for child in app.winfo_children() if isinstance(child, namespace["tk"].Toplevel)]
assert len(detail_windows) >= 4
for window in detail_windows:
    window.destroy()

app.raw_text.insert(
    "1.0",
    "2099-07-01\nweight: 70\ncalories: 1800\nprotein: 120\ncarbs: 180\nfat: 60\n"
    "training: 肩部\n1. Y举\n5 × 12 × 3\ncardio:\nnone\ndiet:\n早餐：燕麦",
)
app.parse_and_review()
assert app.review_widgets["body"]["weight"]
weight_widget = app.review_widgets["body"]["weight"]
weight_widget.delete("1.0", "end")
weight_widget.insert("1.0", "69.5")
app.review_widgets["body"]["cardio_summary"].delete("1.0", "end")
app.review_widgets["body"]["cardio_summary"].insert("1.0", "跑步机 20 分钟")
assert app.apply_review_edits()
assert app.pending["body"]["weight"] == 69.5
assert app.pending["body"]["cardio_summary"] == "跑步机 20 分钟"
app.refresh_review_summary()
assert "体重：69.5" in app.review_summary_var.get()
assert "有氧：跑步机 20 分钟" in app.review_summary_var.get()
assert "动作数：1" in app.review_summary_var.get()
assert any("缺少排便" in warning for warning in app.collect_review_warnings(app.pending))
review_windows = [child for child in app.winfo_children() if isinstance(child, namespace["tk"].Toplevel)]
for window in review_windows:
    window.destroy()

issues = app.collect_data_issues()
assert isinstance(issues, list)
assert not any("缺少排便" in issue["issue"] for issue in issues)
assert not any("引体向上" in issue["issue"] and "没有 sets" in issue["issue"] for issue in issues)
pull_up = next(movement for movement in app.database["movements"].values() if movement.get("movement_id") == "BACK_001")
pull_up["history"].append({"date": "2099-07-02", "sets": [], "cardio": {}, "raw": "自重引体"})
pull_up_issues = app.collect_data_issues()
assert not any(issue["date"] == "2099-07-02" and "没有 sets" in issue["issue"] for issue in pull_up_issues)
pull_up["history"].pop()
app.refresh_data_check()
assert len(app.data_check_table.get_children()) == len(issues)

target_record = {"id": "data-check-target", "Date": "2099-07-03", "Weight (kg)": None, "Notes": ""}
app.database["daily_records"].append(target_record)
app.refresh_body()
app.refresh_data_check()
target_item = next(
    item_id
    for item_id, issue in app.data_check_issues_by_item.items()
    if issue.get("target_id") == "data-check-target"
)
app.data_check_table.selection_set(target_item)
app.open_selected_data_issue()
target_windows = [child for child in app.winfo_children() if isinstance(child, namespace["tk"].Toplevel)]
assert target_windows
for window in target_windows:
    window.destroy()
issues_before_ack = len(app.data_check_table.get_children())
namespace["messagebox"].askyesno = lambda *_args, **_kwargs: True
app.data_check_table.selection_set(target_item)
app.acknowledge_selected_data_issue()
assert len(app.data_check_table.get_children()) == issues_before_ack - 1
assert namespace["DATA_CHECK_STATE_FILE"].exists()
state = namespace["read_json"](namespace["DATA_CHECK_STATE_FILE"], {})
assert state.get("acknowledged")
app.reset_acknowledged_data_issues()
assert len(app.data_check_table.get_children()) == issues_before_ack
app.database["daily_records"].pop()
app.refresh_all()

database_snapshot = copy.deepcopy(app.database)
app.destroy()
assert database_snapshot["raw_entries"] == raw_entries_before
print("FITNESS_LEDGER_REGRESSION_OK")
