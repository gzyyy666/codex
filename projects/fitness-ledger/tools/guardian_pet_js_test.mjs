import assert from 'node:assert/strict';
import { buildBodyRegionSummaries, buildDietStatus, buildHomeEntrySummary, buildMovementPresentationSummary, buildTrainingSaveSummary, buildWeightMilestone } from '../web_desktop/frontend/motion-lab/guardian/guardian-business-adapters.js';
import { presentationForSemanticEvent, presentationForTrainingSave } from '../web_desktop/frontend/motion-lab/guardian/guardian-intent-map.js';
import { createGuardianPresentationManager } from '../web_desktop/frontend/motion-lab/guardian/guardian-presentation-manager.js';

const home = buildHomeEntrySummary({
  today: { body: { 'Weight (kg)': 67.5 } },
  body: [{ Date: '2026-08-01', 'Weight (kg)': 68 }, { Date: '2026-08-07', 'Weight (kg)': 67.5 }],
  training: [{ Date: '2026-08-06', Split: 'Back' }],
  now: new Date('2026-08-07T09:00:00')
});
assert.equal(home.greeting, 'GOOD MORNING');
assert.equal(home.monthTrendText, 'This month · -0.5 kg');
assert.match(home.recentTrainingText, /Back/);

const regions = buildBodyRegionSummaries([
  { movement_id: 'bench', display_name: 'Bench', muscle_group: 'Chest', history_count: 5 },
  { movement_id: 'fly', display_name: 'Fly', muscle_group: 'Chest', history_count: 2 },
  { movement_id: 'row', display_name: 'Row', muscle_group: 'Back', history_count: 8 }
]);
assert.equal(regions.find(item => item.key === 'chest').count, 2);
assert.equal(regions.find(item => item.key === 'chest').representativeMovementId, 'bench');

const movement = buildMovementPresentationSummary({
  movement: { movement_id: 'bench', display_name: 'Bench', muscle_group: 'Chest' },
  progress_history: [
    { metrics: { max_weight: 105, total_reps: 20, has_structured_sets: true } },
    { metrics: { max_weight: 100, total_reps: 24, has_structured_sets: true } }
  ]
});
assert.equal(movement.bodyPart, 'chest');
assert.equal(movement.progressText, 'Latest · 105 kg');
assert.equal(movement.bestText, 'Best · 105 kg');

const save = buildTrainingSaveSummary({ record_id: 'session-1', movement_count: 2, working_sets: 7, personal_records: [{ newPr: true, movementName: 'Bench' }] });
assert.equal(save.recordId, 'session-1');
assert.equal(presentationForTrainingSave(save).kind, 'new_pr');
assert.equal(presentationForSemanticEvent({ type: 'movement-focus', summary: movement, id: 'movement:bench' }).poseId, 'front_double_biceps');
assert.equal(buildDietStatus({ calories: 2000 }, {}), null, 'missing targets must stay silent');
assert.equal(buildDietStatus({ calories: 2000 }, { calories: 2000 }).label, 'CALORIE TARGET MET');
assert.equal(buildWeightMilestone({ previous: 70, current: 69, target: 69 }).dedupeKey, 'weight-milestone:weight-goal:69');
assert.equal(buildWeightMilestone({ previous: 68, current: 67, target: 69 }), null);

let visual = { poseId: 'standing', cameraPreset: 'idle' };
const overlays = [];
const manager = createGuardianPresentationManager({
  snapshot: () => ({ ...visual }),
  restore: async snapshot => { visual = { ...snapshot }; },
  setPose: async poseId => { visual.poseId = poseId; },
  setCameraPreset: async cameraPreset => { visual.cameraPreset = cameraPreset; },
  showOverlay: overlay => overlays.push(overlay?.title || ''),
  hideOverlay: () => {},
  playEffect: () => {},
  stopEffect: () => {}
});
assert.equal(await manager.apply({ id: 'route', kind: 'route_default', poseId: 'side_chest', restore: 'none' }), true);
assert.equal(await manager.apply({ id: 'pr', kind: 'new_pr', poseId: 'crab_hands_apart', restore: 'previous', dedupeKey: 'record-1' }), true);
assert.equal(await manager.apply({ id: 'loading', kind: 'loading', poseId: 'standing' }), false, 'lower priority must not interrupt a PR');
assert.equal(await manager.finish('pr'), true);
assert.equal(visual.poseId, 'standing', 'an interrupted chain restores the original stable snapshot');
assert.equal(await manager.apply({ id: 'duplicate', kind: 'new_pr', dedupeKey: 'record-1' }), false);
assert.equal(overlays.length >= 2, true);
manager.dispose();

console.log('guardian_pet_js_test: PASS');
