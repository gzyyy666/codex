const DEG2RAD = Math.PI / 180;

export function createGuardianUniforms() {
  return {
    uGuardianBaseYaw: { value: 0 },
    uGuardianUpperYaw: { value: 0 },
    uGuardianHeadYaw: { value: 0 },
    uGuardianUpperPitch: { value: 0 },
    uGuardianHeadPitch: { value: 0 },
    uGuardianTime: { value: 0 },
    uGuardianBreath: { value: 1 },
    uGuardianTension: { value: 0.62 },
    uGuardianRigNorm: { value: 1 }
  };
}

const GLSL_HEADER = /* glsl */ `
uniform float uGuardianBaseYaw;
uniform float uGuardianUpperYaw;
uniform float uGuardianHeadYaw;
uniform float uGuardianUpperPitch;
uniform float uGuardianHeadPitch;
uniform float uGuardianTime;
uniform float uGuardianBreath;
uniform float uGuardianTension;
uniform float uGuardianRigNorm;

vec3 guardianRotY(vec3 p, float a) {
  float c = cos(a);
  float s = sin(a);
  return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
}

vec3 guardianRotX(vec3 p, float a) {
  float c = cos(a);
  float s = sin(a);
  return vec3(p.x, c * p.y - s * p.z, s * p.y + c * p.z);
}

vec3 guardianTransformPosition(vec3 inputPosition) {
  float rig = max(uGuardianRigNorm, 0.0001);
  vec3 p = guardianRotY(inputPosition, uGuardianBaseYaw);
  vec3 pn = p / rig;
  float upperMask = smoothstep(0.40, 0.48, pn.y);
  vec3 waistPivot = vec3(0.0, 0.45 * rig, 0.0);
  p = mix(p, guardianRotY(p - waistPivot, uGuardianUpperYaw) + waistPivot, upperMask);
  p = mix(p, guardianRotX(p - waistPivot, uGuardianUpperPitch) + waistPivot, upperMask);

  pn = p / rig;
  float headMask = smoothstep(0.76, 0.83, pn.y)
                 * (1.0 - smoothstep(0.13, 0.19, abs(pn.x)));
  vec3 neckPivot = vec3(0.0, 0.80 * rig, 0.0);
  p = mix(p, guardianRotY(p - neckPivot, uGuardianHeadYaw) + neckPivot, headMask);
  p = mix(p, guardianRotX(p - neckPivot, uGuardianHeadPitch) + neckPivot, headMask);

  float breathWave = sin(uGuardianTime * 0.96) * max(uGuardianBreath, 0.0);
  float breathMask = smoothstep(0.38, 0.52, pn.y) * (1.0 - smoothstep(0.82, 0.98, pn.y));
  vec3 chestPivot = vec3(0.0, 0.50 * rig, 0.0);
  float chestExpansion = 1.0 + breathWave * 0.008;
  p.xz = mix(p.xz, chestPivot.xz + (p.xz - chestPivot.xz) * chestExpansion, breathMask);
  p.z += breathMask * (breathWave * 0.009 * rig + 0.0015 * uGuardianTension * rig);
  p.y += breathMask * breathWave * 0.0032 * rig;
  return p;
}

vec3 guardianTransformNormal(vec3 inputPosition, vec3 inputNormal) {
  float rig = max(uGuardianRigNorm, 0.0001);
  vec3 p = guardianRotY(inputPosition, uGuardianBaseYaw);
  vec3 n = normalize(guardianRotY(inputNormal, uGuardianBaseYaw));
  vec3 pn = p / rig;
  float upperMask = smoothstep(0.40, 0.48, pn.y);
  vec3 waistPivot = vec3(0.0, 0.45 * rig, 0.0);
  p = mix(p, guardianRotY(p - waistPivot, uGuardianUpperYaw) + waistPivot, upperMask);
  n = normalize(mix(n, guardianRotY(n, uGuardianUpperYaw), upperMask));
  p = mix(p, guardianRotX(p - waistPivot, uGuardianUpperPitch) + waistPivot, upperMask);
  n = normalize(mix(n, guardianRotX(n, uGuardianUpperPitch), upperMask));

  pn = p / rig;
  float headMask = smoothstep(0.76, 0.83, pn.y)
                 * (1.0 - smoothstep(0.13, 0.19, abs(pn.x)));
  n = normalize(mix(n, guardianRotY(n, uGuardianHeadYaw), headMask));
  n = normalize(mix(n, guardianRotX(n, uGuardianHeadPitch), headMask));
  return n;
}
`;

