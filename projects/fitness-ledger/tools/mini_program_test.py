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
    print("FITNESS_LEDGER_MINI_PROGRAM_SKELETON_OK")


if __name__ == "__main__":
    main()
