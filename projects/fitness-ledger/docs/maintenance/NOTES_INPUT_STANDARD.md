# Notes Input Standard

Fitness Ledger stores four independent note scopes. They are all optional and
the original raw entry remains the audit source.

## Canonical input

Top-level labels are unindented:

```text
notes:
今日整体状态正常。

diet notes:
训练前碳水较少。

training notes:
左肩稳定性一般，整体控制优先。

training: 肩
 俯身哑铃飞鸟
 10kg x 15 x 2
 notes: 前倾约30度，本次主要刺激中束。
```

`notes:` is Daily Notes, `diet notes:` is Diet Notes, and `training notes:`
is the note for the whole training session. An action-instance note is a
one-space-indented `notes:` line inside the nearest movement block. Structural
indentation is removed before saving; meaningful internal line breaks and
wording are preserved.

The parser uses explicit scope first. Existing historical unindented action
notes remain compatible only when the next line clearly starts another action.
An unlabelled or otherwise ambiguous sentence is not silently assigned to a
scope; the raw input remains available for Review.

Each Notes block ends at the next complete structural marker: another Notes
scope, a section such as `diet:`, `training:`, or `cardio:`, or a recognized
formal field such as `calories: 2200`, `protein: 140`, `weight: 80`, or
`steps: 9000`. Numeric fields must contain a valid numeric value before they
can terminate Notes; prose such as “calories are higher today” remains note
content. This same boundary rule is shared by top-level parsing and training
movement extraction.

Movement Notes belong to one dated movement-history instance. They are not
Movement Dictionary metadata and are never copied into other dates or same-name
instances. Training Notes are not copied into movements.

CRLF/LF, trailing line spaces, and leading/trailing blank lines do not create a
business update. Internal blank lines, punctuation, order, and user wording are
not rewritten. Clearing a note is an explicit empty value and is saved through
the existing Command Service transaction. Repeating equivalent content returns
`NO_CHANGES` without a checkpoint.
