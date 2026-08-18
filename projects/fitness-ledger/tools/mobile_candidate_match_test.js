const assert = require("node:assert/strict");
const { findMatches } = require("../mini_program/miniprogram/utils/freeformCandidates.js");

const index = [
  {
    movement_id: "DUMBBELL_FLY",
    display_name: "哑铃飞鸟",
    english_name: "Dumbbell Fly",
    body_part: "chest",
    body_part_label: "胸",
    terms: ["哑铃飞鸟", "dumbbell fly"]
  },
  {
    movement_id: "BENT_OVER_DUMBBELL_FLY",
    display_name: "俯身哑铃飞鸟",
    english_name: "Bent-Over Dumbbell Fly",
    body_part: "back",
    body_part_label: "背",
    terms: ["俯身哑铃飞鸟", "bent-over dumbbell fly"]
  }
];

const qualified = findMatches("今天做俯身哑铃飞鸟", index);
assert.equal(qualified[0].movement_id, "BENT_OVER_DUMBBELL_FLY");
assert.equal(qualified.some(item => item.movement_id === "DUMBBELL_FLY"), false);

const unqualified = findMatches("今天做哑铃飞鸟", index);
assert.equal(unqualified[0].movement_id, "DUMBBELL_FLY");

console.log("FITNESS_LEDGER_MOBILE_CANDIDATE_MATCH_OK");
