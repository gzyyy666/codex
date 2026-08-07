import * as THREE from './three.module.min.js?v=20260807-v63';
import { GLTFLoader } from './GLTFLoader.js?v=20260807-v63';
import { OrbitControls } from './OrbitControls.js?v=20260807-v63';
import { degreesToRadians, patchGuardianMaterial } from './guardian-shader-deformation.js?v=20260807-v65';
import { createGuardianPresentationManager } from './guardian-presentation-manager.js?v=20260807-v63';

const POSE_ORDER = Object.freeze([
  'standing',
  'front_double_biceps',
  'side_chest',
  'back_double_biceps',
  'back_lat_spread',
  'crab_hands_clasped',
  'crab_hands_apart'
]);

const POSE_FILES = Object.freeze({
  'standing_front_relaxed.glb': 'lowpoly-front-standing.glb',
  'front_double_biceps.glb': 'lowpoly-front-double-biceps.glb',
  'side_chest.glb': 'lowpoly-side-chest.glb',
  'back_double_biceps.glb': 'lowpoly-rear-double-biceps.glb',
  'back_lat_spread.glb': 'lowpoly-rear-lat-spread.glb',
  'most_muscular_hands_clasped.glb': 'lowpoly-most-muscular.glb',
  'most_muscular_hands_apart.glb': 'lowpoly-open-hand-crab.glb'
});

const POSE_ALIASES = Object.freeze({
  'front-standing': 'standing',
  'front-lat-spread': 'standing',
  'front-double-biceps': 'front_double_biceps',
  'side-chest': 'side_chest',
  'rear-double-biceps': 'back_double_biceps',
  'rear-lat-spread': 'back_lat_spread',
  'most-muscular': 'crab_hands_clasped',
  'open-hand-crab': 'crab_hands_apart',
  'crab-open': 'crab_hands_apart',
  'side-triceps': 'side_chest',
  'abs-thighs': 'standing'
});

const POSE_COPY = Object.freeze({
  standing: 'A quiet neutral stance for the local archive.',
  front_double_biceps: 'Front development and a clear training checkpoint.',
  side_chest: 'A controlled side view for shoulder and chest context.',
  back_double_biceps: 'Rear-chain development without losing the stable base.',
  back_lat_spread: 'Back width held in the accepted v6.2 scale.',
  crab_hands_clasped: 'A restrained acknowledgement after a saved session.',
  crab_hands_apart: 'A stronger acknowledgement for a verified personal record.'
});

export const GUARDIAN_POSE_CATALOG = POSE_ORDER.map((id, index) => ({ id, index }));

const configurationPromise = Promise.all([
  fetch(new URL('./config/pose-config.json', import.meta.url)).then(response => {
    if (!response.ok) throw new Error(`Guardian pose config failed (${response.status})`);
    return response.json();
  }),
  fetch(new URL('./config/camera-presets.json', import.meta.url)).then(response => {
    if (!response.ok) throw new Error(`Guardian camera config failed (${response.status})`);
    return response.json();
  }),
  fetch(new URL('./config/intent-config.json', import.meta.url)).then(response => {
    if (!response.ok) throw new Error(`Guardian intent config failed (${response.status})`);
    return response.json();
  })
]).then(([poseConfig, cameraConfig, intentConfig]) => ({ poseConfig, cameraConfig, intentConfig }));

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const resolvePoseId = input => {
  if (typeof input === 'string') {
    const normalized = POSE_ALIASES[input] || input;
    return POSE_ORDER.includes(normalized) ? normalized : POSE_ORDER[0];
  }
  const numeric = Math.round(Number(input));
  return Number.isFinite(numeric) ? POSE_ORDER[((numeric % POSE_ORDER.length) + POSE_ORDER.length) % POSE_ORDER.length] : POSE_ORDER[0];
};
const assetUrl = file => new URL(`./assets/lowpoly/${POSE_FILES[file] || file}`, import.meta.url).href;
const cloneState = state => JSON.parse(JSON.stringify(state));
const guardianControllerRegistry = window.__fitnessLedgerGuardianControllerRegistry instanceof Set
  ? window.__fitnessLedgerGuardianControllerRegistry
  : (window.__fitnessLedgerGuardianControllerRegistry = new Set());

