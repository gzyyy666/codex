import * as THREE from './three.module.min.js';
import { GLTFLoader } from './GLTFLoader.js';

const poseCount = 8;
const assetUrl = file => new URL(file, import.meta.url).href;
const poseTurns = [0, 0, Math.PI * .5, Math.PI, Math.PI, Math.PI * .5, 0, 0];

export function mountGuardianPet(canvas) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(28, 1, .1, 100);
  camera.position.set(0, .35, 7.4);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, premultipliedAlpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.8));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  scene.add(new THREE.HemisphereLight(0xdfe6de, 0x08101c, 2.1));
  const keyLight = new THREE.DirectionalLight(0xf5e4c2, 3.5);
  keyLight.position.set(3, 6, 5);
  scene.add(keyLight);
  const rimLight = new THREE.DirectionalLight(0x9ab8cd, 2.4);
  rimLight.position.set(-4, 3, -5);
  scene.add(rimLight);

  const cursor = { x: 0, y: 0, energy: 0 };
  const bones = new Map();
  const baseTransforms = new Map();
  let modelRoot;
  let pose = 1;
  let poseTween = 1;
  let frame = 0;
  let disposed = false;

  const findBone = (fragment, occurrence = 0) => {
    const needle = fragment.toLowerCase().replace(/[^a-z0-9]/g, '');
    return [...bones.entries()]
      .filter(([name]) => name.toLowerCase().replace(/[^a-z0-9]/g, '').includes(needle))
      .map(([, bone]) => bone)[occurrence];
  };
  const findAnyBone = (...fragments) => fragments.map(fragment => findBone(fragment)).find(Boolean);
  const apply = (bone, x = 0, y = 0, z = 0) => { if (bone) bone.rotation.set(x, y, z); };
  const mirror = (right, left, x, y, z) => { apply(right, x, y, z); apply(left, x, -y, -z); };

  const applyPose = (index, blend) => {
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
  };

  const loadModel = (url, fallback = true) => {
    const loader = new GLTFLoader();
    const texture = url.includes('bodybuilder') ? new THREE.TextureLoader().load(assetUrl('bodybuilder-texture.png')) : null;
    if (texture) {
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.flipY = false;
    }
    loader.load(assetUrl(url), gltf => {
      if (disposed) return;
      modelRoot = gltf.scene;
      modelRoot.traverse(node => {
        if (node.isBone) bones.set(node.name, node);
        if (node.isMesh) {
          node.material = new THREE.MeshStandardMaterial({ map: texture, color: texture ? 0xffffff : 0xc7a788, roughness: .58, metalness: .04 });
        }
      });
      const box = new THREE.Box3().setFromObject(modelRoot);
      const size = box.getSize(new THREE.Vector3());
      modelRoot.scale.setScalar(3.25 / Math.max(size.y, size.x, size.z));
      const center = new THREE.Box3().setFromObject(modelRoot).getCenter(new THREE.Vector3());
      modelRoot.position.sub(center);
      modelRoot.position.y += .08;
      scene.add(modelRoot);
      bones.forEach((bone, name) => baseTransforms.set(name, { position: bone.position.clone(), quaternion: bone.quaternion.clone() }));
      applyPose(pose, 1);
    }, undefined, () => {
      if (fallback && url.endsWith('nick-walker.glb')) loadModel('bodybuilder.glb', false);
    });
  };

  const resize = () => {
    const width = Math.max(1, canvas.clientWidth || 360);
    const height = Math.max(1, canvas.clientHeight || 360);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  const onResize = () => resize();
  const animate = () => {
    if (disposed) return;
    frame = requestAnimationFrame(animate);
    poseTween = Math.min(1, poseTween + .055);
    applyPose(pose, poseTween);
    if (modelRoot) {
      const delta = .016;
      const idleTurn = Math.sin(performance.now() / 1800) * .045;
      const targetTurn = poseTurns[pose] + cursor.x * .16 + idleTurn;
      modelRoot.rotation.y += (targetTurn - modelRoot.rotation.y) * .08;
      modelRoot.rotation.x += (cursor.y * .035 - modelRoot.rotation.x * .06) * .08;
      const neck = findAnyBone('neck', 'neck_joint_1');
      const chest = findAnyBone('spine1', 'torso_joint_2');
      if (neck) { neck.rotation.y += cursor.x * .22; neck.rotation.x += -cursor.y * .12; }
      if (chest) chest.rotation.y += cursor.x * .06;
    }
    renderer.render(scene, camera);
  };

  const setPointer = ({ x = 0, y = 0, energy = 0 } = {}) => {
    cursor.x = THREE.MathUtils.clamp(Number(x) || 0, -1, 1);
    cursor.y = THREE.MathUtils.clamp(Number(y) || 0, -1, 1);
    cursor.energy = THREE.MathUtils.clamp(Number(energy) || 0, 0, 1);
  };
  const setPose = index => {
    pose = (index + poseCount) % poseCount;
    poseTween = 0;
  };
  const onClick = () => setPose(pose + 1);

  canvas.addEventListener('click', onClick);
  window.addEventListener('resize', onResize);
  resize();
  loadModel('nick-walker.glb');
  animate();

  return {
    setPointer,
    setPose,
    nextPose: () => setPose(pose + 1),
    dispose() {
      disposed = true;
      cancelAnimationFrame(frame);
      canvas.removeEventListener('click', onClick);
      window.removeEventListener('resize', onResize);
      renderer.dispose();
      scene.clear();
    }
  };
}
