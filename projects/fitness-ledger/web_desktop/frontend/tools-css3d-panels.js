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

import { presentationForSemanticEvent } from './motion-lab/guardian/guardian-intent-map.js?v=20260807-v62';

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

  return () => {
    body.removeEventListener('contextmenu', onBodyContextMenu);
    body.removeEventListener('keydown', onBodyKeyDown);
    menu.removeEventListener('click', onMenuClick);
    menu.removeEventListener('keydown', onMenuKeyDown);
    document.removeEventListener('pointerdown', onDocumentPointerDown);
    document.removeEventListener('keydown', onDocumentKeyDown);
    menu.remove();
  };
}

function mountLegacyMousePet() {
  const pointer = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.5 };
  const follower = { x: pointer.x, y: pointer.y, tx: pointer.x, ty: pointer.y };
  const body = document.createElement('div');
  const guardian = document.createElement('canvas');
  const petQuery = new URLSearchParams(window.location.search);
  const navSlot = document.querySelector('[data-guardian-nav-slot]');
  const navStatus = navSlot?.querySelector('[data-guardian-nav-status]');
  const navMode = Boolean(navSlot);
  const cornerMode = !navMode && petQuery.get('petFollow') !== '1';
  let guardianPet;
  let disposed = false;
  let pendingPose = null;
  const width = 120;
  const height = 120;
  const spring = reduceMotion ? 1 : 8;
  const inertia = reduceMotion ? 1 : 30;

  body.className = 'tools-pet-follower tools-pet-guardian tools-pet-nav';
  body.dataset.petPosition = navMode ? 'nav' : cornerMode ? 'corner' : 'follow';
  body.dataset.petHint = 'CLICK MENU · WHEEL / ← → POSE';
  body.setAttribute('role', 'button');
  body.setAttribute('tabindex', '0');
  body.setAttribute('aria-label', 'Fitness Ledger guardian pet. Click for pose menu. Use wheel or left and right arrows to change pose.');
  body.title = 'Click: pose menu · Wheel or ← →: change pose';
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
  if (cornerMode) {
    Object.assign(body.style, { top: 'auto', left: 'auto', right: '22px', bottom: '22px', transform: 'translate3d(0, 0, 0)' });
  }

  const syncNavPetPosition = () => {
    if (!navMode || !navSlot) return;
    const rect = navSlot.getBoundingClientRect();
    body.style.left = `${Math.round(rect.left + rect.width * 0.5 - width * 0.5)}px`;
    body.style.top = `${Math.round(rect.top + 2)}px`;
  };

  guardian.title = 'Fitness Ledger guardian pet';
  guardian.className = 'tools-pet-guardian-canvas';
  guardian.tabIndex = -1;
  guardian.setAttribute('aria-hidden', 'true');
  guardian.setAttribute('loading', 'eager');
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

  body.appendChild(guardian);
  document.body.appendChild(body);
  syncNavPetPosition();
  const petModel = window.__fitnessLedgerPetModel || new URLSearchParams(window.location.search).get('petModel') || 'lowpoly-static';
  const petController = petModel === 'legacy' ? './motion-lab/guardian/pet-guardian.js?v=20260807-v62' : './motion-lab/guardian/pet-guardian-static.js?v=20260807-v62';
  const setPetPose = (pose, options) => {
    if (guardianPet) return guardianPet.setPose(pose, options);
    pendingPose = { pose, options };
    return undefined;
  };
  import(petController).then(({ mountGuardianPet }) => {
    if (disposed) return;
    guardianPet = mountGuardianPet(guardian, {
      petMode: true,
      onReady: detail => {
        body.dataset.ready = 'true';
        if (navSlot) navSlot.dataset.petState = 'ready';
        if (navStatus) navStatus.textContent = 'CLICK · WHEEL / ← →';
        body.title = `${detail.poses || 0} poses · Click menu · Wheel or ← →`;
      },
      onError: error => {
        body.dataset.ready = 'error';
        if (navSlot) navSlot.dataset.petState = 'error';
        if (navStatus) navStatus.textContent = 'PET MODEL ERROR';
        body.title = error?.message || 'Guardian Pet model load error';
      },
      onPoseChange: detail => {
        body.dataset.pose = detail.pose;
        body.setAttribute('aria-label', `Fitness Ledger guardian pet · ${detail.name}`);
      }
    });
    window.__fitnessLedgerGuardianPet = guardianPet;
    if (pendingPose) {
      const queuedPose = pendingPose;
      pendingPose = null;
      guardianPet.setPose(queuedPose.pose, queuedPose.options);
    }
    window.dispatchEvent(new CustomEvent('fitness-ledger-pet:ready', { detail: { controller: guardianPet, poseCatalog: guardianPet.getPoseCatalog?.() || [] } }));
    body.dataset.moduleReady = 'true';
  }).catch(error => {
    console.error('[Guardian pet] controller load failed', error);
    body.dataset.ready = 'error';
    if (navSlot) navSlot.dataset.petState = 'error';
    if (navStatus) navStatus.textContent = 'PET MODULE ERROR';
  });
  const cleanupMenu = mountPetMenu(body, { onPose: pose => setPetPose(pose, { source: 'pet-menu' }) });

  const onBodyClick = (event) => {
    event.preventDefault();
    event.stopPropagation();
    const rect = body.getBoundingClientRect();
    body.dispatchEvent(new MouseEvent('contextmenu', {
      bubbles: true,
      clientX: rect.left + rect.width,
      clientY: rect.top + rect.height
    }));
  };
  body.addEventListener('click', onBodyClick);

  const onPetWheel = event => {
    event.preventDefault();
    if (event.deltaY > 0) guardianPet?.nextPose({ source: 'pet-wheel' });
    else guardianPet?.previousPose({ source: 'pet-wheel' });
  };
  const onPetKeyDown = event => {
    if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ']') {
      event.preventDefault();
      guardianPet?.nextPose();
    } else if (event.key === 'ArrowLeft' || event.key === 'PageUp' || event.key === '[') {
      event.preventDefault();
      guardianPet?.previousPose();
    }
  };
  body.addEventListener('wheel', onPetWheel, { passive: false });
  body.addEventListener('keydown', onPetKeyDown);

  const onPointerMove = (event) => {
    if (event.pointerType === 'touch') return;
    pointer.x = event.clientX;
    pointer.y = event.clientY;
  };

  let frame = 0;
  const tick = (time) => {
    syncNavPetPosition();
    const dx = pointer.x - follower.x;
    const dy = pointer.y - follower.y;
    follower.tx += dx / inertia;
    follower.ty += dy / inertia;
    follower.x += (follower.tx - follower.x) / spring;
    follower.y += (follower.ty - follower.y) / spring;

    const distance = Math.hypot(dx, dy);
    body.style.setProperty('--pet-energy', `${Math.min(1, distance / 220).toFixed(3)}`);
    guardianPet?.setPointer({
      type: 'fitness-ledger-pet-pointer',
      x: (pointer.x / Math.max(window.innerWidth, 1)) * 2 - 1,
      y: -((pointer.y / Math.max(window.innerHeight, 1)) * 2 - 1),
      energy: Math.min(1, distance / 220)
    });
    if (!navMode && !cornerMode) body.style.transform = `translate3d(${follower.x - width * 0.5 + 18}px, ${follower.y - height * 0.5 + 18}px, 0)`;
    frame = requestAnimationFrame(tick);
  };

  window.addEventListener('pointermove', onPointerMove, { passive: true });
  frame = requestAnimationFrame(tick);

  return () => {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(frame);
    window.removeEventListener('pointermove', onPointerMove);
    body.removeEventListener('click', onBodyClick);
    body.removeEventListener('wheel', onPetWheel);
    body.removeEventListener('keydown', onPetKeyDown);
    guardianPet?.dispose();
    if (window.__fitnessLedgerGuardianPet === guardianPet) window.__fitnessLedgerGuardianPet = null;
    if (window.__fitnessLedgerArchivePetCleanup === cleanup) window.__fitnessLedgerArchivePetCleanup = null;
    cleanupMenu();
    body.remove();
  };
}

