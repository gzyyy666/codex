# Export validation recovery — development / review

Base: main `20652ad3b7c2a068bd0617ad4bf48ea888eb9bdc`.
Branch: `codex/export-validation-recovery`.

## Actual runtime diagnosis

The running formal Web app at `127.0.0.1:8766` reports build `20652ad` and
initialization prompt v4. Its export error, reset, scope and validation
functions match this source baseline. A headless Edge probe of the formal
entry reproduced the reported sequence without exporting data or navigating
away: malformed JSON → error → clear → valid JSON → validate.

Observed: the real API returned `valid`, the UI stayed at `validate`, the Next
button was disabled, and the scope containers no longer existed. The error
renderer replaced the parent result area's HTML and deleted those containers;
reset cleared surviving nodes but did not reconstruct them. Re-entering the
page rebuilt them, which explains the user's temporary workaround.

## Candidate fix

- Keep error content in a dedicated persistent slot beside scope containers.
  Errors hide scope content; reset, successful scope, and candidate selection
  clear errors and restore that content. Recovery no longer needs a route reload.
- Malformed input gets specific guidance when it resembles concatenated
  objects or translated/smart-quoted protocol text. Nothing is silently
  repaired, truncated, selected from multiple objects, or submitted differently.
- Mark the JSON editor and initialization/definition blocks `translate=no` and
  `notranslate`. This does not control external chat websites or extensions.
- Prompt v5 explicitly requires one object, ASCII string delimiters, unchanged
  machine keys/fields/enums/IDs, complete replacement on correction, and copying
  the original message. The purpose length limit comes from the contract, with
  a shorter suggested budget that does not replace the hard limit.

## User-provided request

The first English-keyed request is valid. Its purpose is 319 characters, below
the 500-character limit. A reconstruction with identical purpose, five dataset
IDs, types, dates, fields, filters and formats returned `valid` with zero errors
from the actual formal validation API. No personal records were exported.

The second pasted fragment has translated machine literals, smart quotes and
missing separators. Two adjacent objects are invalid JSON even if the first
is valid. The user subsequently confirmed that the malformed text was already
visible in the original chat, before it entered the application. For this
reported fragment, application-side paste transformation is therefore not the
origin. Treat it as a malformed original-chat output when assessing prompt
robustness. Raw model output versus translation/rendering within that chat
remains unverified; do not claim either specific mechanism as proven.

## Verification

- `export_validation_recovery_browser_test.py --formal-probe --expect-bug`:
  reproduced the bug in the actual running formal app.
- The default anonymous browser regression passed parse-error/clear/retry,
  schema-error/replace/retry, damaged-copy guidance, mode switching, simulated
  network-error/retry without edits, and transition to the next Preview stage.
- `export_conversation_browser_test.py`: full anonymous export flow passed.
- `analysis_llm_prompt_test.py`: six checks passed, including the actual complex
  request, concatenated-object rejection and translated-key rejection.
- JavaScript syntax checking, Python syntax checking and diff checks passed.
- An independent fresh agent received only the v5 prompt and two Chinese
  requests (complex planning and a damaged-copy correction scenario). Both
  emitted single parseable objects, passed the Validator and anonymous Preview,
  retained intended dates/domains, and respected requested Notes scopes.
  Purpose lengths were 157 and 99. This is bounded model evidence, not a
  guarantee against future model or external translation errors.
- Formal tracker/dictionary hashes remained unchanged during diagnosis.

Local request, formal validation and isolated-model evidence:
`D:/FitnessLedger/task_outputs/export-validation-recovery-20261016/`.

## Publication boundary

Candidate only. No formal files, service restart, Cloud, protected records,
merge, Push or release acceptance changed. Formal `app.js` also contains
unrelated differences in entry/movement editing; preserve or reconcile those
before any later whole-file publication. The export fixes do not resolve that
independent drift.
