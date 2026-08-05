import * as THREE from './three.module.min.js';
import { GLTFLoader } from './GLTFLoader.js';
import { OrbitControls } from './OrbitControls.js';

const poses = [
  { name: 'Front lat spread', copy: 'Open the shoulders and back width like a training route unfolding in front of you.' },
  { name: 'Front double biceps', copy: 'A symmetrical hold for the quiet confirmation after a completed session.' },
  { name: 'Side chest', copy: 'Turn toward the light and make control the starting point for the next record.' },
  { name: 'Rear double biceps', copy: 'Face the rear chain instead of measuring progress only from the front.' },
  { name: 'Rear lat spread', copy: 'Treat the back as a wide local archive surface.' },
  { name: 'Side triceps', copy: 'Keep the line clean and let the pose stay focused.' },
  { name: 'Most muscular', copy: 'Short, concentrated, and clear: one tool call for one job.' },
  { name: 'Abs & thighs', copy: 'A final check on the core and lower body before the work settles.' }
];

const root = document.querySelector('[data-guardian-app]');
const canvas = document.querySelector('[data-guardian-canvas]');
const status = document.querySelector('[data-guardian-status]');
const nameNode = document.querySelector('[data-guardian-pose-name]');
const copyNode = document.querySelector('[data-guardian-pose-copy]');
const indexNode = document.querySelector('[data-guardian-pose-index]');
const list = document.querySelector('[data-guardian-pose-list]');
const petMode = new URLSearchParams(location.search).get('embed') === 'pet';

let activePose = 1;
let modelRoot;
let bones = new Map();
let baseTransforms = new Map();
let mixer;
let clock = new THREE.Clock();
let poseTween = 1;
let targetPose = 1;
const cursor = { x: 0, y: 0, energy: 0 };
const poseTurns = [0, 0, Math.PI * .5, Math.PI, Math.PI, Math.PI * .5, 0, 0];

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x0b1321, .08);
const camera = new THREE.PerspectiveCamera(28, 1, .1, 100);
camera.position.set(3.8, 2.2, 7.8);
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.8));
renderer.setClearColor(0x000000, 0);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.shadowMap.enabled = true;
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.enablePan = false;
controls.minDistance = 4.3;
controls.maxDistance = 10;
controls.target.set(0, 0, 0);

scene.add(new THREE.HemisphereLight(0xdfe6de, 0x08101c, 2.1));
const keyLight = new THREE.DirectionalLight(0xf5e4c2, 3.5);
keyLight.position.set(3, 6, 5);
keyLight.castShadow = true;
scene.add(keyLight);
const rimLight = new THREE.DirectionalLight(0x9ab8cd, 2.4);
rimLight.position.set(-4, 3, -5);
scene.add(rimLight);

const floor = new THREE.Mesh(
  new THREE.CircleGeometry(2.45, 64),
  new THREE.MeshBasicMaterial({ color: 0x263342, transparent: true, opacity: .34 })
);
floor.rotation.x = -Math.PI / 2;
floor.position.y = .04;
scene.add(floor);

const grid = new THREE.GridHelper(5, 18, 0x7e9fb1, 0x314353);
grid.position.y = .045;
grid.material.transparent = true;
grid.material.opacity = .18;
scene.add(grid);
if (petMode) {
  floor.visible = false;
  grid.visible = false;
  camera.position.set(0, .35, 7.4);
  controls.target.set(0, 0, 0);
}

window.addEventListener('message', event => {
  if (event.data?.type !== 'fitness-ledger-pet-pointer') return;
  cursor.x = THREE.MathUtils.clamp(Number(event.data.x) || 0, -1, 1);
  cursor.y = THREE.MathUtils.clamp(Number(event.data.y) || 0, -1, 1);
  cursor.energy = THREE.MathUtils.clamp(Number(event.data.energy) || 0, 0, 1);
});

function renderPoseButtons() {
  list.innerHTML = poses.map((pose, index) => `<button class="guardian-pose-button" type="button" data-guardian-pose="${index}" aria-pressed="${index === activePose}"><span>${String(index + 1).padStart(2, '0')} / POSE</span><strong>${pose.name}</strong></button>`).join('');
  list.addEventListener('click', event => {
    const button = event.target.closest('[data-guardian-pose]');
    if (button) setPose(Number(button.dataset.guardianPose));
  });
}

