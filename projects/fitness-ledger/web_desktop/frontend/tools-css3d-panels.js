/*
 * CSS3D panel controller for the Tools surface.
 *
 * Reference: Three.js CSS3DRenderer applies hierarchical 3D transforms to
 * ordinary DOM elements. We keep the real HTML buttons as the authoritative
 * interaction layer, then drive their CSS 3D variables from the pointer.
 * https://threejs.org/docs/pages/CSS3DRenderer.html
 *
 * The small companion keeps the MIT mouse-follower spring/inertia behavior:
 * https://github.com/ArtBIT/mouse-follower
 */

import { presentationForSemanticEvent } from './motion-lab/guardian/guardian-intent-map.js?v=20260807-v90';

const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const finePointer = window.matchMedia?.('(pointer: coarse)').matches !== true;

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const petNavigation = [
  {
    label: 'ARCHIVE',
    routes: [
      { view: 'home', label: 'Home', meta: '00 / HOME' },
      { view: 'quick', label: 'Daily Entry', meta: '01 / ENTRY' },
      { view: 'body', label: 'Body', meta: '02 / BODY' },
      { view: 'diet', label: 'Diet', meta: '03 / DIET' },
      { view: 'training', label: 'Training', meta: '04 / TRAINING' },
      { view: 'movements', label: 'Movement Progress', meta: '05 / MOVEMENT' }
    ]
  },
  {
    label: 'UTILITY DESK',
    routes: [
      { view: 'tools', label: 'Tools', meta: '08 / TOOLS' },
      { view: 'export', label: 'Analysis Export', meta: '06 / EXPORT' },
      { view: 'cloud-sync', label: 'Cloud Sync', meta: '07 / SYNC' },
      { view: 'checks', label: 'Data Health', meta: '08 / HEALTH' },
      { view: 'dictionary', label: 'Movement Dictionary', meta: '07 / DICTIONARY' },
    ]
  }
];

const petPoseNavigation = {
  label: 'POSE SWITCH',
  routes: [
    { pose: 'standing', label: 'Front standing', meta: '01 / POSE' },
    { pose: 'front_double_biceps', label: 'Front double biceps', meta: '02 / POSE' },
    { pose: 'side_chest', label: 'Side chest', meta: '03 / POSE' },
    { pose: 'back_double_biceps', label: 'Rear double biceps', meta: '04 / POSE' },
    { pose: 'back_lat_spread', label: 'Rear lat spread', meta: '05 / POSE' },
    { pose: 'crab_hands_clasped', label: 'Most muscular', meta: '06 / POSE' },
    { pose: 'crab_hands_apart', label: 'Open-hand crab', meta: '07 / POSE' }
  ]
};
const petQuery = new URLSearchParams(window.location.search);
const reviewPetMode = petQuery.has('guardianPet') || petQuery.get('petReview') === 'corner' || petQuery.get('petFollow') !== '1';
const isGuardianRoute = () => (window.location.hash || '').replace(/^#/, '').split('?')[0] === 'guardian';
const archivePetCrossTabKey = 'fitness-ledger.guardian-pet.owner.v1';
const archivePetCrossTab = window.__fitnessLedgerArchivePetCrossTab && typeof window.__fitnessLedgerArchivePetCrossTab === 'object'
  ? window.__fitnessLedgerArchivePetCrossTab
  : (window.__fitnessLedgerArchivePetCrossTab = { id: `pet-tab-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`, owner: false, timer: null });
const readArchivePetCrossTabOwner = () => {
  try { return JSON.parse(localStorage.getItem(archivePetCrossTabKey) || 'null'); } catch { return null; }
};
const stopArchivePetCrossTabHeartbeat = () => {
  if (archivePetCrossTab.timer !== null) clearInterval(archivePetCrossTab.timer);
  archivePetCrossTab.timer = null;
  archivePetCrossTab.owner = false;
};
const releaseArchivePetCrossTab = () => {
  try {
    if (readArchivePetCrossTabOwner()?.id === archivePetCrossTab.id) localStorage.removeItem(archivePetCrossTabKey);
  } catch {}
  stopArchivePetCrossTabHeartbeat();
};
const claimArchivePetCrossTab = () => {
  const now = Date.now();
  try {
    const current = readArchivePetCrossTabOwner();
    if (current?.id && current.id !== archivePetCrossTab.id && now - Number(current.ts || 0) < 2400) return false;
    localStorage.setItem(archivePetCrossTabKey, JSON.stringify({ id: archivePetCrossTab.id, ts: now }));
    if (readArchivePetCrossTabOwner()?.id !== archivePetCrossTab.id) return false;
  } catch {
    return true;
  }
  archivePetCrossTab.owner = true;
  if (archivePetCrossTab.timer === null) {
    archivePetCrossTab.timer = setInterval(() => {
      if (!archivePetCrossTab.owner || isGuardianRoute()) return;
      try { localStorage.setItem(archivePetCrossTabKey, JSON.stringify({ id: archivePetCrossTab.id, ts: Date.now() })); } catch {}
    }, 700);
  }
  return true;
};
const onArchivePetCrossTabStorage = event => {
  if (event.key !== archivePetCrossTabKey) return;
  if (!event.newValue) {
    window.setTimeout(() => { if (!isGuardianRoute()) syncGlobalArchivePet(); }, 0);
    return;
  }
  try {
    const next = JSON.parse(event.newValue);
    if (next?.id && next.id !== archivePetCrossTab.id && Date.now() - Number(next.ts || 0) < 2400) {
      stopArchivePetCrossTabHeartbeat();
      disposeArchivePetInstances();
    }
  } catch {}
};
window.addEventListener('storage', onArchivePetCrossTabStorage);
window.addEventListener('pagehide', releaseArchivePetCrossTab);

function mountPetMenu(body, { onPose } = {}) {
  const menu = document.createElement('aside');
  menu.className = 'tools-pet-menu';
  menu.hidden = true;
  menu.dataset.open = 'false';
  menu.setAttribute('aria-label', 'Fitness Ledger guardian pet menu');
  menu.setAttribute('role', 'menu');
  const routeGroups = [...petNavigation, reviewPetMode ? { ...petPoseNavigation, routes: petPoseNavigation.routes.filter(route => ['side_chest', 'crab_hands_clasped'].includes(route.pose)) } : petPoseNavigation];
  menu.innerHTML = `<header><span class="eyebrow">PET ROUTER / LOCAL</span><strong>Find the next surface.</strong></header>${routeGroups.map((group) => `<section><span class="tools-pet-menu-label">${group.label}</span>${group.routes.map((route) => route.pose ? `<button type="button" role="menuitem" class="tools-pet-menu-item" data-pet-pose="${route.pose}"><span>${route.label}</span><small>${route.meta}</small></button>` : `<button type="button" role="menuitem" class="tools-pet-menu-item" data-pet-route-view="${route.view}"${route.panel?` data-pet-route-panel="${route.panel}"`:''}><span>${route.label}</span><small>${route.meta}</small></button>`).join('')}</section>`).join('')}`;
  document.body.appendChild(menu);

  const close = () => {
    menu.hidden = true;
    menu.dataset.open = 'false';
  };
  const open = (x, y) => {
    menu.hidden = false;
    menu.dataset.open = 'true';
    menu.style.left = '0px';
    menu.style.top = '0px';
    requestAnimationFrame(() => {
      const margin = 12;
      const left = clamp(x + 10, margin, window.innerWidth - menu.offsetWidth - margin);
      const top = clamp(y + 10, margin, window.innerHeight - menu.offsetHeight - margin);
      menu.style.left = `${left}px`;
      menu.style.top = `${top}px`;
      menu.querySelector('.tools-pet-menu-item')?.focus();
    });
  };
  const activateRoute = (route) => {
    close();
    if (route.view === 'export' || route.view === 'cloud-sync' || route.view === 'checks') {
      window.location.hash = `#${route.view}`;
      return;
    }
    const nav = document.querySelector(`.nav-item[data-view="${route.view}"]`);
    if (nav) nav.click();
    else window.location.hash = `#${route.view}`;
  };
  const onBodyContextMenu = (event) => {
    event.preventDefault();
    event.stopPropagation();
    open(event.clientX, event.clientY);
  };
  const onBodyKeyDown = (event) => {
    if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) {
      event.preventDefault();
      open(body.getBoundingClientRect().left, body.getBoundingClientRect().bottom);
    }
  };
  const onMenuClick = (event) => {
    const pose = event.target.closest('[data-pet-pose]')?.dataset.petPose;
    if (pose) {
      close();
      onPose?.(pose);
      return;
    }
    const item = event.target.closest('[data-pet-route-view]');
    if (!item) return;
    activateRoute({ view: item.dataset.petRouteView, panel: item.dataset.petRoutePanel });
  };
  const onMenuKeyDown = (event) => {
    const items = [...menu.querySelectorAll('.tools-pet-menu-item')];
    const current = items.indexOf(document.activeElement);
    if (!items.length) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      items[next]?.focus();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      close();
      body.focus();
    }
  };
  const onDocumentPointerDown = (event) => {
    if (!event.target.closest('.tools-pet-menu') && event.target !== body) close();
  };
  const onDocumentKeyDown = (event) => {
    if (event.key === 'Escape') close();
  };

  body.addEventListener('contextmenu', onBodyContextMenu);
  body.addEventListener('keydown', onBodyKeyDown);
  menu.addEventListener('click', onMenuClick);
  menu.addEventListener('keydown', onMenuKeyDown);
  document.addEventListener('pointerdown', onDocumentPointerDown, { passive: true });
  document.addEventListener('keydown', onDocumentKeyDown);

  const cleanup = () => {
    body.removeEventListener('contextmenu', onBodyContextMenu);
    body.removeEventListener('keydown', onBodyKeyDown);
    menu.removeEventListener('click', onMenuClick);
    menu.removeEventListener('keydown', onMenuKeyDown);
    document.removeEventListener('pointerdown', onDocumentPointerDown);
    document.removeEventListener('keydown', onDocumentKeyDown);
    menu.remove();
  };
  return cleanup;
}

