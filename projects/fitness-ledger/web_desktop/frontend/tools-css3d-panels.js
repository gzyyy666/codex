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

const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const finePointer = window.matchMedia?.('(hover: hover) and (pointer: fine)').matches;

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
      { view: 'dictionary', label: 'Movement Dictionary', meta: '07 / DICTIONARY' }
    ]
  }
];

function mountPetMenu(body) {
  const menu = document.createElement('aside');
  menu.className = 'tools-pet-menu';
  menu.hidden = true;
  menu.dataset.open = 'false';
  menu.setAttribute('aria-label', 'Fitness Ledger 快捷导航');
  menu.setAttribute('role', 'menu');
  menu.innerHTML = `<header><span class="eyebrow">PET ROUTER / LOCAL</span><strong>Go somewhere.</strong></header>${petNavigation.map((group) => `<section><span class="tools-pet-menu-label">${group.label}</span>${group.routes.map((route) => `<button type="button" role="menuitem" class="tools-pet-menu-item" data-pet-route-view="${route.view}"${route.panel?` data-pet-route-panel="${route.panel}"`:''}><span>${route.label}</span><small>${route.meta}</small></button>`).join('')}</section>`).join('')}`;
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

function mountMousePet() {
  if (!finePointer || reduceMotion) return () => {};

  const pointer = { x: window.innerWidth * 0.5, y: window.innerHeight * 0.5 };
  const follower = { x: pointer.x, y: pointer.y, tx: pointer.x, ty: pointer.y };
  const body = document.createElement('div');
  const eyes = document.createElement('div');
  const width = 34;
  const height = 34;
  const spring = 8;
  const inertia = 30;

  body.className = 'tools-pet-follower';
  body.setAttribute('role', 'button');
  body.setAttribute('tabindex', '0');
  body.setAttribute('aria-label', '打开 Fitness Ledger 快捷导航');
  Object.assign(body.style, {
    position: 'fixed',
    top: '0px',
    left: '0px',
    width: `${width}px`,
    height: `${height}px`,
    pointerEvents: 'auto',
    zIndex: '45',
    backgroundImage: 'url("assets/tools-pet/ghost_body_tartan.gif")',
    backgroundSize: 'contain',
    backgroundRepeat: 'no-repeat',
    imageRendering: 'pixelated',
    opacity: '0.72',
    willChange: 'transform'
  });

  Object.assign(eyes.style, {
    position: 'absolute',
    width: '12px',
    height: '16px',
    backgroundImage: 'url("assets/tools-pet/ghost_eyes.gif")',
    backgroundRepeat: 'no-repeat',
    imageRendering: 'pixelated',
    pointerEvents: 'none'
  });

  body.appendChild(eyes);
  document.body.appendChild(body);
  const cleanupMenu = mountPetMenu(body);

  const onPointerMove = (event) => {
    if (event.pointerType === 'touch') return;
    pointer.x = event.clientX;
    pointer.y = event.clientY;
  };

  let frame = 0;
  const tick = () => {
    const dx = pointer.x - follower.x;
    const dy = pointer.y - follower.y;
    follower.tx += dx / inertia;
    follower.ty += dy / inertia;
    follower.x += (follower.tx - follower.x) / spring;
    follower.y += (follower.ty - follower.y) / spring;

    const eyeX = (width - 12) * 0.5;
    const eyeY = (height - 16) * 0.5;
    const angle = Math.atan2(pointer.y - follower.y, pointer.x - follower.x);
    eyes.style.transform = `translate(${eyeX + Math.cos(angle) * 3}px, ${eyeY + Math.sin(angle) * 3}px)`;
    body.style.transform = `translate3d(${follower.x - width * 0.5 + 18}px, ${follower.y - height * 0.5 + 18}px, 0)`;
    frame = requestAnimationFrame(tick);
  };

  window.addEventListener('pointermove', onPointerMove, { passive: true });
  frame = requestAnimationFrame(tick);

  return () => {
    cancelAnimationFrame(frame);
    window.removeEventListener('pointermove', onPointerMove);
    cleanupMenu();
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