export function patchGuardianMaterial(material, uniforms = createGuardianUniforms(), onError = null) {
  if (!material || typeof material !== 'object') throw new TypeError('Three.js material required');
  const previousOnBeforeCompile = material.onBeforeCompile;
  const previousCacheKey = material.customProgramCacheKey?.bind(material);
  let compiledShader = null;
  let disabled = false;

  const restoreHooks = () => {
    material.onBeforeCompile = previousOnBeforeCompile;
    if (previousCacheKey) material.customProgramCacheKey = previousCacheKey;
    else delete material.customProgramCacheKey;
    material.needsUpdate = true;
  };

  const disable = () => {
    if (disabled) return;
    disabled = true;
    compiledShader = null;
    restoreHooks();
  };

  material.onBeforeCompile = (shader, renderer) => {
    if (disabled) {
      previousOnBeforeCompile?.(shader, renderer);
      return;
    }
    try {
      previousOnBeforeCompile?.(shader, renderer);
      const source = shader.vertexShader;
      if (!source.includes('void main() {') || !source.includes('#include <begin_vertex>')) {
        disable();
        return;
      }
      Object.assign(shader.uniforms, uniforms);
      let vertexShader = source.replace('void main() {', `${GLSL_HEADER}\nvoid main() {`);
      vertexShader = vertexShader.replace(
        '#include <beginnormal_vertex>',
        '#include <beginnormal_vertex>\nobjectNormal = guardianTransformNormal(position, objectNormal);'
      );
      vertexShader = vertexShader.replace(
        '#include <begin_vertex>',
        '#include <begin_vertex>\ntransformed = guardianTransformPosition(transformed);'
      );
      shader.vertexShader = vertexShader;
      compiledShader = shader;
    } catch (error) {
      console.warn('[Guardian] shader deformation disabled; original material retained', error);
      disable();
    }
  };
  material.customProgramCacheKey = () => `${previousCacheKey ? previousCacheKey() : ''}|fl-guardian-static-mask-v6.2`;
  material.needsUpdate = true;

  return {
    material,
    uniforms,
    get compiledShader() { return compiledShader; },
    set(values = {}) {
      if (disabled) return;
      if (Number.isFinite(values.baseYaw)) uniforms.uGuardianBaseYaw.value = values.baseYaw;
      if (Number.isFinite(values.upperYaw)) uniforms.uGuardianUpperYaw.value = values.upperYaw;
      if (Number.isFinite(values.headYaw)) uniforms.uGuardianHeadYaw.value = values.headYaw;
      if (Number.isFinite(values.upperPitch)) uniforms.uGuardianUpperPitch.value = values.upperPitch;
      if (Number.isFinite(values.headPitch)) uniforms.uGuardianHeadPitch.value = values.headPitch;
      if (Number.isFinite(values.timeSeconds)) uniforms.uGuardianTime.value = values.timeSeconds;
      if (Number.isFinite(values.breath)) uniforms.uGuardianBreath.value = Math.max(values.breath, 0);
      if (Number.isFinite(values.tension)) uniforms.uGuardianTension.value = values.tension;
      if (Number.isFinite(values.rigNorm)) uniforms.uGuardianRigNorm.value = Math.max(values.rigNorm, 0.0001);
    },
    disable,
    dispose() {
      disable();
      compiledShader = null;
    }
  };
}

export const degreesToRadians = degrees => degrees * DEG2RAD;