// Legacy nav-pet renderer removed. The global pet has one canonical WebGL host below.

const guardianPetPositionKey = 'fitness-ledger.guardian-pet.position.v1';
const archivePetRegistry = window.__fitnessLedgerArchivePetRegistry instanceof Map
  ? window.__fitnessLedgerArchivePetRegistry
  : (window.__fitnessLedgerArchivePetRegistry = new Map());
const archivePetControllers = window.__fitnessLedgerArchivePetControllers instanceof Set
  ? window.__fitnessLedgerArchivePetControllers
  : (window.__fitnessLedgerArchivePetControllers = new Set());
const archivePetLease = window.__fitnessLedgerArchivePetLease && typeof window.__fitnessLedgerArchivePetLease === 'object'
  ? window.__fitnessLedgerArchivePetLease
  : (window.__fitnessLedgerArchivePetLease = { id: null, cleanup: null, controller: null });
let archivePetSequence = Number(window.__fitnessLedgerArchivePetSequence) || 0;
const nextArchivePetId = () => {
  archivePetSequence += 1;
  window.__fitnessLedgerArchivePetSequence = archivePetSequence;
  return `archive-pet-${Date.now().toString(36)}-${archivePetSequence.toString(36)}`;
};
const guardianPetRoutePoses = {
  home: { poseId: 'standing', cameraPreset: 'idle' },
  quick: { poseId: 'standing', cameraPreset: 'idle' },
  body: { poseId: 'side_chest', cameraPreset: 'upper_side' },
  diet: { poseId: 'standing', cameraPreset: 'idle' },
  training: { poseId: 'front_double_biceps', cameraPreset: 'upper_front' },
  movements: { poseId: 'back_double_biceps', cameraPreset: 'upper_back' },
  tools: { poseId: 'side_chest', cameraPreset: 'upper_side' },
  dictionary: { poseId: 'crab_hands_apart', cameraPreset: 'idle' },
  guardian: { poseId: 'standing', cameraPreset: 'idle' }
};

const readGuardianPetPosition = () => {
  try {
    const saved = JSON.parse(localStorage.getItem(guardianPetPositionKey) || 'null');
    if (Number.isFinite(saved?.x) && Number.isFinite(saved?.y)) return { x: clamp(saved.x, 0, 1), y: clamp(saved.y, 0, 1) };
  } catch {}
  return { x: 1, y: 1 };
};

function mountFloatingPetMenu(body, { onPose, onResetPosition } = {}) {
  const menu = document.createElement('aside');
  menu.className = 'tools-pet-menu';
  menu.hidden = true;
  menu.dataset.open = 'false';
  menu.setAttribute('aria-label', 'Guardian Pet pose menu');
  menu.setAttribute('role', 'menu');
  menu.innerHTML = `<header><span class="eyebrow">GUARDIAN PET / LOCAL</span><strong>Choose a pose.</strong></header><section><span class="tools-pet-menu-label">${petPoseNavigation.label}</span>${petPoseNavigation.routes.map(route => `<button type="button" role="menuitem" class="tools-pet-menu-item" data-pet-pose="${route.pose}"><span>${route.label}</span><small>${route.meta}</small></button>`).join('')}</section><section><span class="tools-pet-menu-label">POSITION</span><button type="button" role="menuitem" class="tools-pet-menu-item" data-pet-reset-position><span>Reset corner</span><small>DEFAULT</small></button></section>`;
  document.body.appendChild(menu);

  const close = () => {
    menu.hidden = true;
    menu.dataset.open = 'false';
  };
  const open = (x, y) => {
    menu.hidden = false;
    menu.dataset.open = 'true';
    menu.style.left = '0px';
    menu.style.top = '0px';
    requestAnimationFrame(() => {
      const margin = 12;
      const left = x >= window.innerWidth / 2 ? x - menu.offsetWidth - 10 : x + 10;
      const top = y >= window.innerHeight / 2 ? y - menu.offsetHeight - 10 : y + 10;
      menu.style.left = `${clamp(left, margin, window.innerWidth - menu.offsetWidth - margin)}px`;
      menu.style.top = `${clamp(top, margin, window.innerHeight - menu.offsetHeight - margin)}px`;
      menu.querySelector('.tools-pet-menu-item')?.focus();
    });
  };
  const onContextMenu = event => {
    event.preventDefault();
    event.stopPropagation();
    open(event.clientX, event.clientY);
  };
  const onKeyDown = event => {
    if (event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')) {
      event.preventDefault();
      const rect = body.getBoundingClientRect();
      open(rect.left, rect.top);
    }
  };
  const onMenuClick = event => {
    const pose = event.target.closest('[data-pet-pose]')?.dataset.petPose;
    if (pose) {
      close();
      onPose?.(pose);
      body.focus();
      return;
    }
    if (event.target.closest('[data-pet-reset-position]')) {
      close();
      onResetPosition?.();
      body.focus();
    }
  };
  const onMenuKeyDown = event => {
    const items = [...menu.querySelectorAll('.tools-pet-menu-item')];
    const current = items.indexOf(document.activeElement);
    if (event.key === 'Escape') {
      event.preventDefault();
      close();
      body.focus();
      return;
    }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      items[next]?.focus();
    }
  };
  const onDocumentPointerDown = event => {
    if (!event.target.closest('.tools-pet-menu') && !event.target.closest('.tools-pet-floating')) close();
  };
  const onDocumentKeyDown = event => { if (event.key === 'Escape') close(); };

  body.addEventListener('contextmenu', onContextMenu);
  body.addEventListener('keydown', onKeyDown);
  menu.addEventListener('click', onMenuClick);
  menu.addEventListener('keydown', onMenuKeyDown);
  document.addEventListener('pointerdown', onDocumentPointerDown, { passive: true });
  document.addEventListener('keydown', onDocumentKeyDown);

  return {
    open,
    cleanup() {
      body.removeEventListener('contextmenu', onContextMenu);
      body.removeEventListener('keydown', onKeyDown);
      menu.removeEventListener('click', onMenuClick);
      menu.removeEventListener('keydown', onMenuKeyDown);
      document.removeEventListener('pointerdown', onDocumentPointerDown);
      document.removeEventListener('keydown', onDocumentKeyDown);
      menu.remove();
    }
  };
}

