import * as THREE from './three.module.min.js?v=20260806-v21';
import { GLTFLoader } from './GLTFLoader.js?v=20260806-v21';
import { OrbitControls } from './OrbitControls.js?v=20260806-v21';

const poseIds = [
  'front-standing',
  'front-double-biceps',
  'side-chest',
  'rear-double-biceps',
  'rear-lat-spread',
  'most-muscular',
  'open-hand-crab'
];

const poseFiles = [
  'lowpoly-front-standing.glb',
  'lowpoly-front-double-biceps.glb',
  'lowpoly-side-chest.glb',
  'lowpoly-rear-double-biceps.glb',
  'lowpoly-rear-lat-spread.glb',
  'lowpoly-most-muscular.glb',
  'lowpoly-open-hand-crab.glb'
];

export const GUARDIAN_POSE_CATALOG = poseIds.map((id, index) => ({ id, index }));

const poseCopy = [
  'A neutral starting stance for the home surface.',
  'Open the front line and hold the first clear checkpoint.',
  'Turn toward the light and make control the starting point for the next record.',
  'Face the rear chain instead of measuring progress only from the front.',
  'Treat the back as a wide local archive surface.',
  'Short, concentrated, and clear: one tool call for one job.',
  'Open the hands and let the pose carry a little more energy.'
];

const poseNames = [
  'Front standing',
  'Front double biceps',
  'Side chest',
  'Rear double biceps',
  'Rear lat spread',
  'Most muscular',
  'Open-hand crab'
];

// A few source exports use a different forward axis. Keep the correction in
// the catalog so new GLBs do not require changes to the renderer.
const poseRotations = [
  Math.PI / 2,
  0,
  0,
  0,
  0,
  Math.PI / 2,
  Math.PI / 2
];

const poseAliases = {
  'front-lat-spread': 'front-standing',
  'side-triceps': 'side-chest',
  'abs-thighs': 'front-standing',
  'crab-open': 'open-hand-crab'
};

const resolvePoseIndex = (input, allowedIndices = poseIds.map((_, index) => index)) => {
  if (typeof input === 'string') {
    const byId = poseIds.indexOf(poseAliases[input] || input);
    if (byId >= 0) return allowedIndices.includes(byId) ? byId : allowedIndices[0];
    const byName = poseNames.findIndex(name => name.toLowerCase() === input.toLowerCase());
    if (byName >= 0) return allowedIndices.includes(byName) ? byName : allowedIndices[0];
  }
  const numeric = Number(input);
  if (!Number.isFinite(numeric)) return allowedIndices[0];
  const rounded = Math.round(numeric);
  if (allowedIndices.includes(rounded)) return rounded;
  const slot = ((rounded % allowedIndices.length) + allowedIndices.length) % allowedIndices.length;
  return allowedIndices[slot];
};

const assetUrl = file => new URL(`./assets/lowpoly/${file}`, import.meta.url).href;

