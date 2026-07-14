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
    assert len(app["pages"]) == 7
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
    assert "notepad-card" in reference and "compact-input" in reference
    assert "copyNote" in reference and "clearNote" in reference
    assert "overview-link" not in reference
    assert "EXPAND" in reference and "COLLAPSE EDIT" in reference
    reference_js = (ROOT / "miniprogram" / "pages" / "reference" / "index.js").read_text(encoding="utf-8")
    assert "part-title" in reference and "label: theme.cn" in reference_js
    assert "notepadExpanded" in reference_js and "notepadFlipBack" in reference_js
    assert "flushDraft" in reference_js and "refreshDraft" in reference_js
    assert "wx.setClipboardData" in reference_js
    assert "createIntersectionObserver" in reference_js
    assert "#notepad-observer-anchor" in reference_js
    assert "disconnectNotepadObserver" in reference_js
    assert "onHide() { this.flushDraft(); this.disconnectNotepadObserver(); }" in reference_js
    assert "dockVisible !== this.data.dockVisible" in reference_js
    assert "wx.nextTick" in reference_js and "thresholds: [0, 1]" in reference_js
    assert "result.boundingClientRect" in reference_js and "rect.bottom <= 0" in reference_js
    assert "intersectionRatio" not in reference_js
    assert "onPageScroll" not in reference_js
    notepad = (ROOT / "miniprogram" / "utils" / "freeformNotepad.js").read_text(encoding="utf-8")
    assert 'STORAGE_KEY = "fitness-ledger:freeform-notepad:v2:current-training"' in notepad
    assert "migrateLegacy" not in notepad and "training-draft" not in notepad and ":v1:" not in notepad
    assert "function load()" in notepad and "function save(text)" in notepad and "function clear()" in notepad
    dock = ROOT / "miniprogram" / "components" / "freeformNotepad"
    for suffix in (".js", ".json", ".wxml", ".wxss"):
        assert (dock / f"index{suffix}").exists()
    dock_js = (dock / "index.js").read_text(encoding="utf-8")
    assert "notepad.load()" in dock_js and "notepad.save(this.noteText)" in dock_js
    assert "pageLifetimes" in dock_js and "show() { this.refresh(); }" in dock_js and "hide() { this.flush(); }" in dock_js
    assert "this.data.part" not in dock_js and "properties: { part:" not in dock_js
    assert "properties: { visible: { type: Boolean, value: true } }" in dock_js
    dock_wxss = (dock / "index.wxss").read_text(encoding="utf-8")
    assert "#fcf9f2" in dock_wxss
    assert "tone-coral" not in dock_wxss and "tone-teal" not in dock_wxss and "tone-violet" not in dock_wxss and "tone-cyan" not in dock_wxss
    assert ":host { position:fixed" in dock_wxss
    assert ".notepad-dock.is-hidden" in dock_wxss and "pointer-events:none" in dock_wxss
    assert "transition:opacity .2s ease-out,transform .2s ease-out" in dock_wxss
    dock_wxml = (dock / "index.wxml").read_text(encoding="utf-8")
    assert "TRAINING NOTE" in dock_wxml and "已自动保存" in dock_wxml
    assert "{{visible ? 'is-visible' : 'is-hidden'}}" in dock_wxml
    movement = (ROOT / "miniprogram" / "pages" / "movement" / "index.wxml").read_text(encoding="utf-8")
    record = (ROOT / "miniprogram" / "pages" / "record" / "index.wxml").read_text(encoding="utf-8")
    assert "<freeform-notepad />" in movement and "<freeform-notepad />" in record
    movement_js = (ROOT / "miniprogram" / "pages" / "movement" / "index.js").read_text(encoding="utf-8")
    record_js = (ROOT / "miniprogram" / "pages" / "record" / "index.js").read_text(encoding="utf-8")
    assert "&part=${this.data.selected}" in reference_js
    assert "part = options.part" in movement_js and "part = options.part" in record_js
    assert "notepad.load(this.data.selected)" not in reference_js
    assert "notepad.save(this.data.selected" not in reference_js
    assert "notepad.clear(this.data.selected)" not in reference_js
    assert "migrateLegacy" not in reference_js
    assert "notepad-observer-anchor" in reference
    assert "<freeform-notepad visible=\"{{dockVisible}}\" />" in reference
    assert "TRAINING NOTE / 训练记录" in reference and "neutral-notepad" in reference
    assert "tone-{{area.tone}}" in reference  # Page and Archive front keep body-part visual identity.
    reference_wxss = (ROOT / "miniprogram" / "pages" / "reference" / "index.wxss").read_text(encoding="utf-8")
    assert ".notepad-input" in reference_wxss and "font-size:25rpx; line-height:1.55" in reference_wxss
    assert ".compact-input" in reference_wxss and "padding:8rpx 0; font-size:25rpx;" in reference_wxss
    assert "训练频率" in reference and "最近训练" in reference and "按训练日" in reference
    training = (ROOT / "miniprogram" / "pages" / "training" / "index.wxml").read_text(encoding="utf-8")
    assert "搜索日期" in training and "查看当日训练" in training
    assert "draft-entry" not in training
    assert not (ROOT / "miniprogram" / "pages" / "today" / "index.js").exists()
    assert not (ROOT / "miniprogram" / "pages" / "home").exists()
    assert not (ROOT / "miniprogram" / "pages" / "search").exists()
    print("FITNESS_LEDGER_MINI_PROGRAM_MOBILE_WORKBENCH_OK")


if __name__ == "__main__":
    main()