function createTrophyNavigator() {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'tools-pet-navigator';
  button.dataset.sprite = 'trophy-3d-reference';
  button.setAttribute('aria-label', 'FL champion navigator. Click to open navigation.');
  button.removeAttribute('title');
  button.title = 'Champion navigator · Click to open FL routes';
  const spriteUrl = new URL('./assets/tools-pet/trophy-champion-v2.png', import.meta.url).href;
  button.innerHTML = `<span class="tools-pet-navigator-aura" aria-hidden="true"></span><img src="${spriteUrl}" alt="" aria-hidden="true" draggable="false">`;
  button.removeAttribute('title');
  return button;
}

const guardianHotspotDefinitions = [
  { key: 'shoulders', label: 'Shoulders' },
  { key: 'chest', label: 'Chest' },
  { key: 'arms', label: 'Arms' },
  { key: 'back', label: 'Back' },
  { key: 'legs', label: 'Legs' }
];

function createGuardianPresentationSurface(body) {
  const overlay = document.createElement('section');
  const overlayTitle = document.createElement('strong');
  const overlayLines = document.createElement('div');
  const effect = document.createElement('span');
  const fallback = document.createElement('div');
  const hotspots = document.createElement('div');
  const summaries = new Map();
  let route = 'home';

  overlay.className = 'guardian-pet-overlay';
  overlay.hidden = true;
  overlay.setAttribute('aria-live', 'polite');
  overlay.append(overlayTitle, overlayLines);
  effect.className = 'guardian-pet-effect';
  effect.hidden = true;
  effect.setAttribute('aria-hidden', 'true');
  fallback.className = 'guardian-pet-fallback';
  fallback.hidden = true;
  fallback.setAttribute('role', 'status');
  fallback.innerHTML = '<span aria-hidden="true">FL</span><strong>Guardian offline</strong><small>Archive controls remain available.</small>';
  hotspots.className = 'guardian-pet-hotspots';
  hotspots.setAttribute('aria-label', 'Body-region movement shortcuts');

  guardianHotspotDefinitions.forEach(definition => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'guardian-pet-hotspot';
    button.dataset.region = definition.key;
    button.setAttribute('aria-label', `${definition.label}: no recorded movement yet`);
    button.innerHTML = `<span>${definition.label}</span><small>0</small>`;
    hotspots.appendChild(button);
  });
  body.append(effect, overlay, hotspots, fallback);

  const showOverlay = (data, request = {}) => {
    if (!data?.title && !data?.lines?.length) return;
    overlayTitle.textContent = data.title || 'FITNESS LEDGER';
    overlayLines.replaceChildren(...(data.lines || []).filter(Boolean).map(line => {
      const node = document.createElement('span');
      node.textContent = String(line);
      return node;
    }));
    overlay.hidden = false;
    overlay.dataset.kind = request.kind || 'route_default';
  };
  const hideOverlay = () => {
    overlay.hidden = true;
    delete overlay.dataset.kind;
  };
  const playEffect = name => {
    if (!name || name === 'none') return;
    effect.hidden = false;
    effect.dataset.effect = name;
    effect.replaceChildren(...Array.from({ length: name === 'soft_particles' ? 9 : 1 }, () => document.createElement('i')));
  };
  const stopEffect = () => {
    effect.hidden = true;
    delete effect.dataset.effect;
    effect.replaceChildren();
  };
  const setFallback = (message = '') => {
    fallback.hidden = false;
    const canvas = body.querySelector('.tools-pet-guardian-canvas');
    if (canvas) canvas.hidden = true;
    const detail = fallback.querySelector('small');
    if (detail && message) detail.textContent = message;
  };
  const setRegions = nextSummaries => {
    summaries.clear();
    (Array.isArray(nextSummaries) ? nextSummaries : []).forEach(summary => {
      if (summary?.key) summaries.set(summary.key, summary);
    });
    hotspots.querySelectorAll('[data-region]').forEach(button => {
      const definition = guardianHotspotDefinitions.find(item => item.key === button.dataset.region);
      const summary = summaries.get(button.dataset.region) || {};
      const count = Number(summary.count) || 0;
      button.querySelector('small').textContent = String(count);
      button.disabled = !summary.representativeMovementId;
      button.setAttribute('aria-label', summary.representativeMovementId
        ? `${definition.label}: ${count} movements. Open ${summary.representativeMovementName || 'representative movement'}.`
        : `${definition.label}: no recorded movement yet`);
    });
  };
  const setRoute = nextRoute => {
    route = nextRoute || 'home';
    hotspots.hidden = !['home', 'body'].includes(route);
  };
  const onHotspotClick = event => {
    const button = event.target.closest('[data-region]');
    const summary = summaries.get(button?.dataset.region);
    if (!summary?.representativeMovementId) return;
    event.preventDefault();
    event.stopPropagation();
    location.hash = `#movements?movement_id=${encodeURIComponent(summary.representativeMovementId)}`;
  };
  const showHotspotHint = event => {
    const button = event.target.closest?.('[data-region]');
    const summary = summaries.get(button?.dataset.region);
    if (!summary || window.__fitnessLedgerGuardianPet?.getState?.().presentation?.active) return;
    const definition = guardianHotspotDefinitions.find(item => item.key === button.dataset.region);
    showOverlay({ title: `${definition.label.toUpperCase()} ARCHIVE`, lines: [`${Number(summary.count) || 0} movements`, summary.representativeMovementName] });
  };
  const hideHotspotHint = event => {
    if (event.relatedTarget?.closest?.('[data-region]')) return;
    if (!window.__fitnessLedgerGuardianPet?.getState?.().presentation?.active) hideOverlay();
  };
  hotspots.addEventListener('click', onHotspotClick);
  hotspots.addEventListener('pointerover', showHotspotHint);
  hotspots.addEventListener('pointerout', hideHotspotHint);
  hotspots.addEventListener('focusin', showHotspotHint);
  hotspots.addEventListener('focusout', hideHotspotHint);
  setRoute(route);

  return {
    showOverlay,
    hideOverlay,
    playEffect,
    stopEffect,
    setFallback,
    setRegions,
    setRoute,
    cleanup() {
      hotspots.removeEventListener('click', onHotspotClick);
      hotspots.removeEventListener('pointerover', showHotspotHint);
      hotspots.removeEventListener('pointerout', hideHotspotHint);
      hotspots.removeEventListener('focusin', showHotspotHint);
      hotspots.removeEventListener('focusout', hideHotspotHint);
      overlay.remove();
      effect.remove();
      fallback.remove();
      hotspots.remove();
    }
  };
}

