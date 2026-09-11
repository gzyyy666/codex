# Complex Set + Session Superset Compatibility Note

Status: candidate implementation / review only. This note does not authorize
formal data writeback, service restart, merge, push, deployment, or migration.

## Scope and product decision

This change adds only two facts:

1. A set may contain ordered load/repetition segments. `+` means sequential
   segments in one set; it is not arithmetic and it must not become two sets.
2. A Session may contain an explicit `superset` relation between independent
   Movement Instances. The relation is not a Movement, Set, Progress object,
   volume bucket, or execution timeline.

The existing `TrainingSession.movement_items` collection remains canonical.
`organization_relations` is the sole canonical home for Session organization
relations. Existing plain sets remain physically unchanged.

## Before / after data shape

```text
BEFORE                                      AFTER (additive)
TrainingSession                             TrainingSession
  movement_items[]                            movement_items[]
    movement_instance_id                        movement_instance_id
    movement_id                                 movement_id
    sets[]                                      sets[]
      weight                                    ordinary: weight/reps/sets
      reps                                       segmented: segments[]
      sets                                         [{weight, reps}, ...]
  (no Session relation)                       organization_relations[]
                                                {id, type: "superset",
                                                 members: [movement refs]}
```

Ordinary rows retain `weight`, `reps`, and `sets`. A segmented row does not
invent a representative scalar weight or repetition count; its `segments`
array is the fact. Repeated identical complex sets use the existing compact
`sets` count. Unequal complex sets use one segmented row per set.

## Accepted entry grammar

The deterministic compact form is:

```text
(7.5+5)-(6+8)-3
```

It means three set repetitions, each containing `7.5 × 6 + 5 × 8`.
Weights and repetitions must have the same segment count. A mismatch is a
Review warning and save is rejected without changing canonical data; the raw
entry remains available for correction.

For unequal complex sets, the LLM must use the explicit per-set form:

```text
sets: 7.5x6+5x8; 7.5x6+5x7; 7.5x5+5x8
```

Each semicolon-delimited expression is one complete set. The parser accepts
this only as a recognized set-list expression and never compresses it to `×3`.

Session-level grouping uses an explicit, ordinal-only directive so parsing
does not require NLP or name matching:

```text
superset: A = movement 1, movement 2
```

The ordinals resolve only to Movement Instances in the same parsed Session.
Missing, duplicated, cross-session, or ambiguous members produce a warning
and no relation write. Neighboring movements without this directive remain
unrelated.

## Session Theme resolution and the no-theme path

The Session Theme catalog is authoritative for archive grouping. A complete
label such as `胸肩` is first checked as a whole; if it is not itself a theme,
the resolver accepts only one unambiguous decomposition into existing theme
names or aliases, such as `胸` + `肩` (the separated form `胸、肩` is accepted
too). It never derives a theme from a movement's muscle group or from adjacent
movement rows. The resulting `session_theme_ids` list is shared by both theme
pages, while `session_theme_name` preserves the original human-readable label.

If there is no label, or the catalog is locked and no existing theme matches,
the Session is still saved with its complete raw and structured record and an
empty theme membership. The archive exposes it under `未命名训练次` / ALL
RECORDS instead of dropping it. In the normal editable catalog mode, a truly
new non-empty label is materialized as a new user Session Theme by the existing
legacy-compatibility normalizer; it can then be renamed, pinned, or disabled
through the Session Theme manager. A malformed or ambiguous multi-theme label
is not silently split: it remains a raw-preserved Review warning until the user
corrects it or adds/chooses a theme explicitly.

## User -> system flow

```text
Training Note / external LLM
  -> formal entry grammar
  -> deterministic parser
  -> Daily Entry Review (segments + [Superset A])
  -> explicit Confirm & Save
  -> TrainingSession.movement_items + organization_relations
  -> shared view-model accessors
     -> volume / recent history / Movement Progress
     -> Training Archive / Open Record
     -> PWA + Cloud read replicas
     -> Analysis Export JSON / Markdown
```

The LLM normalizes user-provided facts into the grammar; it may not invent
missing segment pairs, member identities, IDs, volume, or analytical meaning.

## Superset relation ownership

