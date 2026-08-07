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

  const clearTimer = () => {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  };

  async function apply(request) {
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
    if (request.cameraPreset) await adapter.setCameraPreset?.(request.cameraPreset, request);
    adapter.showOverlay?.(request.overlay || null, request);
    adapter.playEffect?.(request.effect || 'none', request);
    if (Number.isFinite(request.durationMs)) timer = setTimeout(() => void finish(request.id), request.durationMs);
    return true;
  }

  async function finish(id, reason = 'timeout') {
    if (disposed || !active || active.id !== id) return false;
    const finished = active;
    clearTimer();
    adapter.stopEffect?.(finished.effect || 'none', finished);
    adapter.hideOverlay?.(finished, reason);
    active = null;
    const restore = finished.restore || 'previous';
    if (restore === 'previous' && restoreSnapshot) await adapter.restore?.(restoreSnapshot);
    else if (restore === 'page_default' && pageDefault) await adapter.restore?.(pageDefault);
    restoreSnapshot = null;
    return true;
  }

  function setPageDefault(snapshot) {
    pageDefault = snapshot ? { ...snapshot } : null;
  }

  function setPriorities(next = {}) {
    Object.assign(priorities, next);
  }

  async function clear(reason = 'clear') {
    if (active) return finish(active.id, reason);
    clearTimer();
    adapter.hideOverlay?.(null, reason);
    restoreSnapshot = null;
    return true;
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