function mountMousePet() {
  const body = document.createElement('div');
  const guardian = document.createElement('canvas');
  const instanceId = nextArchivePetId();
  const instanceRecord = { cleanup: null, controller: null };
  archivePetRegistry.set(instanceId, instanceRecord);
  const width = window.matchMedia?.('(max-width: 760px)').matches ? 208 : 256;
  const height = width;
  const margin = 18;
  const position = readGuardianPetPosition();
  const manualOverrides = new Map();
  let guardianPet;
  let disposed = false;
  let pendingPose = null;
  const pendingIntents = [];
  let drag = null;

  body.className = 'tools-pet-follower tools-pet-guardian tools-pet-floating';
  body.dataset.petInstance = instanceId;
  body.dataset.petPosition = 'free';
  body.dataset.petHint = 'PAUSE POINTER | FACE CURSOR | HOLD TROPHY | DRAG MOVE | ALT + DRAG VIEW | WHEEL POSE';
  body.setAttribute('role', 'region');
  body.setAttribute('tabindex', '0');
  body.setAttribute('aria-label', 'Fitness Ledger guardian pet. Pause pointer to face cursor. Hold the trophy over the pet for the champion effect. Drag to move. Alt-drag to rotate view. Wheel or left/right to change pose.');
  body.dataset.petStatus = 'Pause pointer: pet turns toward cursor | Hold trophy: champion effect | Drag: move | Alt + drag: rotate view | Wheel or left/right: change pose | Double-click: reset view';
  Object.assign(body.style, {
    position: 'fixed',
    top: '0px',
    left: '0px',
    width: `${width}px`,
    height: `${height}px`,
    flex: '0 0 auto',
    pointerEvents: 'auto',
    zIndex: '999999',
    willChange: 'transform'
  });

  guardian.title = 'Fitness Ledger guardian pet';
  guardian.className = 'tools-pet-guardian-canvas';
  guardian.tabIndex = -1;
  guardian.setAttribute('aria-hidden', 'true');
  Object.assign(guardian.style, {
    position: 'absolute',
    width: `${width}px`,
    height: `${height}px`,
    left: '0px',
    top: '0px',
    border: '0',
    pointerEvents: 'none',
    transform: 'none',
    transformOrigin: '50% 50%'
  });
  const contactShadow = document.createElement('span');
  contactShadow.className = 'tools-pet-contact-shadow';
  contactShadow.setAttribute('aria-hidden', 'true');
  body.appendChild(contactShadow);
  body.appendChild(guardian);
  const presentationSurface = createGuardianPresentationSurface(body);
  presentationSurface.setRegions(window.__fitnessLedgerGuardianBodyRegions || []);
  document.body.appendChild(body);
  const cursorMode = window.__fitnessLedgerPetCursor || new URLSearchParams(window.location.search).get('petCursor') || 'trophy';
  // The supplied recording is the default; an injected URL or query parameter can replace it for review.
  const championAudioOverride = window.__fitnessLedgerChampionAudioUrl || new URLSearchParams(window.location.search).get('championAudio');
  const championAudioUrl = championAudioOverride || new URL('./assets/tools-pet/champion-callout-trimmed.m4a?rev=20260807-v90', import.meta.url).href;
  const championCalloutText = 'And... new Olympia champion!';
  // The asset is the supplied recording with its first ~1.5s removed without
  // re-encoding. “And” begins at 0s; the original ~3.9s “new” cue is now ~2.36s.
  // The recording's currentTime—not a wall-clock timeout—drives the effect.
  const championAudioLeadTrimSeconds = Math.max(0, Number(window.__FitnessLedgerChampionAudioLeadTrimSeconds) || 0);
  const championNewCueSeconds = Math.max(0.1, Number(window.__FitnessLedgerChampionNewCueSeconds) || 2.36);
  const championAndPlaybackRate = Math.min(1, Math.max(0.78, Number(window.__FitnessLedgerChampionAndPlaybackRate) || 1));
  const championNewPlaybackRate = Math.min(1, Math.max(0.78, Number(window.__FitnessLedgerChampionNewPlaybackRate) || 0.86));
  const championDisplayPose = 'crab_hands_apart';
  let championAudio = null;
  let championCueFrame = 0;
  let championEffectTimer = 0;
  let championDisplayFrame = 0;
  let championSequenceActive = false;
  if (championAudioUrl) {
    championAudio = new Audio(championAudioUrl);
    championAudio.preload = 'auto';
    championAudio.preservesPitch = true;
    if ('webkitPreservesPitch' in championAudio) championAudio.webkitPreservesPitch = true;
    championAudio.load();
  }
  const cursorTrail = document.createElement('div');
  cursorTrail.className = `tools-pet-cursor-trail${cursorMode === 'trophy' ? ' is-trophy' : ''}`;
  cursorTrail.dataset.petInstance = instanceId;
  cursorTrail.setAttribute('aria-hidden', 'true');
  const cursorDots = Array.from({ length: 9 }, (_, index) => {
    const dot = document.createElement('i');
    dot.className = `tools-pet-cursor-dot dot-${index + 1}`;
    cursorTrail.appendChild(dot);
    return dot;
  });
  document.body.appendChild(cursorTrail);
  const navigator = createTrophyNavigator();
  navigator.hidden = cursorMode === 'trophy';
  Object.assign(navigator.style, { top: '0px', left: '0px' });
  document.body.appendChild(navigator);

  const clearChampionCueWatch = () => {
    if (!championCueFrame) return;
    window.cancelAnimationFrame(championCueFrame);
    championCueFrame = 0;
  };
  const stopChampionAudio = () => {
    if (!championAudio) return;
    championAudio.pause();
    championAudio.playbackRate = 1;
    if (championAudio.readyState >= 1) championAudio.currentTime = championAudioLeadTrimSeconds;
    body.dataset.championAudioState = 'idle';
  };
  const startChampionDisplay = () => {
    if (disposed) return;
    if (!guardianPet) {
      championSequenceActive = false;
      body.classList.remove('is-champion-sequence');
      delete body.dataset.championSequence;
      return;
    }
    window.cancelAnimationFrame(championDisplayFrame);
    body.classList.add('is-champion-display');
    body.dataset.championDisplay = 'left-to-right-sweep';
    void guardianPet.setPose?.(championDisplayPose, { source: 'champion-display', immediate: false });
    const startedAt = performance.now();
    // Keep the display inside the remaining original recording so the audio
    // carries the full left-to-right / right-to-left sweep without being cut.
    const audioRemainingMs = championAudio && Number.isFinite(championAudio.duration)
      ? Math.max(0, ((championAudio.duration - championAudio.currentTime) / Math.max(championAudio.playbackRate, 0.01)) * 1000)
      : 0;
    const duration = audioRemainingMs > 0
      ? Math.max(900, Math.min(2400, audioRemainingMs * 0.9))
      : 2200;
    const sweep = now => {
      if (disposed || !guardianPet) return;
      const progress = clamp((now - startedAt) / duration, 0, 1);
      const phase = progress < 0.5 ? progress * 2 : (progress - 0.5) * 2;
      const eased = phase < 0.5 ? 2 * phase * phase : 1 - Math.pow(-2 * phase + 2, 2) / 2;
      const x = progress < 0.5 ? -0.86 + eased * 1.72 : 0.86 - eased * 1.72;
      const y = -0.7;
      guardianPet.setFollowTarget?.({ x, y });
      guardianPet.setPointer?.({ x, y, energy: 0.45 });
      if (progress < 1) {
        championDisplayFrame = window.requestAnimationFrame(sweep);
        return;
      }
      championDisplayFrame = 0;
      body.classList.remove('is-champion-display');
      delete body.dataset.championDisplay;
      championSequenceActive = false;
      body.classList.remove('is-champion-sequence');
      delete body.dataset.championSequence;
      applyRoutePose();
    };
    championDisplayFrame = window.requestAnimationFrame(sweep);
  };
  const watchChampionNewCue = () => {
    clearChampionCueWatch();
    const watch = () => {
      if (disposed || !drag || drag.moved || drag.rotate || drag.holdTriggered) {
        championCueFrame = 0;
        return;
      }
      if (championAudio && championAudio.currentTime >= championNewCueSeconds) {
        championCueFrame = 0;
        triggerChampionHold();
        return;
      }
      championCueFrame = window.requestAnimationFrame(watch);
    };
    championCueFrame = window.requestAnimationFrame(watch);
  };
  const playChampionCallout = () => {
    if (championAudioUrl) {
      championAudio ||= new Audio(championAudioUrl);
      championAudio.preload = 'auto';
      championAudio.volume = 1;
      championAudio.pause();
      championAudio.currentTime = championAudioLeadTrimSeconds;
      championAudio.playbackRate = championAndPlaybackRate;
      championAudio.preservesPitch = true;
      if ('webkitPreservesPitch' in championAudio) championAudio.webkitPreservesPitch = true;
      body.dataset.championAudioTrim = `${championAudioLeadTrimSeconds}s`;
      body.dataset.championAudioCue = `${championNewCueSeconds}s`;
      body.dataset.championAudioRate = String(championAndPlaybackRate);
      body.dataset.championAudioState = 'play-requested';
      championAudio.play().then(() => {
        body.dataset.championAudioState = 'playing';
      }).catch(() => {
        body.dataset.championAudioState = 'play-blocked';
      });
      watchChampionNewCue();
      body.dataset.championAudio = 'original-trimmed-asset';
      return;
    }
    body.dataset.championAudio = 'silent-awaiting-audio-asset';
  };
  const triggerChampionHold = () => {
    if (disposed || !drag || drag.moved || drag.rotate || drag.holdTriggered) return;
    clearChampionCueWatch();
    drag.holdTriggered = true;
    championSequenceActive = true;
    body.classList.add('is-champion-sequence');
    body.dataset.championSequence = 'active';
    body.classList.add('is-champion-hold');
    body.dataset.championHold = 'triggered';
    body.dataset.championCallout = championCalloutText;
    presentationSurface.playEffect('champion_hold');
    if (championAudio) {
      championAudio.playbackRate = championNewPlaybackRate;
      body.dataset.championAudioRate = String(championNewPlaybackRate);
    }
    startChampionDisplay();
    window.clearTimeout(championEffectTimer);
    championEffectTimer = window.setTimeout(() => {
      body.classList.remove('is-champion-hold');
      delete body.dataset.championHold;
      presentationSurface.stopEffect();
      championEffectTimer = 0;
    }, 1700);
  };

  const viewportMax = () => ({ x: Math.max(0, window.innerWidth - width - margin * 2), y: Math.max(0, window.innerHeight - height - margin * 2) });
  const applyPosition = () => {
    const max = viewportMax();
    const x = margin + position.x * max.x;
    const y = margin + position.y * max.y;
    body.style.transform = `translate3d(${Math.round(x)}px, ${Math.round(y)}px, 0)`;
  };
  const savePosition = () => {
    try { localStorage.setItem(guardianPetPositionKey, JSON.stringify(position)); } catch {}
  };
  const movePosition = (x, y, persist = true) => {
    const max = viewportMax();
    position.x = max.x ? clamp((x - margin) / max.x, 0, 1) : 1;
    position.y = max.y ? clamp((y - margin) / max.y, 0, 1) : 1;
    applyPosition();
    if (persist) savePosition();
  };
  applyPosition();

  const currentView = () => (location.hash.slice(1).split('?')[0] || 'home');
  const applyRoutePose = ({ view = currentView() } = {}) => {
    const routeDefault = guardianPetRoutePoses[view] || guardianPetRoutePoses.home;
    const poseId = manualOverrides.get(view) || routeDefault.poseId;
    presentationSurface.setRoute(view);
    body.dataset.route = view;
    body.dataset.routePose = poseId;
    if (guardianPet) {
      void Promise.resolve(guardianPet.clearIntent?.('route-change')).then(() => {
        if (guardianPet.setPageDefault) return guardianPet.setPageDefault({ poseId, cameraPreset: routeDefault.cameraPreset });
        return guardianPet.setPose(poseId, { source: 'route' });
      });
    } else {
      pendingPose = { pose: poseId, options: { source: 'route' }, cameraPreset: routeDefault.cameraPreset };
    }
  };
  const setPetPose = (pose, options) => {
    if (guardianPet) return guardianPet.setPose(pose, options);
    pendingPose = { pose, options };
    return undefined;
  };
  const navigatorMenu = mountPetMenu(navigator, { onPose: pose => setPetPose(pose, { source: 'pet-menu' }) });
  const onNavigatorClick = event => {
    event.preventDefault();
    event.stopPropagation();
    const rect = navigator.getBoundingClientRect();
    navigator.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: rect.right, clientY: rect.top }));
  };
  navigator.addEventListener('click', onNavigatorClick);
  const onRouteChange = event => applyRoutePose(event.detail || {});
  const onGuardianIntent = event => {
    const detail = event.detail || {};
    if (detail.phase === 'finish') {
      if (guardianPet) void guardianPet.finishIntent?.(detail.id, detail.reason || 'completed');
      return;
    }
    const request = presentationForSemanticEvent(detail);
    if (!request) return;
    if (guardianPet?.setIntent) void guardianPet.setIntent(request);
    else pendingIntents.push(request);
  };
  const onBodyRegions = event => presentationSurface.setRegions(event.detail?.regions);
  window.addEventListener('fitness-ledger-pet:route-change', onRouteChange);
  window.addEventListener('fitness-ledger-pet:intent', onGuardianIntent);
  window.addEventListener('fitness-ledger-pet:body-regions', onBodyRegions);

  const petQuery = new URLSearchParams(window.location.search);
  const petController = './motion-lab/guardian/pet-guardian-static.js?v=20260807-v90';
  import(petController).then(({ mountGuardianPet }) => {
    if (disposed) return;
    guardianPet = mountGuardianPet(guardian, {
      petMode: true,
      showOverlay: presentationSurface.showOverlay,
      hideOverlay: presentationSurface.hideOverlay,
      playEffect: presentationSurface.playEffect,
      stopEffect: presentationSurface.stopEffect,
      onReady: detail => {
        body.dataset.ready = 'true';
        body.dataset.petStatus = `${detail.poses || 0} poses | Pause pointer to face cursor | Hold trophy: champion effect | Drag: move | Alt + drag: rotate view | Wheel or left/right`;
        applyRoutePose();
      },
      onError: error => {
        body.dataset.ready = 'error';
        body.dataset.petStatus = error?.message || 'Guardian Pet model load error';
        presentationSurface.setFallback('The 3D model could not be loaded. Archive controls remain available.');
      },
      onPoseChange: detail => {
        body.dataset.pose = detail.pose;
        body.setAttribute('aria-label', `Fitness Ledger guardian pet | ${detail.name}. Pause pointer to face cursor. Hold the trophy over the pet for the champion effect. Drag to move. Alt-drag to rotate view. Wheel or left/right to change pose.`);
        if (['pet-wheel', 'pet-keyboard', 'canvas-click'].includes(detail.source)) manualOverrides.set(currentView(), detail.pose);
      }
    });
    instanceRecord.controller = guardianPet;
    archivePetControllers.add(guardianPet);
    if (archivePetLease.id === instanceId) archivePetLease.controller = guardianPet;
    window.__fitnessLedgerGuardianPet = guardianPet;
    if (pendingPose) {
      const queuedPose = pendingPose;
      pendingPose = null;
      if (guardianPet.setPageDefault) void guardianPet.setPageDefault({ poseId: queuedPose.pose, cameraPreset: queuedPose.cameraPreset || 'idle' });
      else void guardianPet.setPose(queuedPose.pose, queuedPose.options);
    }
    pendingIntents.splice(0).forEach(request => { if (guardianPet.setIntent) void guardianPet.setIntent(request); });
    const pendingDetail = window.__fitnessLedgerGuardianPendingIntent;
    if (pendingDetail) {
      window.__fitnessLedgerGuardianPendingIntent = null;
      onGuardianIntent({ detail: pendingDetail });
    }
    window.dispatchEvent(new CustomEvent('fitness-ledger-pet:ready', { detail: { controller: guardianPet, poseCatalog: guardianPet.getPoseCatalog?.() || [] } }));
    body.dataset.moduleReady = 'true';
  }).catch(error => {
    console.error('[Guardian pet] controller load failed', error);
    body.dataset.ready = 'error';
    body.dataset.petStatus = error?.message || 'Guardian Pet module error';
    presentationSurface.setFallback('The 3D module is unavailable. Archive controls remain available.');
  });

  const onPetWheel = event => {
    event.preventDefault();
    if (championSequenceActive) return;
    if (event.deltaY > 0) guardianPet?.nextPose({ source: 'pet-wheel' });
    else guardianPet?.previousPose({ source: 'pet-wheel' });
  };
  const onPetKeyDown = event => {
    if (championSequenceActive) return;
    if (event.shiftKey && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
      event.preventDefault();
      const rect = body.getBoundingClientRect();
      const step = event.key === 'ArrowLeft' ? -24 : event.key === 'ArrowRight' ? 24 : 0;
      const vertical = event.key === 'ArrowUp' ? -24 : event.key === 'ArrowDown' ? 24 : 0;
      movePosition(rect.left + step, rect.top + vertical);
      return;
    }
    if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ']') {
      event.preventDefault();
      guardianPet?.nextPose({ source: 'pet-keyboard' });
    } else if (event.key === 'ArrowLeft' || event.key === 'PageUp' || event.key === '[') {
      event.preventDefault();
      guardianPet?.previousPose({ source: 'pet-keyboard' });
    }
  };
  const pointer = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.5 };
  const cursorTrailPoints = cursorDots.map((_, index) => ({ x: pointer.x, y: pointer.y, lag: 0.18 + index * 0.045 }));
  const navigatorFollower = { x: pointer.x + 22, y: pointer.y + 22, tx: pointer.x + 22, ty: pointer.y + 22 };
  let followFrame = 0;
  const onPagePointerMove = event => {
    if (event.pointerType === 'touch') return;
    pointer.x = event.clientX;
    pointer.y = event.clientY;
  };
  const updatePointerFollow = time => {
    const rect = body.getBoundingClientRect();
    const centerX = rect.left + rect.width * 0.5;
    const centerY = rect.top + rect.height * 0.5;
    const navigatorWidth = navigator.offsetWidth || 74;
    const navigatorHeight = navigator.offsetHeight || 104;
    navigatorFollower.tx = clamp(pointer.x + 22, 8, window.innerWidth - navigatorWidth - 8);
    navigatorFollower.ty = clamp(pointer.y + 20, 8, window.innerHeight - navigatorHeight - 8);
    navigatorFollower.x += (navigatorFollower.tx - navigatorFollower.x) * 0.12;
    navigatorFollower.y += (navigatorFollower.ty - navigatorFollower.y) * 0.12;
    const navigatorTilt = clamp((navigatorFollower.tx - navigatorFollower.x) * 0.12, -8, 8);
    const navigatorTiltX = clamp((navigatorFollower.ty - navigatorFollower.y) * 0.09, -9, 9);
    const navigatorTiltY = clamp((navigatorFollower.tx - navigatorFollower.x) * -0.09, -9, 9);
    navigator.style.transform = `translate3d(${Math.round(navigatorFollower.x)}px, ${Math.round(navigatorFollower.y)}px, 0) perspective(720px) rotateX(${navigatorTiltX.toFixed(2)}deg) rotateY(${navigatorTiltY.toFixed(2)}deg) rotateZ(${navigatorTilt.toFixed(2)}deg)`;
    cursorTrailPoints.forEach((point, index) => {
      const targetX = index === 0 ? pointer.x : cursorTrailPoints[index - 1].x;
      const targetY = index === 0 ? pointer.y : cursorTrailPoints[index - 1].y;
      point.x += (targetX - point.x) * (1 - point.lag);
      point.y += (targetY - point.y) * (1 - point.lag);
      const trophyMotion = cursorMode === 'trophy' && index === 0
        ? ` rotateZ(${clamp((targetX - point.x) * 0.16, -12, 12).toFixed(2)}deg) translateY(${(Math.sin(time / 220) * 1.8).toFixed(2)}px) scale(${(0.96 + Math.sin(time / 280) * 0.035).toFixed(3)})`
        : '';
      cursorDots[index].style.transform = `translate3d(${Math.round(point.x)}px, ${Math.round(point.y)}px, 0)${trophyMotion}`;
    });
    if (!championSequenceActive) {
      const pointerX = (pointer.x / Math.max(window.innerWidth, 1)) * 2 - 1;
      const pointerY = -((pointer.y / Math.max(window.innerHeight, 1)) * 2 - 1);
      guardianPet?.setPointer({ x: pointerX, y: pointerY, energy: 0 });
      guardianPet?.setFollowTarget?.({
        x: clamp((pointer.x - centerX) / Math.max(window.innerWidth * 0.5, width * 1.6), -1, 1),
        y: -clamp((pointer.y - centerY) / Math.max(window.innerHeight / 1.8, height * 1.6), -1, 1)
      });
    }
    followFrame = requestAnimationFrame(updatePointerFollow);
  };
  let viewRotation = { x: 0, y: 0 };
  const onPointerDown = event => {
    if (championSequenceActive) {
      event.preventDefault();
      return;
    }
    if (event.button !== 0 || event.target.closest('.guardian-pet-hotspot')) return;
    const rect = body.getBoundingClientRect();
    const rotate = event.altKey;
    drag = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, originX: rect.left, originY: rect.top, moved: false, holdTriggered: false, rotate, startRotation: { ...viewRotation } };
    clearChampionCueWatch();
    if (!rotate) {
      playChampionCallout();
    }
    body.setPointerCapture?.(event.pointerId);
    body.classList.toggle('is-rotating', rotate);
    body.classList.toggle('is-dragging', !rotate);
  };
  const onPointerMove = event => {
    if (championSequenceActive) {
      event.preventDefault();
      return;
    }
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    clearChampionCueWatch();
    if (!drag.holdTriggered) stopChampionAudio();
    drag.moved = true;
    if (drag.rotate) {
      viewRotation = {
        x: clamp(drag.startRotation.x + dx / 120, -1, 1),
        y: clamp(drag.startRotation.y + dy / 120, -1, 1)
      };
      guardianPet?.setViewRotation?.(viewRotation);
      return;
    }
    movePosition(drag.originX + dx, drag.originY + dy, false);
  };
  const onPointerUp = event => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    if (championSequenceActive) {
      event.preventDefault();
      clearChampionCueWatch();
      body.releasePointerCapture?.(event.pointerId);
      body.classList.remove('is-dragging', 'is-rotating');
      drag = null;
      return;
    }
    clearChampionCueWatch();
    if (!drag.holdTriggered) stopChampionAudio();
    if (drag.moved && !drag.rotate) {
      const rect = body.getBoundingClientRect();
      movePosition(rect.left, rect.top);
    }
    body.releasePointerCapture?.(event.pointerId);
    body.classList.remove('is-dragging', 'is-rotating');
    drag = null;
  };
  const onDoubleClick = event => {
    if (championSequenceActive) return;
    event.preventDefault();
    viewRotation = { x: 0, y: 0 };
    void guardianPet?.resetView?.();
  };
  const onResize = applyPosition;
  body.addEventListener('wheel', onPetWheel, { passive: false });
  body.addEventListener('keydown', onPetKeyDown);
  body.addEventListener('pointerdown', onPointerDown);
  body.addEventListener('pointermove', onPointerMove);
  body.addEventListener('pointerup', onPointerUp);
  body.addEventListener('pointercancel', onPointerUp);
  body.addEventListener('dblclick', onDoubleClick);
  window.addEventListener('pointermove', onPagePointerMove, { passive: true });
  window.addEventListener('resize', onResize);
  followFrame = requestAnimationFrame(updatePointerFollow);

  const cleanup = () => {
    if (disposed) return;
    disposed = true;
    window.removeEventListener('fitness-ledger-pet:route-change', onRouteChange);
    window.removeEventListener('fitness-ledger-pet:intent', onGuardianIntent);
    window.removeEventListener('fitness-ledger-pet:body-regions', onBodyRegions);
    window.removeEventListener('resize', onResize);
    body.removeEventListener('wheel', onPetWheel);
    body.removeEventListener('keydown', onPetKeyDown);
    body.removeEventListener('pointerdown', onPointerDown);
    body.removeEventListener('pointermove', onPointerMove);
    body.removeEventListener('pointerup', onPointerUp);
    body.removeEventListener('pointercancel', onPointerUp);
    body.removeEventListener('dblclick', onDoubleClick);
    window.removeEventListener('pointermove', onPagePointerMove);
    cancelAnimationFrame(followFrame);
    clearChampionCueWatch();
    window.clearTimeout(championEffectTimer);
    window.cancelAnimationFrame(championDisplayFrame);
    stopChampionAudio();
    championAudio?.removeAttribute?.('src');
    championAudio = null;
    navigator.removeEventListener('click', onNavigatorClick);
    navigatorMenu();
    navigator.remove();
    cursorTrail.remove();
    if (document.documentElement.dataset.petCursorOwner === instanceId) {
      delete document.documentElement.dataset.petCursor;
      delete document.documentElement.dataset.petCursorOwner;
    }
    presentationSurface.cleanup();
    guardianPet?.dispose();
    if (guardianPet) archivePetControllers.delete(guardianPet);
    if (window.__fitnessLedgerGuardianPet === guardianPet) window.__fitnessLedgerGuardianPet = null;
    if (window.__fitnessLedgerArchivePetCleanup === cleanup) window.__fitnessLedgerArchivePetCleanup = null;
    archivePetRegistry.delete(instanceId);
    if (archivePetLease.id === instanceId) {
      archivePetLease.id = null;
      archivePetLease.cleanup = null;
      archivePetLease.controller = null;
    }
    body.remove();
  };
  instanceRecord.cleanup = cleanup;
  if (archivePetLease.cleanup && archivePetLease.id !== instanceId) archivePetLease.cleanup();
  archivePetLease.id = instanceId;
  archivePetLease.cleanup = cleanup;
  document.documentElement.dataset.petCursorOwner = instanceId;
  document.documentElement.dataset.petCursor = cursorMode;
  return cleanup;
}