```text
TrainingSession
  ├─ Movement Instance 1: biceps curl ─┐
  ├─ Movement Instance 2: triceps pushdown ─┤
  └─ organization_relations[]             │
       └─ {type: superset, members: [1, 2]} ┘
```

The relation is displayed as `[超级组 A]` / `Superset A` while each movement
keeps its own order, identity, sets, progress eligibility, and volume. No
superset progress, superset volume, A1/A2 timeline, or adjacency inference is
introduced.

## Impact map and required adaptations

| Layer | Existing scalar/implicit assumption | Candidate adaptation |
|---|---|---|
| Grammar/parser | set row has one weight/reps; legacy parenthesized progression is different | parse equal compact and explicit unequal segmented forms; retain raw and warning state |
| LLM entry template | no `+` segment rule or relation syntax | document exact grammar, pair-count rule, no guessing, ordinal superset directive |
| Session Theme resolution | one saved theme label was treated as one archive key | resolve only explicit/unambiguous existing-theme memberships; keep original label and expose an unthemed bucket |
| Review | scalar set text; no Session relation context | render complete `+` expression and relation members; block invalid writes |
| Canonical save/migration | `movement_items` is canonical; no relation collection | additive `segments` and Session `organization_relations`; normalize in memory only |
| Open Record | scalar `sets_text` editor | parse/render one segmented set without regenerating other movements |
| Metrics/progress | scalar weight/reps assumptions | central accessor computes segment-aware reps/volume; scalar-only metrics abstain on complex rows |
| Archive/history/chart | reads `sets_lines` and scalar metrics | consume shared formatter/metrics and relation context; no new progress object |
| PWA/mobile | read-only scalar summaries/raw note | preserve raw note and show structured `+` lines when present; relation badge is optional context |
| Cloud/read replica | allowlisted/read-only copies can flatten fields | preserve `segments` and `organization_relations`; raw stripping remains recursive |
| Analysis Export | strict field catalog/materializer fields | additive optional fields and derived metrics; v1.1 request semantics remain frozen |
| Tests/evidence | ordinary-only fixtures | parser, zero-write, volume, history, export, cloud/PWA contracts and browser evidence |

## Compatibility and migration policy

- Old ordinary sets are read and written exactly as before.
- Missing `segments` means unknown/absent, not a fabricated single segment.
- Existing adjacent movements never become a superset.
- No bulk historical migration is needed. `migrate_state` only normalizes
  copies, and any confirmed write uses the existing checkpoint/atomic boundary.
- Unknown or malformed new structure is retained in raw text and rejected at
  the Review/save boundary rather than guessed.
- Custom/untracked movement members remain custom/untracked and do not become
  eligible for Movement Progress merely because they are in a relation.

## Export sample (anonymous)

```json
{
  "movement_id": "m001",
  "movement_name": "Incline Press",
  "sets": [{
    "segments": [{"weight": 7.5, "reps": 6}, {"weight": 5, "reps": 8}],
    "sets": 3
  }],
  "derived_metrics": {"set_count": 3, "segment_count": 2, "total_reps": 42, "volume": 255},
  "organization_relations": [{
    "id": "superset:session-001:A",
    "type": "superset",
    "members": ["movement-instance-001", "movement-instance-002"],
    "co_members": [{"movement_id": "m002", "movement_name": "Triceps Pushdown"}]
  }]
}
```

`volume` and the other metrics above are deterministic projections, not new
stored facts. An analysis assistant must treat the relation as context and
must not infer that it caused fatigue, performance change, or efficiency.

## Review checklist

- [ ] ordinary `60kg × 5 × 3` unchanged
- [ ] `(7.5+5)-(6+8)-3` round-trips as 3 sets / 2 segments and volume 255
- [ ] mismatch warns and performs zero canonical write
- [ ] unequal complex sets remain per-set and are not compressed
- [ ] one segment edit leaves all other records unchanged
- [ ] explicit superset creates one Session relation; adjacency alone does not
- [ ] old data, raw stripping, Cloud/PWA and Analysis Export remain compatible
- [ ] browser evidence covers Review, history, Session, and hover/tap context
- [ ] candidate status, diff, tests, and incomplete runtime evidence reported