export function mountGuardianPet(canvas, options = {}) {
  const params = new URLSearchParams(location.search);
  const petMode = params.get('embed') === 'pet' || options.petMode === true;
  const poseSequence = poseIds.map((_, index) => index);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(24, 1, 0.1, 100);
  camera.position.set(8.6, 0.26, 0.08);
  camera.lookAt(0, 0.04, 0);

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

  const controls = petMode ? null : new OrbitControls(camera, canvas);
  if (controls) {
    controls.enableDamping = true;
    controls.enablePan = false;
    controls.minDistance = 4.2;
    controls.maxDistance = 11;
    controls.target.set(0, 0.04, 0);
  }

  const cursor = { x: 0, y: 0, energy: 0 };
  const models = new Map();
  let activePose = poseSequence.includes(0) ? 0 : poseSequence[0];
  let activeRoot = null;
  let frame = 0;
  let disposed = false;
  let readyNotified = false;

  const rootForPose = index => models.get(poseFiles[index]);
  const uniqueFiles = [...new Set(poseSequence.map(index => poseFiles[index]))];
  const poseIndexForFile = file => poseFiles.indexOf(file);
  const setOpacity = (root, value) => {
    if (!root) return;
    root.visible = value > 0.001;
    root.traverse(node => {
      if (!node.isMesh) return;
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.filter(Boolean).forEach(material => {
        material.userData.guardianBaseOpacity ??= Number.isFinite(material.opacity) ? material.opacity : 1;
        material.transparent = value < 0.999 || material.userData.guardianBaseTransparent === true;
        material.opacity = material.userData.guardianBaseOpacity * value;
        material.depthWrite = value > 0.96;
        material.needsUpdate = true;
      });
    });
  };

  const smoothNonIndexedNormals = geometry => {
    const position = geometry?.getAttribute?.('position');
    if (!position || geometry.index || position.count < 3 || position.count % 3 !== 0) return;
    const groups = new Map();
    const keys = new Array(position.count);
    const quantize = value => Math.round(value * 100000);
    const keyAt = index => `${quantize(position.getX(index))}:${quantize(position.getY(index))}:${quantize(position.getZ(index))}`;
    for (let offset = 0; offset < position.count; offset += 3) {
      const ax = position.getX(offset);
      const ay = position.getY(offset);
      const az = position.getZ(offset);
      const bx = position.getX(offset + 1);
      const by = position.getY(offset + 1);
      const bz = position.getZ(offset + 1);
      const cx = position.getX(offset + 2);
      const cy = position.getY(offset + 2);
      const cz = position.getZ(offset + 2);
      const abx = bx - ax;
      const aby = by - ay;
      const abz = bz - az;
      const acx = cx - ax;
      const acy = cy - ay;
      const acz = cz - az;
      const nx = aby * acz - abz * acy;
      const ny = abz * acx - abx * acz;
      const nz = abx * acy - aby * acx;
      [offset, offset + 1, offset + 2].forEach(index => {
        const key = keyAt(index);
        keys[index] = key;
        const sum = groups.get(key) || [0, 0, 0];
        sum[0] += nx;
        sum[1] += ny;
        sum[2] += nz;
        groups.set(key, sum);
      });
    }
    const normals = new Float32Array(position.count * 3);
    keys.forEach((key, index) => {
      const sum = groups.get(key) || [0, 1, 0];
      const length = Math.hypot(sum[0], sum[1], sum[2]) || 1;
      normals[index * 3] = sum[0] / length;
      normals[index * 3 + 1] = sum[1] / length;
      normals[index * 3 + 2] = sum[2] / length;
    });
    geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
  };

  const normalizeMaterial = material => {
    if (!material) return;
    material.metalness = 0;
    material.roughness = 0.5;
    material.color?.setRGB?.(0.8, 0.8, 0.8);
    if ('specularIntensity' in material) material.specularIntensity = 1;
    material.needsUpdate = true;
  };

  const prepareModel = (root, poseIndex) => {
    root.rotation.y = poseRotations[poseIndex] || 0;
    root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(root);
    const size = box.getSize(new THREE.Vector3());
    const scale = 3.45 / Math.max(size.y, size.x, size.z, 0.0001);
    root.scale.setScalar(scale);
    root.updateMatrixWorld(true);
    const scaledBox = new THREE.Box3().setFromObject(root);
    const center = scaledBox.getCenter(new THREE.Vector3());
    root.position.sub(center);
    root.position.y += 0.08;
    root.userData.guardianBaseY = root.position.y;
    root.userData.guardianBaseScale = scale;
    root.userData.guardianBaseRotationY = poseRotations[poseIndex] || 0;
    root.traverse(node => {
       if (!node.isMesh) return;
       node.frustumCulled = true;
       node.castShadow = false;
       node.receiveShadow = false;
       smoothNonIndexedNormals(node.geometry);
       const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.filter(Boolean).forEach(material => {
        normalizeMaterial(material);
        material.userData.guardianBaseTransparent = material.transparent === true;
        material.userData.guardianBaseOpacity ??= Number.isFinite(material.opacity) ? material.opacity : 1;
      });
    });
    setOpacity(root, 0);
    scene.add(root);
  };

  const loadModel = (file, poseIndex) => new Promise((resolve, reject) => {
    new GLTFLoader().load(assetUrl(file), gltf => {
      if (disposed) return;
      try {
        const meshCount = [];
        gltf.scene.traverse(node => { if (node.isMesh) meshCount.push(node); });
        if (!meshCount.length) throw new Error(`No mesh found in ${file}`);
        prepareModel(gltf.scene, poseIndex);
        models.set(file, gltf.scene);
        resolve(gltf.scene);
      } catch (error) {
        console.error(`[Guardian] low-poly asset prepare failed: ${file}`, error);
        reject(error);
      }
    }, undefined, error => {
      console.error(`[Guardian] low-poly asset failed: ${file}`, error);
      const status = document.querySelector('[data-guardian-status]');
      if (status) status.textContent = `LOW-POLY ERROR · ${file.replace('lowpoly-', '').replace('.glb', '')}`;
      reject(error);
    });
  });

  const emitPoseChange = (index, source = 'api') => {
    const detail = { pose: poseIds[index], index, name: poseNames[index], source };
    options.onPoseChange?.(detail);
    window.dispatchEvent(new CustomEvent('fitness-ledger-pet:pose-change', { detail }));
  };

  const updateMeta = index => {
    const nameNode = document.querySelector('[data-guardian-pose-name]');
    const copyNode = document.querySelector('[data-guardian-pose-copy]');
    const indexNode = document.querySelector('[data-guardian-pose-index]');
    const status = document.querySelector('[data-guardian-status]');
    if (nameNode) nameNode.textContent = poseNames[index];
    if (copyNode) copyNode.textContent = `${poseCopy[index]} · STATIC TRANSITION`;
    if (indexNode) indexNode.textContent = `${String(Math.max(0, poseSequence.indexOf(index)) + 1).padStart(2, '0')} / ${String(poseSequence.length).padStart(2, '0')}`;
    document.querySelectorAll('[data-guardian-pose]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.guardianPose) === index)));
    if (status && readyNotified) status.textContent = `LOW-POLY STATIC PET · ${String(models.size).padStart(2, '0')} ASSETS`;
  };

  const hideOtherRoots = (...keep) => {
    models.forEach(root => {
      if (!keep.includes(root)) setOpacity(root, 0);
    });
  };

  const setPose = (input, immediateOrOptions = false, source = 'api') => {
    const optionsObject = typeof immediateOrOptions === 'object' ? immediateOrOptions : null;
    const changeSource = optionsObject?.source || source;
    activePose = resolvePoseIndex(input, poseSequence);
    updateMeta(activePose);
    const target = rootForPose(activePose);
    if (!target) return;
    if (target === activeRoot) {
      hideOtherRoots(target);
      setOpacity(target, 1);
      return;
    }
    activeRoot = target;
    hideOtherRoots(activeRoot);
    setOpacity(activeRoot, 1);
    emitPoseChange(activePose, changeSource);
  };

  const renderPoseButtons = () => {
    const list = document.querySelector('[data-guardian-pose-list]');
    if (!list) return;
    list.innerHTML = poseSequence.map((index, slot) => `<button class="guardian-pose-button" type="button" data-guardian-pose="${index}" aria-pressed="${index === activePose}"><span>${String(slot + 1).padStart(2, '0')} / POSE</span><strong>${poseNames[index]}</strong></button>`).join('');
    list.addEventListener('click', event => {
      const button = event.target.closest('[data-guardian-pose]');
      if (button) setPose(Number(button.dataset.guardianPose), { source: 'button' });
    });
  };

  const onMessage = event => {
    if (event.data?.type === 'fitness-ledger-pet-pointer') setPointer(event.data);
    if (event.data?.type === 'fitness-ledger-pet-set-pose') setPose(event.data.pose ?? event.data.index, { immediate: event.data.immediate === true, source: 'postMessage' });
  };
  window.addEventListener('message', onMessage);

  const onPoseCommand = event => setPose(event.detail?.pose ?? event.detail?.index, { immediate: event.detail?.immediate === true, source: event.detail?.source || 'custom-event' });
  window.addEventListener('fitness-ledger-pet:set-pose', onPoseCommand);

  const setPointer = ({ x = 0, y = 0, energy = 0 } = {}) => {
    cursor.x = THREE.MathUtils.clamp(Number(x) || 0, -1, 1);
    cursor.y = THREE.MathUtils.clamp(Number(y) || 0, -1, 1);
    cursor.energy = THREE.MathUtils.clamp(Number(energy) || 0, 0, 1);
  };

  const onCanvasPointerMove = event => {
    if (petMode) return;
    const rect = canvas.getBoundingClientRect();
    setPointer({ x: ((event.clientX - rect.left) / Math.max(rect.width, 1)) * 2 - 1, y: -(((event.clientY - rect.top) / Math.max(rect.height, 1)) * 2 - 1), energy: 0.5 });
  };
  const onCanvasClick = () => {
    const slot = poseSequence.indexOf(activePose);
    setPose(poseSequence[(slot + 1) % poseSequence.length], { source: 'canvas-click' });
  };
  canvas.addEventListener('pointermove', onCanvasPointerMove, { passive: true });
  canvas.addEventListener('click', onCanvasClick);

  const resize = () => {
    const width = Math.max(1, canvas.clientWidth || 360);
    const height = Math.max(1, canvas.clientHeight || 360);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };

  const animate = now => {
    if (disposed) return;
    frame = requestAnimationFrame(animate);
    const breath = Math.sin(now / 1200) * 0.006;
    const targetYawOffset = cursor.x * 0.12 + Math.sin(now / 2600) * 0.014;
    const targetPitch = -cursor.y * 0.025;
    models.forEach(root => {
      if (!root.visible) return;
      const targetYaw = root.userData.guardianBaseRotationY + targetYawOffset;
      root.rotation.y += (targetYaw - root.rotation.y) * 0.07;
      root.rotation.x += (targetPitch - root.rotation.x) * 0.06;
      root.position.y = root.userData.guardianBaseY + breath;
      const pulse = 1 + Math.sin(now / 1200) * 0.0006;
      root.scale.setScalar(root.userData.guardianBaseScale * pulse);
    });
    controls?.update();
    renderer.render(scene, camera);
  };

  const loadAll = async () => {
    const status = document.querySelector('[data-guardian-status]');
    status && (status.textContent = `LOADING LOW-POLY · 00 / ${String(uniqueFiles.length).padStart(2, '0')}`);
    const activeFile = poseFiles[activePose];
    const activeResult = (await Promise.allSettled([loadModel(activeFile, activePose)]))[0];
    if (activeResult.status === 'fulfilled') {
      readyNotified = true;
      options.onReady?.({ source: 'lowpoly-static', assets: 1, poses: poseSequence.length, fallback: false, poseCatalog: poseSequence.map(index => ({ ...GUARDIAN_POSE_CATALOG[index], name: poseNames[index] })) });
      setPose(activePose, { immediate: true, source: 'ready' });
    }
    status && (status.textContent = `LOADING LOW-POLY · ${String(models.size).padStart(2, '0')} / ${String(uniqueFiles.length).padStart(2, '0')}`);
    const remainingFiles = uniqueFiles.filter(file => file !== activeFile);
    await Promise.allSettled(remainingFiles.map(async file => {
      await loadModel(file, poseIndexForFile(file)).catch(() => undefined);
      status && (status.textContent = `LOADING LOW-POLY · ${String(Math.min(uniqueFiles.length, models.size)).padStart(2, '0')} / ${String(uniqueFiles.length).padStart(2, '0')}`);
    }));
    const loaded = models.size;
    if (loaded === 0) {
      status && (status.textContent = 'LOW-POLY PET LOAD ERROR');
      options.onError?.(new Error('No low-poly guardian assets could be loaded'));
      return;
    }
    if (!readyNotified) {
      const fallbackPose = poseSequence.find(index => models.has(poseFiles[index]));
      readyNotified = true;
      options.onReady?.({ source: 'lowpoly-static', assets: loaded, poses: poseSequence.length, fallback: false, poseCatalog: poseSequence.map(index => ({ ...GUARDIAN_POSE_CATALOG[index], name: poseNames[index] })) });
      setPose(fallbackPose ?? poseSequence[0], { immediate: true, source: 'ready-fallback' });
    }
    status && (status.textContent = `LOW-POLY STATIC PET · ${String(loaded).padStart(2, '0')} ASSETS`);
  };

  renderPoseButtons();
  updateMeta(activePose);
  resize();
  window.addEventListener('resize', resize);
  loadAll();
  animate(0);

  return {
    setPointer,
    setPose,
    previousPose: (options = {}) => {
      const slot = poseSequence.indexOf(activePose);
      return setPose(poseSequence[(slot - 1 + poseSequence.length) % poseSequence.length], { source: options.source || 'previous' });
    },
    nextPose: (options = {}) => {
      const slot = poseSequence.indexOf(activePose);
      return setPose(poseSequence[(slot + 1) % poseSequence.length], { source: options.source || 'next' });
    },
    getPoseCatalog: () => poseSequence.map(index => ({ ...GUARDIAN_POSE_CATALOG[index], name: poseNames[index] })),
    getDiagnostics: () => {
      const box = activeRoot ? new THREE.Box3().setFromObject(activeRoot) : null;
      const meshes = [];
      activeRoot?.traverse(node => {
        if (!node.isMesh) return;
        const materials = (Array.isArray(node.material) ? node.material : [node.material]).filter(Boolean);
        meshes.push({
          visible: node.visible,
          frustumCulled: node.frustumCulled,
          vertices: node.geometry?.getAttribute?.('position')?.count || 0,
          materials: materials.map(material => ({
            type: material.type,
            visible: material.visible,
            opacity: material.opacity,
            transparent: material.transparent,
            depthWrite: material.depthWrite,
            hasMap: Boolean(material.map)
          }))
        });
      });
      return {
        mode: 'lowpoly-static',
        activePose,
        activePoseId: poseIds[activePose],
        loadedAssets: [...models.keys()],
        visibleRoots: [...models.values()].filter(root => root.visible).length,
        visibleRootFiles: [...models.entries()].filter(([, root]) => root.visible).map(([file]) => file),
        camera: {
          position: camera.position.toArray(),
          rotation: camera.rotation.toArray(),
          aspect: camera.aspect,
          fov: camera.fov,
          near: camera.near,
          far: camera.far
        },
        activeRoot: activeRoot ? {
          visible: activeRoot.visible,
          position: activeRoot.position.toArray(),
          rotation: activeRoot.rotation.toArray(),
          scale: activeRoot.scale.toArray(),
          boxMin: box.min.toArray(),
          boxMax: box.max.toArray(),
          meshes
        } : null,
        render: { ...renderer.info.render }
      };
    },
    dispose() {
      disposed = true;
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', resize);
      window.removeEventListener('message', onMessage);
      window.removeEventListener('fitness-ledger-pet:set-pose', onPoseCommand);
      canvas.removeEventListener('pointermove', onCanvasPointerMove);
      canvas.removeEventListener('click', onCanvasClick);
      controls?.dispose();
      models.forEach(root => {
        root.traverse(node => {
          if (!node.isMesh) return;
          node.geometry?.dispose?.();
          const materials = Array.isArray(node.material) ? node.material : [node.material];
          materials.filter(Boolean).forEach(material => {
            Object.values(material).forEach(value => value?.isTexture && value.dispose?.());
            material.dispose?.();
          });
        });
      });
      renderer.dispose();
      scene.clear();
    }
  };
}

// The standalone Motion Lab page imports this module directly. The embedded
// mouse pet calls the exported mount function itself, so this remains a
// no-op there because its canvas does not use the standalone data attribute.
const standaloneCanvas = document.querySelector('[data-guardian-canvas]:not([data-guardian-page])');
if (standaloneCanvas) mountGuardianPet(standaloneCanvas);