const removeArchivePetNodes = () => {
  document.querySelectorAll('.tools-pet-floating, .tools-pet-nav, .tools-pet-guardian, .tools-pet-navigator, .tools-pet-menu, .tools-pet-cursor-trail').forEach(node => node.remove());
};

const disposeArchivePetInstances = () => {
  const records = [...archivePetRegistry.values()];
  const leaseCleanup = archivePetLease.cleanup;
  if (typeof leaseCleanup === 'function' && !records.some(record => record.cleanup === leaseCleanup)) leaseCleanup();
  records.forEach(record => record.cleanup?.());
  [...archivePetControllers].forEach(controller => controller?.dispose?.());
  archivePetControllers.clear();
  if (!isGuardianRoute() && !records.some(record => record.controller === window.__fitnessLedgerGuardianPet)) {
    window.__fitnessLedgerGuardianPet?.dispose?.();
  }
  archivePetRegistry.clear();
  window.__fitnessLedgerArchivePetCleanup = null;
  removeArchivePetNodes();
};

const syncGlobalArchivePet = () => {
  const cleanup = window.__fitnessLedgerArchivePetCleanup;
  const floatingCount = document.querySelectorAll('.tools-pet-floating').length;
  const navigatorCount = document.querySelectorAll('.tools-pet-navigator').length;
  const legacyPetCount = document.querySelectorAll('.tools-pet-nav').length;
  if (isGuardianRoute()) {
    releaseArchivePetCrossTab();
    disposeArchivePetInstances();
    return null;
  }
  if (!claimArchivePetCrossTab()) {
    stopArchivePetCrossTabHeartbeat();
    disposeArchivePetInstances();
    return null;
  }
  window.__fitnessLedgerGuardianPageCleanup?.();
  const hasSingleLiveInstance = archivePetRegistry.size === 1
    && floatingCount === 1
    && navigatorCount === 1
    && legacyPetCount === 0
    && typeof cleanup === 'function';
  if (!hasSingleLiveInstance) {
    disposeArchivePetInstances();
  }
  if (typeof window.__fitnessLedgerArchivePetCleanup !== 'function') {
    window.__fitnessLedgerArchivePetCleanup = mountMousePet();
  }
  return window.__fitnessLedgerArchivePetCleanup;
};

