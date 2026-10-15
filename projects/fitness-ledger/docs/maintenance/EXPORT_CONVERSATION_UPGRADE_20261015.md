# Export conversation upgrade — development / review

## Coordination

- Worktree: `D:/FitnessLedger/worktrees/export-conversation-upgrade`
- Branch: `codex/export-conversation-upgrade`
- Base: local main `064548c4c1c31681f695e8ede02f1fba13d3d66c`.
- This task is one of three changes awaiting combined integration: training
  display/PWA themes, export conversation, and Web loading/rendering.
- No dependency on or merge of the training-display candidate. Shared edits
  to `web_desktop/frontend/app.js` and `web_desktop/backend/server.py` must be
  reviewed together during integration. Do not copy an old tree over formal.
- Source candidate only: no formal deployment, Cloud changes, merge, Push,
  Tags, protected-record changes, or final release acceptance.

## User-visible changes

- “提取过去一周的全部数据” produces four datasets: body, diet, training,
  movement_progress. All current structured fields are included, with a shared
  seven-day scope. Empty movement history is still an explicit dataset.
- “全部” refers to the current v1.1 structured fields, not Raw or custom
  modules. Additional Notes require an explicit request such as “包含备注”.
  Existing movement-progress exclusion rules remain in effect; they do not
  remove those facts from training records.
- Supported time wording includes 过去/近/这 N 天, weeks including 星期/礼拜,
  上周/本周/上上周, 今天/昨天, and 从上周到今天. Calendar weeks start Monday;
  the current week ends today. Existing explicit dates and month forms remain.
- 近期/这几天 use seven days with a visible notice. Dataset-specific defaults
  are also disclosed. Unrecognized explicit periods ask for clarification;
  they must not silently become all-history exports.
- “不要饮食/体重/备注” preserves exclusions; “全部数据但只要体重” becomes one
  body dataset with date and weight, using the same requested time window.
- Latest-N training sessions and recent-N-day training can be linked to the
  three preceding diet days. Each diet row retains its target training date.
- Unrecognized before/after relations ask for clarification rather than
  exporting unrelated contemporaneous diet. The local parser does not yet
  compile arbitrary after/before-and-after windows; the LLM JSON contract
  supports the existing protocol's relative modes.
- The page explains scope, shows defaults/warnings, and offers editable
  examples after clarification. Download links follow actual returned formats.

## LLM initialization

The actual initialization endpoint now returns `prompt_revision:
export-conversation-v2`. Its prompt separates initialization, request building,
clarification, and analysis after the user supplies a real downloaded bundle.
It contains validator-grounded fields, per-dataset modes, Notes permissions,
filter shapes, identifiers, structural limits, and a complete valid example.
The old incomplete frontend English substitute was removed. The setup prompt
is currently Chinese, with an instruction to converse in the user's language.
English UI text explains this. No model was connected to the local parser.

An independent isolated model received only the prompt and anonymous metadata.
Old-prompt output for past-week all-data omitted required filters/fields and
failed validation; the relationship request asked for missing contract details.
The revised prompt was tested again in a fresh isolated agent:

| Case | Result |
| --- | --- |
| Past week, all data | Valid four-dataset JSON; nonempty bundle; dates checked |
| Latest three sessions and three preceding diet days | Valid JSON; exact target/date pairs checked |
| Vague recent poor state | Asks for scope; no invented JSON |
| Fourteen-day sleep custom field | Explains unsupported item and asks about alternatives |
| Fourteen-day Synthetic Row movement | Valid JSON; correctly empty because fixture history is older |

Three JSON replies were replayed through Validator → Preview → Confirm →
artifact retrieval. JSON and Markdown were retrievable; Preview/Bundle counts
matched. This is a bounded independent-agent experiment, not a benchmark of
external providers or a guarantee for arbitrary speech.

## Validation and evidence

Passed: `restricted_export_integration_test.py` (5 tests),
`analysis_llm_prompt_test.py` (3 checks),
`export_conversation_semantic_test.py`, `export_conversation_browser_test.py`,
`analysis_export_protocol_web_test.py`,
`analysis_export_request_protocol_test.py`, `analysis_export_materializer_test.py`,
`formal_readonly_export_binding_test.py`, `formal_local_semantic_hint_web_test.py`,
and JavaScript syntax checking.

The headless Edge test opens the actual initialization modal, enters the
past-week all-data request, previews, confirms, retrieves the actual offered
artifact, checks its four domains, and exercises clarification examples.
Anonymous ledger hashes remain unchanged. No formal runtime result is claimed.

Model responses, prompts, and anonymous bundles are retained outside Git at
`D:/FitnessLedger/task_outputs/export-conversation-upgrade/`. Replay with:

```powershell
python tools/export_conversation_semantic_test.py --responses D:/FitnessLedger/task_outputs/export-conversation-upgrade/final_responses.json
```
