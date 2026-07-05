const BODY_PARTS = [
  { id: "shoulders", cn: "肩", en: "SHOULDERS", tone: "amber" },
  { id: "chest", cn: "胸", en: "CHEST", tone: "coral" },
  { id: "back", cn: "背", en: "BACK", tone: "teal" },
  { id: "legs", cn: "腿", en: "LEGS", tone: "violet" },
  { id: "arms", cn: "手臂", en: "ARMS", tone: "cyan" }
];

function byId(id) {
  return BODY_PARTS.find(item => item.id === id) || null;
}

module.exports = { BODY_PARTS, byId };