function setPose(index) {
  activePose = (index + poses.length) % poses.length;
  targetPose = activePose;
  poseTween = 0;
  nameNode.textContent = poses[activePose].name;
  copyNode.textContent = poses[activePose].copy;
  indexNode.textContent = `${String(activePose + 1).padStart(2, '0')} / 08`;
  list.querySelectorAll('[data-guardian-pose]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.guardianPose) === activePose)));
}

function findBone(fragment, occurrence = 0) {
  const needle = fragment.toLowerCase().replace(/[^a-z0-9]/g, '');
  return [...bones.entries()].filter(([name]) => name.toLowerCase().replace(/[^a-z0-9]/g, '').includes(needle)).map(([, bone]) => bone)[occurrence];
}

function findAnyBone(...fragments) {
  return fragments.map(fragment => findBone(fragment)).find(Boolean);
}

function captureBaseTransforms() {
  bones.forEach((bone, name) => baseTransforms.set(name, { position: bone.position.clone(), quaternion: bone.quaternion.clone() }));
}

function applyPose(index, blend) {
  if (!modelRoot) return;
  bones.forEach((bone, name) => {
    const base = baseTransforms.get(name);
    if (!base) return;
    bone.position.lerp(base.position, blend);
    bone.quaternion.slerp(base.quaternion, blend);
  });

  const rightArm = findAnyBone('rightarm', 'arm_joint_r');
  const rightForearm = findAnyBone('rightforearm', 'arm_joint_r_2');
  const rightHand = findAnyBone('righthand', 'arm_joint_r_3');
  const leftArm = findAnyBone('leftarm', 'arm_joint_l');
  const leftForearm = findAnyBone('leftforearm', 'arm_joint_l_2');
  const leftHand = findAnyBone('lefthand', 'arm_joint_l_3');
  const rightThigh = findAnyBone('rightupleg', 'leg_joint_r_1');
  const leftThigh = findAnyBone('leftupleg', 'leg_joint_l_1');
  const rightShin = findAnyBone('rightleg', 'leg_joint_r_2');
  const leftShin = findAnyBone('leftleg', 'leg_joint_l_2');
  const chest = findAnyBone('spine1', 'torso_joint_2');
  const waist = findAnyBone('spine', 'torso_joint_1');
  const neck = findAnyBone('neck', 'neck_joint_1');
  const apply = (bone, x = 0, y = 0, z = 0) => { if (bone) bone.rotation.set(x, y, z); };

  const mirror = (right, left, x, y, z) => { apply(right, x, y, z); apply(left, x, -y, -z); };
  switch (index) {
    case 0: mirror(rightArm, leftArm, -.18, .58, .2); mirror(rightForearm, leftForearm, -.1, .3, .05); break;
    case 1: mirror(rightArm, leftArm, -1.12, .36, .16); mirror(rightForearm, leftForearm, -.82, .3, .12); mirror(rightHand, leftHand, -.35, .12, .06); break;
    case 2: apply(rightArm, -.3, -.55, .15); apply(rightForearm, -.1, -.35, .2); apply(leftArm, -.3, .32, -.15); apply(leftForearm, -.1, .28, -.2); break;
    case 3: mirror(rightArm, leftArm, -1.2, -.38, -.16); mirror(rightForearm, leftForearm, -.82, -.26, -.12); mirror(rightHand, leftHand, -.35, -.12, -.06); break;
    case 4: mirror(rightArm, leftArm, -.16, -.58, -.2); mirror(rightForearm, leftForearm, -.1, -.3, -.05); break;
    case 5: mirror(rightArm, leftArm, .45, .18, .12); mirror(rightForearm, leftForearm, .72, .12, .12); mirror(rightHand, leftHand, .16, .08, .03); break;
    case 6: mirror(rightArm, leftArm, -.55, .64, .2); mirror(rightForearm, leftForearm, -.92, .82, .1); mirror(rightHand, leftHand, -.5, .5, .05); break;
    case 7: mirror(rightArm, leftArm, -.86, .72, .16); mirror(rightForearm, leftForearm, -.42, .54, .1); mirror(rightHand, leftHand, -.2, .34, .05); apply(rightThigh, .18, -.1, .04); apply(leftThigh, .18, .1, -.04); apply(rightShin, -.18, -.08, 0); apply(leftShin, -.18, .08, 0); apply(waist, .24, 0, 0); break;
  }
  if (neck && (index === 2 || index === 5)) neck.rotation.y = index === 2 ? -.26 : .26;
}

function fitModel(rootNode) {
  const box = new THREE.Box3().setFromObject(rootNode);
  const size = box.getSize(new THREE.Vector3());
  const scale = 3.25 / Math.max(size.y, size.x, size.z);
  rootNode.scale.setScalar(scale);
  const scaledCenter = new THREE.Box3().setFromObject(rootNode).getCenter(new THREE.Vector3());
  rootNode.position.sub(scaledCenter);
  rootNode.position.y += .08;
}

function loadModel(url) {
  const loader = new GLTFLoader();
  const bodyTexture = url.includes('bodybuilder') ? new THREE.TextureLoader().load('./bodybuilder-texture.png') : null;
  if (bodyTexture) {
    bodyTexture.colorSpace = THREE.SRGBColorSpace;
    bodyTexture.flipY = false;
  }
  loader.load(url, gltf => {
    modelRoot = gltf.scene;
    modelRoot.traverse(node => {
      if (node.isBone) bones.set(node.name, node);
      if (node.isMesh) {
        node.castShadow = true;
        node.receiveShadow = true;
        node.material = new THREE.MeshStandardMaterial({ map: bodyTexture, color: bodyTexture ? 0xffffff : 0xc7a788, roughness: .58, metalness: .04 });
      }
    });
    fitModel(modelRoot);
    scene.add(modelRoot);
    captureBaseTransforms();
    if (gltf.animations?.length && gltf.animations[0].duration > .01) {
      mixer = new THREE.AnimationMixer(modelRoot);
      mixer.clipAction(gltf.animations[0]).play();
    }
    window.__guardianDebug = () => {
      const box = new THREE.Box3().setFromObject(modelRoot);
      return { min: box.min.toArray(), max: box.max.toArray(), position: modelRoot.position.toArray(), rotation: modelRoot.rotation.toArray(), scale: modelRoot.scale.toArray(), camera: camera.position.toArray(), target: controls.target.toArray(), bones: [...bones.keys()] };
    };
    status.textContent = url.includes('nick-walker') ? 'NICK WALKER / LOCAL GLB' : url.includes('bodybuilder') ? 'BODYBUILDER RIG / OPEN SOURCE FALLBACK' : 'FULL BODY RIG / OPEN SOURCE FALLBACK';
    setPose(activePose);
  }, undefined, () => {
    if (url.endsWith('nick-walker.glb')) loadModel('./bodybuilder.glb');
    else status.textContent = 'RIG LOAD ERROR';
  });
}

function resize() {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, rect.width);
  const height = Math.max(1, rect.height);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  if (mixer) mixer.update(delta);
  poseTween = Math.min(1, poseTween + delta * 3.4);
  applyPose(targetPose, poseTween);
  if (modelRoot) {
    const idleTurn = Math.sin(performance.now() / 1800) * .045;
    const targetTurn = poseTurns[targetPose] + cursor.x * .16 + idleTurn;
    modelRoot.rotation.y += (targetTurn - modelRoot.rotation.y) * .08;
    modelRoot.rotation.x += (cursor.y * .035 - modelRoot.rotation.x * .06) * .08;
    const neck = findAnyBone('neck', 'neck_joint_1');
    const chest = findAnyBone('spine1', 'torso_joint_2');
    if (neck) {
      neck.rotation.y += cursor.x * .22;
      neck.rotation.x += -cursor.y * .12;
    }
    if (chest) chest.rotation.y += cursor.x * .06;
  }
  controls.update();
  renderer.render(scene, camera);
}

renderPoseButtons();
setPose(activePose);
window.addEventListener('resize', resize);
window.addEventListener('keydown', event => {
  if (event.key === 'ArrowRight' || event.key === ' ') { event.preventDefault(); setPose(activePose + 1); }
  if (event.key === 'ArrowLeft') { event.preventDefault(); setPose(activePose - 1); }
  if (/^[1-8]$/.test(event.key)) setPose(Number(event.key) - 1);
});
canvas.addEventListener('click', () => setPose(activePose + 1));
resize();
loadModel('./nick-walker.glb');
animate();
