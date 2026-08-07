const numberOrNull = value => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

const dateOf = record => String(record?.Date || record?.date || '').slice(0, 10);
const compactNumber = value => Number(value).toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');

export function bodyPartKey(value = '') {
  const key = String(value).toLowerCase();
  if (/chest|pec|胸/.test(key)) return 'chest';
  if (/back|lat|pull|背/.test(key)) return 'back';
  if (/shoulder|delt|肩/.test(key)) return 'shoulders';
  if (/arm|bicep|tricep|肱|手臂/.test(key)) return 'arms';
  if (/leg|glute|quad|hamstring|calf|腿|臀/.test(key)) return 'legs';
  return 'full_body';
}

export function buildHomeEntrySummary({ today = {}, body = [], training = [], now = new Date() } = {}) {
  const hour = now.getHours();
  const greeting = hour < 11 ? 'GOOD MORNING' : hour < 18 ? 'GOOD AFTERNOON' : 'GOOD EVENING';
  const todayWeight = numberOrNull(today?.body?.['Weight (kg)']);
  const datedWeights = body.map(record => ({ date: dateOf(record), weight: numberOrNull(record?.['Weight (kg)']) }))
    .filter(item => item.date && item.weight !== null)
    .sort((a, b) => a.date.localeCompare(b.date));
  const weight = todayWeight ?? datedWeights.at(-1)?.weight ?? null;
  const monthPrefix = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const month = datedWeights.filter(item => item.date.startsWith(monthPrefix));
  const monthDelta = month.length > 1 ? month.at(-1).weight - month[0].weight : null;
  const recentSession = [...training].sort((a, b) => dateOf(b).localeCompare(dateOf(a)))[0];
  return {
    greeting,
    weightText: weight === null ? '' : `Latest weight · ${compactNumber(weight)} kg`,
    monthTrendText: monthDelta === null ? '' : `This month · ${monthDelta > 0 ? '+' : ''}${compactNumber(monthDelta)} kg`,
    recentTrainingText: recentSession ? `Recent training · ${recentSession.Split || recentSession.split || dateOf(recentSession)}` : ''
  };
}

export function buildBodyRegionSummaries(movements = []) {
  const labels = { shoulders: 'Shoulders', chest: 'Chest', arms: 'Arms', back: 'Back', legs: 'Legs' };
  return Object.entries(labels).map(([key, label]) => {
    const matching = movements.filter(item => bodyPartKey(item.muscle_group) === key);
    const representative = matching.sort((a, b) => Number(b.history_count || 0) - Number(a.history_count || 0))[0];
    return {
      key,
      label,
      count: matching.length,
      sessionCount: matching.reduce((sum, item) => sum + Number(item.history_count || 0), 0),
      representativeMovementId: representative?.movement_id || '',
      representativeMovementName: representative?.display_name || representative?.english_name || ''
    };
  });
}

export function buildMovementPresentationSummary(payload = {}) {
  const movement = payload.movement || {};
  const history = Array.isArray(payload.progress_history) ? payload.progress_history : [];
  const latest = history[0];
  const performance = latest?.metrics;
  const useLoad = Number(performance?.max_weight || 0) > 0;
  const metric = record => useLoad ? Number(record?.metrics?.max_weight || 0) : Number(record?.metrics?.total_reps || 0);
  const best = history.reduce((maximum, record) => Math.max(maximum, metric(record)), 0);
  const unit = useLoad ? 'kg' : 'reps';
  return {
    movementId: movement.movement_id || '',
    movementName: movement.display_name || movement.english_name || '',
    bodyPart: bodyPartKey(movement.muscle_group),
    progressText: latest && performance?.has_structured_sets ? `Latest · ${compactNumber(metric(latest))} ${unit}` : '',
    bestText: best > 0 ? `Best · ${compactNumber(best)} ${unit}` : ''
  };
}

export function buildTrainingSaveSummary(result = {}) {
  return {
    recordId: result.record_id || '',
    date: result.date || '',
    splitLabel: result.split_label || '',
    movementCountText: Number(result.movement_count || result.saved_movements || 0) > 0 ? `${Number(result.movement_count || result.saved_movements)} movements` : '',
    setCountText: Number(result.working_sets || 0) > 0 ? `${Number(result.working_sets)} working sets` : '',
    personalRecords: Array.isArray(result.personal_records) ? result.personal_records.filter(item => item?.newPr === true) : []
  };
}

export function buildDietStatus(record = {}, targets = {}) {
  const calories = numberOrNull(record['Calories (kcal)'] ?? record.calories);
  const target = numberOrNull(targets.calories ?? targets['Calories (kcal)']);
  if (calories === null || target === null || target <= 0) return null;
  const delta = calories - target;
  return {
    label: Math.abs(delta) <= target * 0.05 ? 'CALORIE TARGET MET' : delta < 0 ? 'BELOW CALORIE TARGET' : 'ABOVE CALORIE TARGET',
    detail: `${compactNumber(calories)} / ${compactNumber(target)} kcal`
  };
}

export function buildWeightMilestone({ current, previous, target, targetId = 'weight-goal' } = {}) {
  const values = [current, previous, target].map(numberOrNull);
  if (values.some(value => value === null)) return null;
  const [currentWeight, previousWeight, targetWeight] = values;
  const crossed = previousWeight > targetWeight ? currentWeight <= targetWeight : previousWeight < targetWeight ? currentWeight >= targetWeight : false;
  if (!crossed) return null;
  return {
    message: `Target reached · ${compactNumber(currentWeight)} kg`,
    dedupeKey: `weight-milestone:${targetId}:${compactNumber(targetWeight)}`
  };
}

export function buildStructuredAnalysisSummary(requests = [], previews = []) {
  const list = (Array.isArray(requests) ? requests : [requests]).filter(Boolean);
  const types = [...new Set(list.flatMap(request => (request.datasets || []).map(dataset => dataset.type).filter(Boolean)))];
  const count = (Array.isArray(previews) ? previews : [previews]).reduce((sum, preview) => sum + Number(preview?.preview?.record_count || preview?.record_count || 0), 0);
  return {
    movementName: types.length ? types.join(' · ') : 'Structured archive',
    progressText: count > 0 ? `${count} records prepared` : '',
    bestText: list.length > 0 ? `${list.length} read-only package${list.length === 1 ? '' : 's'}` : ''
  };
}
