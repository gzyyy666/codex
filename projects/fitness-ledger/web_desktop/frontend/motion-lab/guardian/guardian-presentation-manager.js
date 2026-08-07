const DEFAULT_PRIORITIES = Object.freeze({
  route_default: 10,
  home_entry: 20,
  loading: 30,
  save_success: 50,
  milestone: 60,
  new_pr: 70,
  needs_review: 80,
  fatal_error: 90
});

export function createGuardianPresentationManager(adapter, options = {}) {
  if (!adapter) throw new Error('Guardian presentation adapter is required');
  const priorities = { ...DEFAULT_PRIORITIES, ...(options.priorities || {}) };
  let pageDefault = null;
  let active = null;
  let restoreSnapshot = null;
  let timer = null;
  let disposed = false;
  const dedupe = new Set();
  let operationQueue = Promise.resolve();

  const enqueue = task => {
    const result = operationQueue.then(task, task);
    operationQueue = result.catch(() => {});
    return result;
  };

  const clearTimer = () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  };

  async function applyNow(request) {
    if (disposed) return false;
    if (!request?.id) throw new Error('Presentation request requires id');
    const priority = request.priority ?? priorities[request.kind] ?? 10;
    if (request.dedupeKey && dedupe.has(request.dedupeKey)) return false;
    if (active && active.priority > priority) return false;

    clearTimer();
    if (!active) restoreSnapshot = adapter.snapshot?.() ?? null;
    else {
      adapter.stopEffect?.(active.effect || 'none', active);
      adapter.hideOverlay?.(active, 'interrupted');
    }
    active = { ...request, priority };
    if (request.dedupeKey) dedupe.add(request.dedupeKey);

    if (request.poseId) await adapter.setPose(request.poseId, { source: 'intent' });
    if (disposed || active?.id !== request.id) return false;
    if (request.cameraPreset) await adapter.setCameraPreset?.(request.cameraPreset, request);
    if (disposed || active?.id !== request.id) return false;
    adapter.showOverlay?.(request.overlay || null, request);
    adapter.playEffect?.(request.effect || 'none', request);
    if (Number.isFinite(request.durationMs)) timer = setTimeout(() => void finish(request.id), request.durationMs);
    return true;
  }

  function apply(request) {
    return enqueue(() => applyNow(request)).catch(() => {
      if (active?.id === request?.id) {
        clearTimer();
        adapter.stopEffect?.(active.effect || 'none', active);
        adapter.hideOverlay?.(active, 'error');
        active = null;
        restoreSnapshot = null;
      }
      return false;
    });
  }

  async function finishNow(id, reason = 'timeout') {
    if (disposed || !active || active.id !== id) return false;
    const finished = active;
    clearTimer();
    adapter.stopEffect?.(finished.effect || 'none', finished);
    adapter.hideOverlay?.(finished, reason);
    active = null;
    const restore = finished.restore || 'previous';
    const snapshot = restoreSnapshot;
    restoreSnapshot = null;
    if (restore === 'previous' && snapshot) await adapter.restore?.(snapshot);
    else if (restore === 'page_default' && pageDefault) await adapter.restore?.(pageDefault);
    return true;
  }

  function finish(id, reason = 'timeout') {
    return enqueue(() => finishNow(id, reason)).catch(() => false);
  }

  function setPageDefault(snapshot) {
    pageDefault = snapshot ? { ...snapshot } : null;
    const desired = pageDefault ? { ...pageDefault } : null;
    return enqueue(async () => {
      if (disposed) return false;
      clearTimer();
      if (active) {
        adapter.stopEffect?.(active.effect || 'none', active);
        adapter.hideOverlay?.(active, 'route-change');
        active = null;
      } else {
        adapter.hideOverlay?.(null, 'route-change');
      }
      restoreSnapshot = null;
      if (desired) await adapter.restore?.(desired);
      return true;
    }).catch(() => false);
  }

  function setPriorities(next = {}) {
    Object.assign(priorities, next);
  }

  function clear(reason = 'clear') {
    return enqueue(() => {
      if (active) return finishNow(active.id, reason);
      clearTimer();
      adapter.hideOverlay?.(null, reason);
      restoreSnapshot = null;
      return true;
    }).catch(() => false);
  }

  function getState() {
    return { active: active ? { ...active } : null, pageDefault: pageDefault ? { ...pageDefault } : null, dedupeCount: dedupe.size };
  }

  function dispose() {
    if (disposed) return;
    disposed = true;
    clearTimer();
    adapter.stopEffect?.(active?.effect || 'none', active);
    adapter.hideOverlay?.(active, 'dispose');
    active = null;
    pageDefault = null;
    restoreSnapshot = null;
    dedupe.clear();
  }

  return { apply, finish, clear, setPageDefault, setPriorities, getState, dispose };
}
