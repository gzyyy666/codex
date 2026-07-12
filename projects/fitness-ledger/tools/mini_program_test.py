from __future__ import annotations

import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / "mini_program"


def main() -> None:
    config = json.loads((ROOT / "project.config.json").read_text(encoding="utf-8"))
    app = json.loads((ROOT / "miniprogram" / "app.json").read_text(encoding="utf-8"))
    assert config["miniprogramRoot"] == "miniprogram/"
    assert config["cloudfunctionRoot"] == "cloudfunctions/"
    assert len(app["pages"]) == 8
    for page in app["pages"]:
        base = ROOT / "miniprogram" / page
        for suffix in (".js", ".json", ".wxml", ".wxss"):
            assert base.with_suffix(suffix).exists(), f"Missing {base.with_suffix(suffix)}"
    cloud = (ROOT / "cloudfunctions" / "ledgerRead" / "index.js").read_text(encoding="utf-8")
    for forbidden in (".add(", ".update(", ".set(", ".remove("):
        assert forbidden not in cloud
    assert 'case "bodyAreas"' in cloud
    assert 'case "bodyArea"' in cloud
    assert 'case "bodyRecords"' in cloud
    assert 'case "dietRecords"' in cloud
    assert 'case "trainingRecords"' in cloud
    assert app["pages"][0] == "pages/reference/index"
    assert app["tabBar"]["list"][0]["pagePath"] == "pages/reference/index"
    assert app["tabBar"]["list"][1]["pagePath"] == "pages/training/index"
    reference = (ROOT / "miniprogram" / "pages" / "reference" / "index.wxml").read_text(encoding="utf-8")
    assert "动作与最近表现" in reference
    assert "Standardized Summary" not in reference
    assert "训练频率" in reference and "最近训练" in reference and "按训练日" in reference
    training = (ROOT / "miniprogram" / "pages" / "training" / "index.wxml").read_text(encoding="utf-8")
    assert "搜索日期" in training and "查看当日训练" in training
    assert not (ROOT / "miniprogram" / "pages" / "home").exists()
    assert not (ROOT / "miniprogram" / "pages" / "search").exists()
    print("FITNESS_LEDGER_MINI_PROGRAM_MOBILE_WORKBENCH_OK")


if __name__ == "__main__":
    main()
