"""Regression checks for conservative mobile action-reference candidates."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "mini_program" / "miniprogram" / "utils" / "freeformCandidates.js"


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    assert 'ledger.call("movementCatalog")' in source
    assert 'ledger.call("bodyArea"' not in source[source.index("function loadIndex()"):]
    assert "史密斯" in source and "再次" not in source

    script = f"""
const vm = require('vm');
const source = {json.dumps(source, ensure_ascii=False)};
const sandbox = {{
  module: {{ exports: {{}} }},
  require: path => path.includes('bodyParts') ? ({{ BODY_PARTS: [] }}) : ({{ call: () => Promise.resolve({{ ok: true, data: [] }}) }}),
  Promise, String, Array, Set, console
}};
vm.runInNewContext(source, sandbox, {{ filename: 'freeformCandidates.js' }});
const helper = sandbox.module.exports;
const index = helper.buildCatalogIndex ? helper.buildCatalogIndex([]) : null;
const catalog = [
  {{ movement_id: 'BARBELL_BENCH', display_name: '杠铃卧推', english_name: 'Barbell Bench Press', aliases: ['平板杠铃卧推'], body_parts: ['chest'] }},
  {{ movement_id: 'BENCH', display_name: '卧推', english_name: '', aliases: ['平板推举'], body_parts: ['chest'] }}
];
// buildCatalogIndex is intentionally private; provide the normalized entries
// through the public finder exactly as the catalog loader would.
const entries = catalog.map(item => ({{ ...item, parts: [], body_part: '', body_part_label: '', terms: [item.display_name.toLowerCase(), ...item.aliases.map(value => value.toLowerCase())] }}));
const named = helper.findMatches('今天练杠铃卧推 4 组', entries).map(item => item.movement_id);
const alias = helper.findMatches('平板杠铃卧推 4 组', entries).map(item => item.movement_id);
const unmatched = helper.findMatches('今天练史密斯卧推 4 组', entries).map(item => item.movement_id);
if (JSON.stringify(named) !== JSON.stringify(['BARBELL_BENCH'])) throw new Error('qualified canonical name must not fall through to a shorter action');
if (JSON.stringify(alias) !== JSON.stringify(['BARBELL_BENCH'])) throw new Error('exact approved alias must match');
if (unmatched.length) throw new Error('unapproved qualifier must not match a shorter dictionary action');
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert not completed.stdout
    print("FITNESS_LEDGER_FREEFORM_CANDIDATES_EXACT_MATCH_OK")


if __name__ == "__main__":
    main()
