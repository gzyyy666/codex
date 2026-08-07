export const BODY_PART_PRESENTATION = Object.freeze({
  chest: { poseId: 'front_double_biceps', cameraPreset: 'upper_front', headline: 'CHEST DEVELOPMENT' },
  back: { poseId: 'back_lat_spread', cameraPreset: 'upper_back', headline: 'BACK DEVELOPMENT' },
  back_width: { poseId: 'back_lat_spread', cameraPreset: 'upper_back', headline: 'BACK WIDTH' },
  back_thickness: { poseId: 'back_double_biceps', cameraPreset: 'upper_back', headline: 'BACK DEVELOPMENT' },
  shoulders: { poseId: 'side_chest', cameraPreset: 'upper_side', headline: 'SHOULDER DEVELOPMENT' },
  shoulder: { poseId: 'side_chest', cameraPreset: 'upper_side', headline: 'SHOULDER DEVELOPMENT' },
  arms: { poseId: 'front_double_biceps', cameraPreset: 'upper_front', headline: 'ARM DEVELOPMENT' },
  legs: { poseId: 'standing', cameraPreset: 'lower_body', headline: 'LOWER BODY' },
  full_body: { poseId: 'standing', cameraPreset: 'idle', headline: 'BODY ARCHIVE' }
});

const cleanLines = values => values.filter(value => value !== undefined && value !== null && String(value).trim() !== '');

export function presentationForMovement(summary = {}) {
  const key = summary.focusKey || summary.bodyPart || 'full_body';
  const mapping = BODY_PART_PRESENTATION[key] || BODY_PART_PRESENTATION.full_body;
  return {
    id: `movement:${summary.movementId || key}`,
    kind: 'route_default',
    poseId: mapping.poseId,
    cameraPreset: mapping.cameraPreset,
    overlay: { title: summary.headline || mapping.headline, lines: cleanLines([summary.movementName, summary.progressText, summary.bestText]) },
    restore: 'none'
  };
}

export function presentationForTrainingSave(summary = {}) {
  const pr = Array.isArray(summary.personalRecords) && summary.personalRecords.length > 0;
  const firstPr = summary.personalRecords?.[0] || {};
  return {
    id: `training-save:${summary.recordId || summary.date || Date.now()}`,
    kind: pr ? 'new_pr' : 'save_success',
    poseId: pr ? 'crab_hands_apart' : 'crab_hands_clasped',
    cameraPreset: 'celebration',
    durationMs: pr ? 4800 : 3200,
    restore: 'previous',
    dedupeKey: summary.recordId ? `training-save:${summary.recordId}` : undefined,
    effect: pr ? 'soft_particles' : 'gold_sweep',
    overlay: pr ? {
      title: 'NEW PERSONAL RECORD',
      lines: cleanLines([firstPr.movementName, firstPr.deltaText])
    } : {
      title: 'TRAINING COMPLETE',
      lines: cleanLines([summary.splitLabel, summary.movementCountText, summary.setCountText])
    }
  };
}

export function presentationForSemanticEvent(detail = {}) {
  const summary = detail.summary || {};
  const id = detail.id || `${detail.type || 'event'}:${detail.key || Date.now()}`;
  if (detail.request) return { ...detail.request, id: detail.request.id || id };
  if (detail.type === 'training-save') return presentationForTrainingSave(summary);
  if (detail.type === 'movement-focus' || detail.type === 'analysis-result') return { ...presentationForMovement(summary), id };
  if (detail.type === 'home-entry') return { id, kind: 'home_entry', poseId: 'standing', cameraPreset: 'idle', durationMs: 3200, restore: 'page_default', overlay: { title: summary.greeting || 'FITNESS LEDGER', lines: cleanLines([summary.weightText, summary.monthTrendText, summary.recentTrainingText]) } };
  if (detail.type === 'page-loading' || detail.type === 'analysis-loading') return { id, kind: 'loading', poseId: 'standing', cameraPreset: 'loading', restore: 'previous', overlay: { title: detail.type === 'analysis-loading' ? 'PREPARING ANALYSIS' : 'PREPARING ARCHIVE', lines: cleanLines([summary.stage]) } };
  if (detail.type === 'syncing') return { id, kind: 'loading', poseId: 'back_lat_spread', cameraPreset: 'loading', restore: 'previous', overlay: { title: 'SYNCING READ-ONLY COPY', lines: cleanLines([summary.stage]) } };
  if (detail.type === 'sync-result') return { id, kind: summary.ok ? 'save_success' : 'needs_review', poseId: summary.ok ? 'back_lat_spread' : 'standing', cameraPreset: 'idle', durationMs: 3400, restore: 'previous', overlay: { title: summary.ok ? 'SYNC VERIFIED' : 'SYNC NEEDS REVIEW', lines: cleanLines([summary.message]) } };
  if (detail.type === 'needs-review') return { id, kind: 'needs_review', poseId: 'standing', cameraPreset: 'idle', restore: 'page_default', overlay: { title: 'NEEDS REVIEW', lines: cleanLines([summary.message, summary.countText]) } };
  if (detail.type === 'diet-status') return { id, kind: 'home_entry', poseId: 'standing', cameraPreset: 'idle', durationMs: 3000, restore: 'previous', overlay: { title: summary.label, lines: cleanLines([summary.detail]) } };
  if (detail.type === 'weight-milestone') return { id, kind: 'milestone', poseId: 'front_double_biceps', cameraPreset: 'celebration', durationMs: 4500, restore: 'previous', dedupeKey: summary.dedupeKey, effect: 'gold_sweep', overlay: { title: 'WEIGHT MILESTONE', lines: cleanLines([summary.message]) } };
  return null;
}
