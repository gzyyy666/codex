const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web_desktop/frontend/app.js'), 'utf8');
const start = source.indexOf('function trainingMovementRefs(record)');
const end = source.indexOf('function renderPreviousPreview', start);
const context = vm.createContext({
  value: (record, ...keys) => keys.map(key => record[key]).find(Boolean),
  trainingMovementTokens: record => (record['Standardized Summary'] || '').split(';').filter(Boolean),
  uiLanguage: () => 'en', esc: value => String(value), short: value => value,
});
vm.runInContext(source.slice(start, end), context);
const tracked = {order: 2, movement_id: 'CHEST_004', history_id: 'saved', display_name: 'Tracked', sets_lines: ['saved sets'], is_linkable: true};
const record = {'Raw Record': '1. First\n40-15-1\n2. Tracked\n30-12-2\n3. Third\n15-12-2\n4. Fourth\nthree sets\n5. Fifth\n15-3', movement_refs: [tracked]};
const rows = context.trainingMovementRefs(record);
assert.equal(rows.length, 5);
assert.equal(rows[1], tracked);
assert.equal(rows.filter(row => row.raw_only && row.exclude_from_progress).length, 4);
assert.equal(rows[0].sets_lines[0], '40-15-1');
assert.equal(rows[3].sets_lines[0], 'three sets');
assert.match(context.trainingMovementRow(rows[0], '2026-10-04'), /Count toward progress: No/);
assert.equal(context.trainingMovementRefs({...record, movement_refs: rows}).length, 5);
assert.equal(context.trainingMovementRefs({movement_refs: [tracked]})[0], tracked);
assert.equal(context.trainingMovementRefs({'Standardized Summary': 'First;Second'}).length, 2);
console.log('PASS: mixed raw/structured sessions retain all five movements without changing tracked rows');
