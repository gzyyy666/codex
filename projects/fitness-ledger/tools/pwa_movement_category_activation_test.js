const assert = require('assert')
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const source = fs.readFileSync(path.join(__dirname, '..', 'mobile_viewer', 'pwa', 'app-blur-height-fix.js'), 'utf8')
const start = source.indexOf('function activeBodyParts() {')
const end = source.indexOf('\nfunction activeMovementModules()', start)
assert.ok(start >= 0 && end > start, 'activeBodyParts must remain a named, testable function')
const functionSource = source.slice(start, end)

const bodyParts = [
  { id: 'shoulders', cn: '肩', en: 'SHOULDERS', tone: 'amber' },
  { id: 'chest', cn: '胸', en: 'CHEST', tone: 'ember' },
  { id: 'back', cn: '背', en: 'BACK', tone: 'teal' },
  { id: 'legs', cn: '腿', en: 'LEGS', tone: 'violet' },
  { id: 'arms', cn: '手臂', en: 'ARMS', tone: 'blue' },
  { id: 'glutes', cn: '臀', en: 'GLUTES', tone: 'rose' },
  { id: 'core', cn: '核心', en: 'CORE', tone: 'white' },
  { id: 'cardio', cn: '有氧', en: 'CARDIO', tone: 'blue' },
]
const defaultIds = ['chest', 'shoulders', 'back', 'legs', 'arms', 'core']
const defaultOrder = ['chest', 'shoulders', 'back', 'legs', 'arms', 'glutes', 'core', 'cardio']
const tones = Object.fromEntries(bodyParts.map(item => [item.id, item.tone]))

function resolve(categories) {
  const context = {
    state: { organization: { movement_categories: categories } },
    BODY_PARTS: bodyParts,
    DEFAULT_ACTIVE_BODY_PART_IDS: new Set(defaultIds),
    DEFAULT_BODY_PART_ORDER: defaultOrder,
    MOVEMENT_MODULE_TONES: tones,
  }
  const result = vm.runInNewContext(`${functionSource}; activeBodyParts().map(item => ({ id: item.id, cn: item.cn, en: item.en }))`, context)
  return JSON.parse(JSON.stringify(result))
}

const categories = [
  { category_id: 'chest', display_name: 'Chest', label_zh: '胸', active: true, sort_order: 10 },
  { category_id: 'shoulders', display_name: 'Shoulders', label_zh: '肩', active: true, sort_order: 20 },
  { category_id: 'back', display_name: 'Back', label_zh: '背', active: true, sort_order: 30 },
  { category_id: 'legs', display_name: 'Legs', label_zh: '腿', active: true, sort_order: 40 },
  { category_id: 'glutes', display_name: 'Glutes', label_zh: '臀', active: false, sort_order: 50 },
  { category_id: 'arms', display_name: 'Arms', label_zh: '手臂', active: true, sort_order: 60 },
  { category_id: 'core', display_name: 'Core', label_zh: '核心', active: true, sort_order: 70 },
  { category_id: 'cardio', display_name: 'Cardio', label_zh: '有氧', active: false, sort_order: 80 },
  { category_id: 'custom-body-part', display_name: 'Custom', active: true, sort_order: 90 },
]
assert.deepStrictEqual(resolve(categories).map(item => item.id), defaultIds)
assert.deepStrictEqual(resolve(categories).map(item => item.en), ['Chest', 'Shoulders', 'Back', 'Legs', 'Arms', 'Core'])
assert.deepStrictEqual(resolve(categories.filter(item => item.active === false)), [], 'all-disabled configured categories must not fall back to defaults')
assert.deepStrictEqual(resolve([]).map(item => item.id), defaultIds, 'an empty organization must retain the established default modules')

console.log('PWA_MOVEMENT_CATEGORY_ACTIVATION_OK')