export function mountGlobalArchivePet() { return syncGlobalArchivePet() || (() => {}); }

window.addEventListener('hashchange', syncGlobalArchivePet);
window.addEventListener('fitness-ledger-pet:route-change', syncGlobalArchivePet);
let archivePetMutationScheduled = false;
const archivePetDomObserver = typeof MutationObserver === 'function' && document.body ? new MutationObserver(() => {
  if (archivePetMutationScheduled) return;
  archivePetMutationScheduled = true;
  queueMicrotask(() => {
    archivePetMutationScheduled = false;
    syncGlobalArchivePet();
  });
}) : null;
archivePetDomObserver?.observe(document.body, { childList: true });

function setPanelValues(card, values, immediate = false) {
  const factor = immediate ? 1 : 0.16;
  const current = card.__tools3dCurrent || { x: 0, y: 0, z: 0, lx: 50, ly: 50 };
  current.x += (values.x - current.x) * factor;
  current.y += (values.y - current.y) * factor;
  current.z += (values.z - current.z) * factor;
  current.lx += (values.lx - current.lx) * factor;
  current.ly += (values.ly - current.ly) * factor;
  card.__tools3dCurrent = current;
  card.style.setProperty('--tools-card-tilt-x', `${current.x.toFixed(3)}deg`);
  card.style.setProperty('--tools-card-tilt-y', `${current.y.toFixed(3)}deg`);
  card.style.setProperty('--tools-card-z', `${current.z.toFixed(2)}px`);
  card.style.setProperty('--tools-card-light-x', `${current.lx.toFixed(2)}%`);
  card.style.setProperty('--tools-card-light-y', `${current.ly.toFixed(2)}%`);
}

