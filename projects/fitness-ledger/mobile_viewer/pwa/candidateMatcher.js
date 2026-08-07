const CANDIDATE_ALIAS_OVERRIDES = Object.freeze({
  SHOULDER_002: ["龙门架后束飞鸟", "龙门架后束", "绳索后束飞鸟", "绳索反飞", "后束绳索飞鸟"],
  SHOULDER_009: ["俯身哑铃飞鸟", "俯身哑铃反飞", "哑铃后束飞鸟"]
});

function compactTerm(value) {
  return normalizeCandidateText(value).replace(/\s/g, "");
}

export function normalizeCandidateText(value) {
  return String(value || "")
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/[‐‑‒–—―−]/g, "-")
    .replace(/[\s\u200b]+/g, " ")
    .trim();
}

export function usableCandidateTerm(value) {
  const term = normalizeCandidateText(value);
  if (!term) return "";
  const compactLength = term.replace(/\s/g, "").length;
  if (/[\u3400-\u9fff]/.test(term)) return compactLength >= 2 ? term : "";
  return compactLength >= 3 ? term : "";
}

function candidateTerms(item) {
  const movementId = String(item?.movement_id || item?.id || "").toUpperCase();
  const displayName = usableCandidateTerm(item?.display_name);
  const englishName = usableCandidateTerm(item?.english_name);
  const terms = [
    { value: displayName, priority: 3 },
    { value: englishName, priority: 2 },
    ...(item?.aliases || []).map(value => ({ value: usableCandidateTerm(value), priority: 1 })),
    ...(CANDIDATE_ALIAS_OVERRIDES[movementId] || []).map(value => ({ value: usableCandidateTerm(value), priority: 2 }))
  ];
  const unique = new Map();
  for (const term of terms) {
    if (!term.value) continue;
    const current = unique.get(term.value);
    if (!current || term.priority > current.priority) unique.set(term.value, term);
  }
  return [...unique.values()].map(term => ({
    ...term,
    compactLength: compactTerm(term.value).length,
    isDisplayName: term.value === displayName
  }));
}

function findTermHits(source, item) {
  const hits = [];
  for (const term of candidateTerms(item)) {
    let position = source.indexOf(term.value);
    while (position >= 0) {
      hits.push({
        item,
        term: term.value,
        position,
        end: position + term.value.length,
        specificity: term.compactLength * 100 + term.priority * 10 + (term.isDisplayName ? 5 : 0)
      });
      position = source.indexOf(term.value, position + 1);
    }
  }
  return hits;
}

export function findLastCandidate(note, catalog) {
  const source = normalizeCandidateText(note);
  if (!source) return null;
  const hits = (catalog || []).flatMap(item => findTermHits(source, item));
  if (!hits.length) return null;

  const latest = hits.reduce((current, hit) => hit.position > current.position ? hit : current);
  const overlapping = hits.filter(hit => hit.position < latest.end && hit.end > latest.position);
  overlapping.sort((a, b) => b.specificity - a.specificity || b.position - a.position || b.term.length - a.term.length);
  const winner = overlapping[0];
  return {
    ...winner.item,
    matched_term: winner.term,
    matched_position: winner.position,
    matched_specificity: winner.specificity
  };
}

export { CANDIDATE_ALIAS_OVERRIDES };
