const ledger = require("../services/ledger");
const { BODY_PARTS } = require("./bodyParts");

let cachedIndex = null;
let indexPromise = null;

function normalize(value) {
  return String(value || "").toLocaleLowerCase().replace(/\s+/g, " ").trim();
}

function usableTerm(value) {
  const term = normalize(value);
  if (!term) return "";
  const compactLength = term.replace(/\s/g, "").length;
  // One-character Chinese matches (例如“胸”“背”) are too ambiguous to
  // become action candidates. English needs a slightly longer phrase too.
  if (/[\u3400-\u9fff]/.test(term)) return compactLength >= 2 ? term : "";
  return compactLength >= 3 ? term : "";
}

function buildIndex(responses) {
  const byId = {};
  (responses || []).forEach((response, responseIndex) => {
    const part = BODY_PARTS[responseIndex];
    const movements = response && response.ok && response.data && Array.isArray(response.data.movements)
      ? response.data.movements
      : [];
    movements.forEach(item => {
      const movementId = String(item.movement_id || "").trim();
      const displayName = String(item.display_name || "").trim();
      if (!movementId || !displayName) return;
      const current = byId[movementId] || {
        movement_id: movementId,
        display_name: displayName,
        english_name: String(item.english_name || "").trim(),
        parts: [],
        terms: []
      };
      if (part && !current.parts.some(value => value.id === part.id)) current.parts.push(part);
      if (!current.english_name && item.english_name) current.english_name = String(item.english_name).trim();
      byId[movementId] = current;
    });
  });
  return finalizeIndex(Object.values(byId));
}

function buildCatalogIndex(records) {
  const items = (records || []).map(item => ({
    movement_id: String(item.movement_id || "").trim(),
    display_name: String(item.display_name || "").trim(),
    english_name: String(item.english_name || "").trim(),
    aliases: Array.isArray(item.aliases) ? item.aliases : [],
    parts: (Array.isArray(item.body_parts) ? item.body_parts : []).map(id => BODY_PARTS.find(part => part.id === id)).filter(Boolean)
  })).filter(item => item.movement_id && item.display_name);
  return finalizeIndex(items);
}

function finalizeIndex(items) {
  return (items || []).map(item => {
    const terms = [item.display_name, item.english_name].map(usableTerm).filter(Boolean);
    (item.aliases || []).map(usableTerm).filter(Boolean).forEach(term => terms.push(term));
    return {
      ...item,
      terms: Array.from(new Set(terms)),
      body_part: item.parts[0] ? item.parts[0].id : "",
      body_part_label: item.parts.map(part => part.cn).join(" / ")
    };
  }).filter(item => item.terms.length);
}

function loadIndex() {
  if (cachedIndex) return Promise.resolve(cachedIndex);
  if (indexPromise) return indexPromise;
  indexPromise = ledger.call("movementCatalog")
    .then(catalog => {
      if (catalog.ok && Array.isArray(catalog.data)) {
        cachedIndex = buildCatalogIndex(catalog.data);
        return cachedIndex;
      }
      return Promise.all(BODY_PARTS.map(part => ledger.call("bodyArea", { part: part.id }))).then(responses => {
        cachedIndex = buildIndex(responses);
        return cachedIndex;
      });
    })
    .catch(() => [])
    .finally(() => { indexPromise = null; });
  return indexPromise;
}

function findMatches(text, index) {
  const source = normalize(text);
  if (!source || !Array.isArray(index)) return [];
  return index.map(item => {
    const matches = item.terms
      .map(term => ({ term, position: source.indexOf(term) }))
      .filter(match => match.position >= 0)
      .sort((a, b) => a.position - b.position || b.term.length - a.term.length);
    if (!matches.length) return null;
    return {
      movement_id: item.movement_id,
      display_name: item.display_name,
      english_name: item.english_name,
      body_part: item.body_part,
      body_part_label: item.body_part_label,
      matched_term: matches[0].term,
      matched_position: matches[0].position
    };
  }).filter(Boolean)
    .sort((a, b) => a.matched_position - b.matched_position || b.matched_term.length - a.matched_term.length)
    .slice(0, 4);
}

function detect(text) {
  return loadIndex().then(index => findMatches(text, index));
}

module.exports = { loadIndex, findMatches, detect };