export function mountToolsCSS3DPanels(page) {
  if (!page || page.dataset.tools3dReady === 'true') return () => {};

  const shell = page.querySelector('.tools-lab-shell');
  const cards = [...page.querySelectorAll('.tools-card[data-tools-panel]')];
  if (!shell || !cards.length) return () => {};
  page.dataset.tools3dReady = 'true';
  page.dataset.tools3dStatus = finePointer ? 'ready' : 'static';

  const pointer = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.5, inside: false, card: null };
  const target = { x: 0, y: 0 };
  let activeRoute = null;
  let frame = 0;

  const applyRouteState = (nextRoute) => {
    activeRoute = cards.some((card) => card.dataset.toolsPanel === nextRoute) ? nextRoute : null;
    cards.forEach((card) => {
      const isActive = activeRoute === card.dataset.toolsPanel;
      card.dataset.toolsRouteActive = isActive ? 'true' : 'false';
      if (isActive) card.style.setProperty('--tools-card-route-z', '18px');
      else card.style.removeProperty('--tools-card-route-z');
    });
  };

  const routeFromEvent = (event) => event.target?.closest?.('.tools-card[data-tools-panel]')?.dataset.toolsPanel || null;
  const onRoutePointerOver = (event) => applyRouteState(routeFromEvent(event));
  const onRoutePointerOut = (event) => {
    if (!event.relatedTarget?.closest?.('.tools-card[data-tools-panel]')) applyRouteState(null);
  };
  const onRouteFocus = (event) => applyRouteState(routeFromEvent(event));
  const onRouteBlur = (event) => {
    if (!event.relatedTarget?.closest?.('.tools-card[data-tools-panel]')) applyRouteState(null);
  };
  document.addEventListener('pointerover', onRoutePointerOver, { passive: true });
  document.addEventListener('pointerout', onRoutePointerOut, { passive: true });
  document.addEventListener('focusin', onRouteFocus);
  document.addEventListener('focusout', onRouteBlur);

  const onPointerMove = (event) => {
    if (event.pointerType === 'touch') return;
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    const stage = event.target?.closest?.('.tools-lab-shell');
    pointer.inside = stage === shell;
    pointer.card = pointer.inside ? event.target?.closest?.('.tools-card[data-tools-panel]') : null;
    if (!pointer.inside) {
      target.x = 0;
      target.y = 0;
      return;
    }
    const rect = shell.getBoundingClientRect();
    target.x = clamp(((event.clientX - rect.left) / Math.max(rect.width, 1) - 0.5) * 2, -1, 1);
    target.y = clamp(((event.clientY - rect.top) / Math.max(rect.height, 1) - 0.5) * 2, -1, 1);
  };
  const onPointerLeave = () => {
    pointer.inside = false;
    pointer.card = null;
    target.x = 0;
    target.y = 0;
    applyRouteState(null);
  };
  page.addEventListener('pointermove', onPointerMove, { passive: true });
  page.addEventListener('pointerleave', onPointerLeave, { passive: true });

  const render = () => {
    const shellX = pointer.inside ? target.x * 0.58 : 0;
    const shellY = pointer.inside ? -target.y * 0.44 : 0;
    shell.style.setProperty('--tools-shell-tilt-x', `${shellX.toFixed(3)}deg`);
    shell.style.setProperty('--tools-shell-tilt-y', `${shellY.toFixed(3)}deg`);
    page.style.setProperty('--tools-field-x', `${(50 + target.x * 28).toFixed(2)}%`);
    page.style.setProperty('--tools-field-y', `${(42 + target.y * 24).toFixed(2)}%`);

    cards.forEach((card) => {
      const rect = card.getBoundingClientRect();
      const localX = clamp((pointer.x - (rect.left + rect.width * 0.5)) / Math.max(rect.width * 0.5, 1), -1, 1);
      const localY = clamp((pointer.y - (rect.top + rect.height * 0.5)) / Math.max(rect.height * 0.5, 1), -1, 1);
      const isFocused = pointer.card === card;
      const cardX = isFocused ? localX * 2.4 + target.x * 0.25 : 0;
      const cardY = isFocused ? -localY * 2.1 - target.y * 0.18 : 0;
      const cardZ = activeRoute === card.dataset.toolsPanel ? 10 : isFocused && Math.abs(localX) < 0.78 && Math.abs(localY) < 0.78 ? 4 : 0;
      setPanelValues(card, { x: cardX, y: cardY, z: cardZ, lx: 50 + localX * 34, ly: 50 + localY * 34 });
    });
    frame = requestAnimationFrame(render);
  };

  const resizeObserver = new ResizeObserver(() => {
    if (!page.isConnected) cleanup();
  });
  resizeObserver.observe(page);

  if (finePointer && !reduceMotion) frame = requestAnimationFrame(render);
  else cards.forEach((card) => setPanelValues(card, { x: 0, y: 0, z: 0, lx: 50, ly: 50 }, true));

  function cleanup() {
    cancelAnimationFrame(frame);
    resizeObserver.disconnect();
    page.removeEventListener('pointermove', onPointerMove);
    page.removeEventListener('pointerleave', onPointerLeave);
    document.removeEventListener('pointerover', onRoutePointerOver);
    document.removeEventListener('pointerout', onRoutePointerOut);
    document.removeEventListener('focusin', onRouteFocus);
    document.removeEventListener('focusout', onRouteBlur);
    shell.style.removeProperty('--tools-shell-tilt-x');
    shell.style.removeProperty('--tools-shell-tilt-y');
    page.style.removeProperty('--tools-field-x');
    page.style.removeProperty('--tools-field-y');
    cards.forEach((card) => {
      delete card.dataset.toolsRouteActive;
      card.style.removeProperty('--tools-card-route-z');
      card.style.removeProperty('--tools-card-tilt-x');
      card.style.removeProperty('--tools-card-tilt-y');
      card.style.removeProperty('--tools-card-z');
      card.style.removeProperty('--tools-card-light-x');
      card.style.removeProperty('--tools-card-light-y');
      delete card.__tools3dCurrent;
    });
    delete page.dataset.tools3dReady;
    delete page.dataset.tools3dStatus;
  }

  window.__fitnessLedgerTools3DCleanup = cleanup;
  return cleanup;
}