const guardianPetPositionKey = 'fitness-ledger.guardian-pet.position.v1';
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
  button.setAttribute('aria-label', 'FL champion navigator. Click to open navigation.');
  button.title = 'Champion navigator · Click to open FL routes';
  button.innerHTML = `<span class="tools-pet-navigator-aura" aria-hidden="true"></span><svg viewBox="0 0 90 118" aria-hidden="true" focusable="false"><defs><linearGradient id="guardian-trophy-bronze" x1="15%" y1="5%" x2="85%" y2="95%"><stop offset="0" stop-color="#fff1b0"/><stop offset=".2" stop-color="#cf8d3c"/><stop offset=".46" stop-color="#784018"/><stop offset=".68" stop-color="#e2a85b"/><stop offset="1" stop-color="#4a2615"/></linearGradient><linearGradient id="guardian-trophy-base" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#3d2317"/><stop offset=".45" stop-color="#b87532"/><stop offset="1" stop-color="#5b3018"/></linearGradient></defs><g fill="url(#guardian-trophy-bronze)" stroke="#3f2415" stroke-width="1.25" stroke-linejoin="round"><circle cx="45" cy="14" r="7"/><path d="M36 23c-3 7-4 14-2 20 2 7 7 11 11 12 5-1 10-5 12-12 2-6 1-13-2-20-6 2-13 2-19 0z"/><path d="M33 26c-7 1-13 4-17 9-2 3-1 6 2 7l16 1 2-8zM57 26c7 1 13 4 17 9 2 3 1 6-2 7l-16 1-2-8z"/><path d="M37 51l-7 23 9 6 6-22 6 22 9-6-7-23c-5 3-11 3-16 0z"/><path d="M30 74l-5 16 13 4 4-13zM60 74l5 16-13 4-4-13z"/></g><path d="M27 34L70 98" fill="none" stroke="#f2c477" stroke-width="2.7" stroke-linecap="round"/><circle cx="25" cy="31" r="5" fill="url(#guardian-trophy-bronze)" stroke="#3f2415" stroke-width="1.25"/><circle cx="71" cy="100" r="5" fill="url(#guardian-trophy-bronze)" stroke="#3f2415" stroke-width="1.25"/><path d="M17 94h56l7 7H10z" fill="url(#guardian-trophy-base)" stroke="#3f2415" stroke-width="1.25"/><path d="M24 101h42v7H24z" fill="#8a5427" stroke="#3f2415" stroke-width="1.25"/><path d="M33 105h24" stroke="#f0c174" stroke-width="1.1" stroke-linecap="round" opacity=".75"/></svg>`;
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
  const width = 204;
  const height = 204;
  const margin = 18;
  const position = readGuardianPetPosition();
  const manualOverrides = new Map();
  let guardianPet;
  let disposed = false;
  let pendingPose = null;
  const pendingIntents = [];
  let drag = null;

  body.className = 'tools-pet-follower tools-pet-guardian tools-pet-floating';
  body.dataset.petPosition = 'free';
  body.dataset.petHint = 'PAUSE POINTER | FACE CURSOR | DRAG MOVE | ALT + DRAG VIEW | WHEEL POSE';
  body.setAttribute('role', 'region');
  body.setAttribute('tabindex', '0');
  body.setAttribute('aria-label', 'Fitness Ledger guardian pet. Pause pointer to face cursor. Drag to move. Alt-drag to rotate view. Wheel or left/right to change pose.');
  body.title = 'Pause pointer: pet turns toward cursor | Drag: move | Alt + drag: rotate view | Wheel or left/right: change pose | Double-click: reset view';
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
  const navigator = createTrophyNavigator();
  document.body.appendChild(navigator);

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
  const petModel = window.__fitnessLedgerPetModel || petQuery.get('petModel') || 'lowpoly-static';
  const petController = petModel === 'legacy' ? './motion-lab/guardian/pet-guardian.js?v=20260807-v62' : './motion-lab/guardian/pet-guardian-static.js?v=20260807-v62';
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
        body.title = `${detail.poses || 0} poses | Pause pointer to face cursor | Drag: move | Alt + drag: rotate view | Wheel or left/right`;
        applyRoutePose();
      },
      onError: error => {
        body.dataset.ready = 'error';
        body.title = error?.message || 'Guardian Pet model load error';
        presentationSurface.setFallback('The 3D model could not be loaded. Archive controls remain available.');
      },
      onPoseChange: detail => {
        body.dataset.pose = detail.pose;
        body.setAttribute('aria-label', `Fitness Ledger guardian pet | ${detail.name}. Pause pointer to face cursor. Drag to move. Alt-drag to rotate view. Wheel or left/right to change pose.`);
        if (['pet-wheel', 'pet-keyboard', 'canvas-click'].includes(detail.source)) manualOverrides.set(currentView(), detail.pose);
      }
    });
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
    body.title = error?.message || 'Guardian Pet module error';
    presentationSurface.setFallback('The 3D module is unavailable. Archive controls remain available.');
  });

  const onPetWheel = event => {
    event.preventDefault();
    if (event.deltaY > 0) guardianPet?.nextPose({ source: 'pet-wheel' });
    else guardianPet?.previousPose({ source: 'pet-wheel' });
  };
  const onPetKeyDown = event => {
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
  const pointer = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.5, lastMoveAt: performance.now() };
  const navigatorFollower = { x: pointer.x + 22, y: pointer.y + 22, tx: pointer.x + 22, ty: pointer.y + 22 };
  let followFrame = 0;
  const onPagePointerMove = event => {
    if (event.pointerType === 'touch') return;
    const moved = Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y);
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    if (moved >= 2) pointer.lastMoveAt = performance.now();
  };
  const updatePointerFollow = time => {
    const rect = body.getBoundingClientRect();
    const centerX = rect.left + rect.width * 0.5;
    const centerY = rect.top + rect.height * 0.5;
    navigatorFollower.tx = clamp(pointer.x + 22, 8, window.innerWidth - 82);
    navigatorFollower.ty = clamp(pointer.y + 20, 8, window.innerHeight - 112);
    navigatorFollower.x += (navigatorFollower.tx - navigatorFollower.x) * 0.12;
    navigatorFollower.y += (navigatorFollower.ty - navigatorFollower.y) * 0.12;
    const navigatorTilt = clamp((navigatorFollower.tx - navigatorFollower.x) * 0.12, -8, 8);
    navigator.style.transform = `translate3d(${Math.round(navigatorFollower.x)}px, ${Math.round(navigatorFollower.y)}px, 0) rotate(${navigatorTilt.toFixed(2)}deg)`;
    const pointerX = (pointer.x / Math.max(window.innerWidth, 1)) * 2 - 1;
    const pointerY = -((pointer.y / Math.max(window.innerHeight, 1)) * 2 - 1);
    const stationary = time - pointer.lastMoveAt >= 260;
    guardianPet?.setPointer({ x: pointerX, y: pointerY, energy: 0 });
    if (stationary && !drag) {
      guardianPet?.setFollowTarget?.({
        x: clamp((pointer.x - centerX) / Math.max(window.innerWidth * 0.32, 260), -1, 1),
        y: clamp((pointer.y - centerY) / Math.max(window.innerHeight * 0.26, 180), -1, 1)
      });
    } else {
      guardianPet?.setFollowTarget?.({ x: 0, y: 0 });
    }
    followFrame = requestAnimationFrame(updatePointerFollow);
  };
  let viewRotation = { x: 0, y: 0 };
  const onPointerDown = event => {
    if (event.button !== 0 || event.target.closest('.guardian-pet-hotspot')) return;
    const rect = body.getBoundingClientRect();
    const rotate = event.altKey;
    drag = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, originX: rect.left, originY: rect.top, moved: false, rotate, startRotation: { ...viewRotation } };
    body.setPointerCapture?.(event.pointerId);
    body.classList.toggle('is-rotating', rotate);
    body.classList.toggle('is-dragging', !rotate);
  };
  const onPointerMove = event => {
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
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
    if (drag.moved && !drag.rotate) {
      const rect = body.getBoundingClientRect();
      movePosition(rect.left, rect.top);
    }
    body.releasePointerCapture?.(event.pointerId);
    body.classList.remove('is-dragging', 'is-rotating');
    drag = null;
  };
  const onDoubleClick = event => {
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

  return () => {
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
    navigator.removeEventListener('click', onNavigatorClick);
    navigatorMenu();
    navigator.remove();
    presentationSurface.cleanup();
    guardianPet?.dispose();
    if (window.__fitnessLedgerGuardianPet === guardianPet) window.__fitnessLedgerGuardianPet = null;
    body.remove();
  };
}

export function mountGlobalArchivePet() {
  if (typeof window.__fitnessLedgerArchivePetCleanup === 'function') return window.__fitnessLedgerArchivePetCleanup;
  const cleanup = mountMousePet();
  window.__fitnessLedgerArchivePetCleanup = cleanup;
  return cleanup;
}

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
