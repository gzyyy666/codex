"""Contract checks for the isolated CloudBase PWA read function."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FUNCTION = ROOT / "mini_program" / "cloudfunctions" / "ledgerWebRead"


def main() -> None:
    index = FUNCTION / "index.js"
    package = FUNCTION / "package.json"
    readme = FUNCTION / "README.md"
    for path in (index, package, readme):
        assert path.is_file(), f"missing web function file: {path}"

    source = index.read_text(encoding="utf-8")
    for marker in ("async function readAction", "exports.main", "OPTIONS", "Authorization", "bodyAreas", "movementHistory"):
        assert marker in source, f"missing web read contract marker: {marker}"
    for forbidden in ("getWXContext", "FITNESS_LEDGER_ALLOWED_OPENIDS", ".add(", ".update(", ".set(", ".remove("):
        assert forbidden not in source, f"web function must not use Mini Program/write boundary: {forbidden}"
    assert '"wx-server-sdk":"3.0.1"' in (FUNCTION / "package.json").read_text(encoding="utf-8")
    print("ledger web read contract: PASS")


if __name__ == "__main__":
    main()