export function mountGuardianPet(canvas, options = {}) {
  if (!canvas?.getContext) throw new TypeError('mountGuardianPet requires a canvas');
  [...guardianControllerRegistry].forEach(controller => controller?.dispose?.());
  const params = new URLSearchParams(location.search);
  const petMode = params.get('embed') === 'pet' || options.petMode === true;
  const presentationScale = petMode ? 1.06 : 1;
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(31, 1, 0.05, 20);
  camera.position.set(0, 0.5, 2.18);
  const cameraLookAt = new THREE.Vector3(0, 0.5, 0);
  camera.lookAt(cameraLookAt);

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    premultipliedAlpha: false,
    powerPreference: 'high-performance'
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.08;

  scene.add(new THREE.HemisphereLight(0xe8e4d8, 0x1b2530, 2.25));
  const keyLight = new THREE.DirectionalLight(0xffe6c4, 3.1);
  keyLight.position.set(3.2, 5.4, 4.8);
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0xd8c39d, 1.25);
  fillLight.position.set(-2.6, 2.4, 3.5);
  scene.add(fillLight);
  const rimLight = new THREE.DirectionalLight(0xa8bfd0, 1.7);
  rimLight.position.set(-4.2, 3.0, -4.8);
  scene.add(rimLight);
  const keyLightHome = keyLight.position.clone();

  const ambientMotes = petMode ? (() => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array([
      -0.42, 0.48, -0.46, -0.18, 1.24, 0.54, -0.34, 2.08, 0.12,
      -0.16, 2.78, -0.52, -0.44, 1.76, 0.58, -0.28, 0.92, -0.62,
      -0.52, 2.52, 0.42, -0.08, 0.26, 0.36
    ]), 3));
    const material = new THREE.PointsMaterial({ color: 0xf0d69f, size: 0.018, transparent: true, opacity: 0.16, depthWrite: false });
    const points = new THREE.Points(geometry, material);
    scene.add(points);
    return points;
  })() : null;

  const controls = petMode ? null : new OrbitControls(camera, canvas);
  if (controls) {
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.minDistance = 1.2;
    controls.maxDistance = 6;
    controls.target.copy(cameraLookAt);
  }

  const state = {
    poseId: 'standing',
    cameraPreset: 'idle',
    pointerX: 0,
    pointerY: 0,
    targetX: 0,
    targetY: 0,
    aimX: 0,
    aimY: 0,
    response: Number.isFinite(options.response) ? options.response : 0.82,
    reducedMotion: options.reducedMotion ?? Boolean(media?.matches),
    zoom: 1,
    targetZoom: 1,
    offsetX: 0,
    offsetY: 0,
    yawOffset: 0,
    viewRotation: { x: 0, y: 0 },
    ready: false,
    failed: false,
    disposed: false
  };
  const models = new Map();
  const modelLoads = new Map();
  const modelRecords = new Set();
  const cameraGoal = camera.position.clone();
  const lookGoal = cameraLookAt.clone();
  const adjustedCameraGoal = camera.position.clone();
  const adjustedLookGoal = cameraLookAt.clone();
  let configuration = null;
  let activeRecord = null;
  let frame = 0;
  let poseToken = 0;
  let visible = document.visibilityState !== 'hidden';
  let readyNotified = false;
  let failureNotified = false;

  const notifyFailure = error => {
    if (failureNotified || state.disposed) return;
    failureNotified = true;
    state.failed = true;
    canvas.hidden = true;
    options.onError?.(error);
    console.error('[Guardian pet] rendering fallback enabled', error);
  };

  const smoothNonIndexedNormals = geometry => {
    const position = geometry?.getAttribute?.('position');
    if (!position || geometry.index || position.count < 3 || position.count % 3 !== 0) return;
    const groups = new Map();
    const keys = new Array(position.count);
    const quantize = value => Math.round(value * 100000);
    const keyAt = index => `${quantize(position.getX(index))}:${quantize(position.getY(index))}:${quantize(position.getZ(index))}`;
    for (let offset = 0; offset < position.count; offset += 3) {
      const a = new THREE.Vector3(position.getX(offset), position.getY(offset), position.getZ(offset));
      const b = new THREE.Vector3(position.getX(offset + 1), position.getY(offset + 1), position.getZ(offset + 1));
      const c = new THREE.Vector3(position.getX(offset + 2), position.getY(offset + 2), position.getZ(offset + 2));
      const normal = new THREE.Vector3().crossVectors(b.sub(a), c.sub(a));
      [offset, offset + 1, offset + 2].forEach(index => {
        const key = keyAt(index);
        keys[index] = key;
        const sum = groups.get(key) || new THREE.Vector3();
        groups.set(key, sum.add(normal));
      });
    }
    const normals = new Float32Array(position.count * 3);
    keys.forEach((key, index) => {
      const normal = (groups.get(key) || new THREE.Vector3(0, 1, 0)).normalize();
      normals[index * 3] = normal.x;
      normals[index * 3 + 1] = normal.y;
      normals[index * 3 + 2] = normal.z;
    });
    geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
  };

  const prepareModel = (group, poseId, cfg) => {
    const patches = [];
    group.name = `guardian-pose:${poseId}`;
    group.visible = false;
    group.traverse(object => {
      if (!object.isMesh) return;
      smoothNonIndexedNormals(object.geometry);
      object.frustumCulled = false;
      object.castShadow = false;
      object.receiveShadow = false;
      const source = Array.isArray(object.material) ? object.material : [object.material];
      const materials = source.filter(Boolean).map(material => {
        const clone = material.clone();
        if ('metalness' in clone) clone.metalness = 0;
        if ('roughness' in clone) clone.roughness = 0.38;
        clone.userData.guardianBaseTransparent = clone.transparent === true;
        clone.userData.guardianBaseOpacity = Number.isFinite(clone.opacity) ? clone.opacity : 1;
        patches.push(patchGuardianMaterial(clone, undefined, notifyFailure));
        return clone;
      });
      object.material = Array.isArray(object.material) ? materials : materials[0];
    });
    scene.add(group);
    const record = { poseId, cfg, group, patches, transitionAt: 0 };
    models.set(poseId, record);
    modelRecords.add(record);
    return record;
  };

  const loadPose = poseId => {
    if (models.has(poseId)) return Promise.resolve(models.get(poseId));
    if (modelLoads.has(poseId)) return modelLoads.get(poseId);
    const pending = (async () => {
      configuration ||= await configurationPromise;
      const cfg = configuration.poseConfig.poses?.[poseId];
      if (!cfg) throw new Error(`Unknown guardian pose: ${poseId}`);
      const gltf = await new GLTFLoader().loadAsync(assetUrl(cfg.file));
      let meshCount = 0;
      gltf.scene.traverse(object => { if (object.isMesh) meshCount += 1; });
      if (!meshCount) throw new Error(`No mesh found in guardian pose ${poseId}`);
      return prepareModel(gltf.scene, poseId, cfg);
    })().finally(() => modelLoads.delete(poseId));
    modelLoads.set(poseId, pending);
    return pending;
  };

  const setPose = async (input, poseOptions = {}) => {
    const token = ++poseToken;
    const poseId = resolvePoseId(input);
    let next;
    try {
      next = await loadPose(poseId);
    } catch (error) {
      notifyFailure(error);
      return getState();
    }
    if (state.disposed || token !== poseToken) return getState();
    modelRecords.forEach(record => { record.group.visible = record === next; });
    activeRecord = next;
    activeRecord.transitionAt = poseOptions.immediate || state.reducedMotion ? 0 : performance.now();
    state.poseId = poseId;
    updateMeta(poseId);
    const detail = { pose: poseId, index: POSE_ORDER.indexOf(poseId), name: next.cfg.name, source: poseOptions.source || 'api' };
    options.onPoseChange?.(detail);
    window.dispatchEvent(new CustomEvent('fitness-ledger-pet:pose-change', { detail }));
    return getState();
  };

  const setPointer = ({ x = 0, y = 0 } = {}) => {
    state.pointerX = clamp(Number(x) || 0, -1, 1);
    state.pointerY = clamp(Number(y) || 0, -1, 1);
  };

  const setFollowTarget = ({ x = 0, y = 0 } = {}) => {
    state.targetX = clamp(Number(x) || 0, -1, 1);
    state.targetY = clamp(Number(y) || 0, -1, 1);
  };

  const setViewRotation = ({ x = 0, y = 0 } = {}) => {
    state.viewRotation.x = clamp(Number(x) || 0, -1, 1);
    state.viewRotation.y = clamp(Number(y) || 0, -1, 1);
  };

  const setCameraPreset = async presetName => {
    configuration ||= await configurationPromise;
    const preset = configuration.cameraConfig.presets?.[presetName] || configuration.cameraConfig.presets.idle;
    state.cameraPreset = configuration.cameraConfig.presets?.[presetName] ? presetName : 'idle';
    if (petMode) {
      // The floating pet must keep the complete figure inside its transparent frame.
      // Page presets are intentionally close-up; applying their zoom/distance here
      // crops the head and feet on movement/body routes.
      state.targetZoom = Math.min(Number(preset.zoom) || 1, 1.02);
      cameraGoal.set(0, 0.5, Math.max(Number(preset.camera?.[2]) || 2.18, 2.45));
      lookGoal.set(0, 0.5, 0);
    } else {
      state.targetZoom = Number(preset.zoom) || 1;
      cameraGoal.fromArray(preset.camera || [0, 0.5, 2.18]);
      lookGoal.fromArray(preset.target || [0, 0.5, 0]);
    }
    if (state.reducedMotion) {
      state.zoom = state.targetZoom;
      camera.position.copy(cameraGoal);
      cameraLookAt.copy(lookGoal);
    }
    return getState();
  };

  const resetView = () => {
    state.offsetX = 0;
    state.offsetY = 0;
    state.yawOffset = 0;
    setViewRotation({ x: 0, y: 0 });
    setFollowTarget({ x: 0, y: 0 });
    return setCameraPreset('idle');
  };

  const snapshot = () => cloneState({
    poseId: state.poseId,
    cameraPreset: state.cameraPreset,
    pointerX: state.pointerX,
    pointerY: state.pointerY,
    targetX: state.targetX,
    targetY: state.targetY,
    aimX: state.aimX,
    aimY: state.aimY,
    zoom: state.zoom,
    targetZoom: state.targetZoom,
    offsetX: state.offsetX,
    offsetY: state.offsetY,
    yawOffset: state.yawOffset,
    viewRotation: state.viewRotation,
    reducedMotion: state.reducedMotion
  });

  const restore = async saved => {
    if (!saved || state.disposed) return;
    if (saved.poseId) await setPose(saved.poseId, { source: 'restore', immediate: state.reducedMotion });
    Object.assign(state, {
      pointerX: saved.pointerX ?? 0,
      pointerY: saved.pointerY ?? 0,
      targetX: saved.targetX ?? 0,
      targetY: saved.targetY ?? 0,
      aimX: saved.aimX ?? 0,
      aimY: saved.aimY ?? 0,
      zoom: saved.zoom ?? 1,
      targetZoom: saved.targetZoom ?? saved.zoom ?? 1,
      offsetX: saved.offsetX ?? 0,
      offsetY: saved.offsetY ?? 0,
      yawOffset: saved.yawOffset ?? 0
    });
    state.viewRotation = { x: saved.viewRotation?.x ?? 0, y: saved.viewRotation?.y ?? 0 };
    await setCameraPreset(saved.cameraPreset || 'idle');
  };

  const presentation = createGuardianPresentationManager({
    snapshot,
    restore,
    setPose,
    setCameraPreset,
    showOverlay: options.showOverlay,
    hideOverlay: options.hideOverlay,
    playEffect: options.playEffect,
    stopEffect: options.stopEffect
  });

  const setPageDefault = async ({ poseId = 'standing', cameraPreset = 'idle' } = {}) => {
    const desired = { ...snapshot(), poseId: resolvePoseId(poseId), cameraPreset };
    presentation.setPageDefault(desired);
    if (!presentation.getState().active) await restore(desired);
    return getState();
  };

  const setReducedMotion = value => {
    state.reducedMotion = Boolean(value);
    if (state.reducedMotion) {
      state.aimX = state.targetX;
      state.aimY = state.targetY;
      state.zoom = state.targetZoom;
    }
  };

  function getState() {
    return { renderer: snapshot(), presentation: presentation?.getState?.() || null };
  }

  const updateMeta = poseId => {
    const cfg = configuration?.poseConfig.poses?.[poseId] || {};
    document.querySelector('[data-guardian-pose-name]')?.replaceChildren(document.createTextNode(cfg.name || poseId));
    document.querySelector('[data-guardian-pose-copy]')?.replaceChildren(document.createTextNode(POSE_COPY[poseId] || cfg.subtitle || ''));
    const indexNode = document.querySelector('[data-guardian-pose-index]');
    if (indexNode) indexNode.textContent = `${String(POSE_ORDER.indexOf(poseId) + 1).padStart(2, '0')} / ${String(POSE_ORDER.length).padStart(2, '0')}`;
  };

  const renderPoseButtons = async () => {
    configuration ||= await configurationPromise;
    const list = document.querySelector('[data-guardian-pose-list]');
    if (!list) return;
    list.innerHTML = POSE_ORDER.map((poseId, index) => `<button class="guardian-pose-button" type="button" data-guardian-pose="${poseId}"><span>${String(index + 1).padStart(2, '0')} / POSE</span><strong>${configuration.poseConfig.poses[poseId].name}</strong></button>`).join('');
  };

  const resize = () => {
    const width = Math.max(1, canvas.clientWidth || 360);
    const height = Math.max(1, canvas.clientHeight || 360);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };

  const tick = now => {
    if (state.disposed || !activeRecord) return;
    modelRecords.forEach(record => { if (record !== activeRecord && record.group.visible) record.group.visible = false; });
    const cfg = activeRecord.cfg;
    const horizontalFollow = state.reducedMotion ? 0.16 : 0.085;
    const verticalFollow = state.reducedMotion ? 0.16 : 0.075;
    state.aimX += (state.targetX - state.aimX) * horizontalFollow;
    state.aimY += (state.targetY - state.aimY) * verticalFollow;
    state.zoom += (state.targetZoom - state.zoom) * (state.reducedMotion ? 1 : 0.08);
    const motionScale = state.reducedMotion ? 0.25 : 1;
    const wholeYaw = degreesToRadians(state.aimX * state.response * cfg.wholeYaw * motionScale);
    const upperYaw = degreesToRadians(state.aimX * state.response * cfg.upperYaw * motionScale);
    const headYaw = degreesToRadians(state.aimX * state.response * cfg.headYaw * motionScale);
    const upperPitch = degreesToRadians(-state.aimY * state.response * cfg.upperPitch * motionScale);
    const headPitch = degreesToRadians(-state.aimY * state.response * cfg.headPitch * motionScale);
    const pointerLoad = Math.min(1, Math.hypot(state.aimX, state.aimY));
    const breathLevel = state.reducedMotion ? 0 : clamp(1 - pointerLoad * 0.18, 0.72, 1);

    const transition = activeRecord.transitionAt ? clamp((now - activeRecord.transitionAt) / 220, 0, 1) : 1;
    const eased = 1 - Math.pow(1 - transition, 3);
    if (transition >= 1) activeRecord.transitionAt = 0;
    activeRecord.group.position.set(state.offsetX, cfg.baseY + state.offsetY + (1 - eased) * 0.025, 0);
    activeRecord.group.scale.setScalar(cfg.baseScale * presentationScale * state.zoom * (0.965 + eased * 0.035));
    activeRecord.group.rotation.y = degreesToRadians(state.yawOffset + state.viewRotation.x * 18) + wholeYaw;
    for (const patch of activeRecord.patches) {
      patch.set({
        baseYaw: degreesToRadians(cfg.baseYaw),
        upperYaw,
        headYaw,
        upperPitch,
        headPitch,
        timeSeconds: state.reducedMotion ? 0 : now / 1000,
        breath: breathLevel,
        tension: state.reducedMotion ? 0.12 : 0.62,
        rigNorm: cfg.rigNorm
      });
    }

    adjustedCameraGoal.copy(cameraGoal).setY(cameraGoal.y - state.viewRotation.y * 0.12);
    adjustedLookGoal.copy(lookGoal).setY(lookGoal.y - state.viewRotation.y * 0.08);
    camera.position.lerp(adjustedCameraGoal, state.reducedMotion ? 1 : 0.08);
    cameraLookAt.lerp(adjustedLookGoal, state.reducedMotion ? 1 : 0.08);
    if (controls) controls.target.copy(cameraLookAt);
    else camera.lookAt(cameraLookAt);
    keyLight.position.x = keyLightHome.x + state.pointerX * 0.45;
    keyLight.position.y = keyLightHome.y - state.pointerY * 0.22;
    if (ambientMotes) ambientMotes.rotation.y = Math.sin(now / 5200) * 0.08;
  };

  const animate = now => {
    if (state.disposed) return;
    frame = requestAnimationFrame(animate);
    if (!visible || state.failed) return;
    tick(now);
    controls?.update();
    try {
      renderer.render(scene, camera);
    } catch (error) {
      notifyFailure(error);
    }
  };

  const onCanvasPointerMove = event => {
    if (petMode) return;
    const rect = canvas.getBoundingClientRect();
    const pointer = { x: ((event.clientX - rect.left) / Math.max(rect.width, 1)) * 2 - 1, y: -(((event.clientY - rect.top) / Math.max(rect.height, 1)) * 2 - 1) };
    setPointer(pointer);
    setFollowTarget(pointer);
  };
  const onCanvasClick = () => {
    const index = POSE_ORDER.indexOf(state.poseId);
    void setPose(POSE_ORDER[(index + 1) % POSE_ORDER.length], { source: 'canvas-click' });
  };
  const onPoseListClick = event => {
    const button = event.target.closest('[data-guardian-pose]');
    if (button) void setPose(button.dataset.guardianPose, { source: 'button' });
  };
  const onMessage = event => {
    if (event.data?.type === 'fitness-ledger-pet-pointer') setPointer(event.data);
    if (event.data?.type === 'fitness-ledger-pet-set-pose') void setPose(event.data.pose ?? event.data.index, { source: 'postMessage', immediate: event.data.immediate === true });
  };
  const onPoseCommand = event => void setPose(event.detail?.pose ?? event.detail?.index, { source: event.detail?.source || 'custom-event', immediate: event.detail?.immediate === true });
  const onVisibility = () => { visible = document.visibilityState !== 'hidden'; };
  const onMotionPreference = event => setReducedMotion(event.matches);
  const intersectionObserver = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => { visible = document.visibilityState !== 'hidden' && entries.some(entry => entry.isIntersecting); }) : null;

  canvas.addEventListener('pointermove', onCanvasPointerMove, { passive: true });
  canvas.addEventListener('click', onCanvasClick);
  document.querySelector('[data-guardian-pose-list]')?.addEventListener('click', onPoseListClick);
  window.addEventListener('resize', resize);
  window.addEventListener('message', onMessage);
  window.addEventListener('fitness-ledger-pet:set-pose', onPoseCommand);
  document.addEventListener('visibilitychange', onVisibility);
  media?.addEventListener?.('change', onMotionPreference);
  intersectionObserver?.observe(canvas);
  resize();
  animate(0);

  const readyPromise = (async () => {
    try {
      configuration = await configurationPromise;
      presentation.setPriorities?.(configuration.intentConfig?.priorities || {});
      await renderPoseButtons();
      await setCameraPreset('idle');
      await setPose(options.initialPose || 'standing', { source: 'ready', immediate: true });
      if (state.failed) return;
      state.ready = true;
      canvas.hidden = false;
      readyNotified = true;
      const catalog = POSE_ORDER.map((id, index) => ({ id, index, name: configuration.poseConfig.poses[id].name }));
      options.onReady?.({ source: 'lowpoly-static-shader-v6.2', assets: 1, poses: POSE_ORDER.length, fallback: false, poseCatalog: catalog });
      await Promise.allSettled(POSE_ORDER.filter(id => id !== state.poseId).map(loadPose));
    } catch (error) {
      notifyFailure(error);
    }
  })();

  const dispose = () => {
    if (state.disposed) return;
    state.disposed = true;
    presentation.dispose();
    cancelAnimationFrame(frame);
    intersectionObserver?.disconnect();
    window.removeEventListener('resize', resize);
    window.removeEventListener('message', onMessage);
    window.removeEventListener('fitness-ledger-pet:set-pose', onPoseCommand);
    document.removeEventListener('visibilitychange', onVisibility);
    media?.removeEventListener?.('change', onMotionPreference);
    canvas.removeEventListener('pointermove', onCanvasPointerMove);
    canvas.removeEventListener('click', onCanvasClick);
    document.querySelector('[data-guardian-pose-list]')?.removeEventListener('click', onPoseListClick);
    controls?.dispose();
    const geometries = new Set();
    const textures = new Set();
    modelRecords.forEach(record => {
      record.patches.forEach(patch => patch.dispose());
      record.group.traverse(object => {
        if (!object.isMesh) return;
        if (object.geometry) geometries.add(object.geometry);
        const materials = Array.isArray(object.material) ? object.material : [object.material];
        materials.filter(Boolean).forEach(material => {
          Object.values(material).forEach(value => { if (value?.isTexture) textures.add(value); });
          material.dispose?.();
        });
      });
    });
    geometries.forEach(geometry => geometry.dispose?.());
    textures.forEach(texture => texture.dispose?.());
    ambientMotes?.geometry?.dispose?.();
    ambientMotes?.material?.dispose?.();
    models.clear();
    modelLoads.clear();
    modelRecords.clear();
    renderer.dispose();
    scene.clear();
    guardianControllerRegistry.delete(api);
    if (window.__fitnessLedgerGuardianPet === api) window.__fitnessLedgerGuardianPet = null;
  };

  const api = {
    ready: readyPromise,
    loadPose,
    setPose,
    setIntent: request => presentation.apply(request),
    finishIntent: (id, reason) => presentation.finish(id, reason),
    clearIntent: reason => presentation.clear(reason),
    setPageDefault,
    setPointer,
    setFollowTarget,
    setViewRotation,
    setCameraPreset,
    resetView,
    getState,
    getPoseCatalog: () => POSE_ORDER.map((id, index) => ({ id, index, name: configuration?.poseConfig.poses?.[id]?.name || id })),
    getDiagnostics: () => ({
      ...getState(),
      loadedAssets: [...models.keys()],
      trackedRoots: modelRecords.size,
      scenePoseRoots: scene.children.filter(child => child.name?.startsWith('guardian-pose:')).length,
      visibleRoots: [...modelRecords].filter(record => record.group.visible).length,
      inFlightLoads: modelLoads.size,
      readyNotified,
      render: { ...renderer.info.render }
    }),
    setReducedMotion,
    previousPose: poseOptions => setPose(POSE_ORDER[(POSE_ORDER.indexOf(state.poseId) - 1 + POSE_ORDER.length) % POSE_ORDER.length], { ...poseOptions, source: poseOptions?.source || 'previous' }),
    nextPose: poseOptions => setPose(POSE_ORDER[(POSE_ORDER.indexOf(state.poseId) + 1) % POSE_ORDER.length], { ...poseOptions, source: poseOptions?.source || 'next' }),
    dispose
  };
  guardianControllerRegistry.add(api);
  return api;
}
