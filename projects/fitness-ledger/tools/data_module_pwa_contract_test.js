const assert = require('assert')
const path = require('path')

const tools = require(path.join(__dirname, '..', 'mobile_viewer', 'pwa', 'data-modules.js'))

const contract = tools.normalizeContract({
  schema: 'fitness-ledger-mini-module-contract-v1',
  modules: [
    {
      module_id: 'waist_cm', label: '腰围', category_id: 'body', status: 'active',
      display_surface: { value: 'category_page' },
      history: [{ record_id: 'waist-1', date: '2026-08-15', value: 82.5, actual_unit: 'cm' }],
    },
    {
      module_id: 'creatine_g', label: '肌酸', category_id: 'diet', status: 'active',
      display_surface: { value: 'category_page' },
      history: [{ record_id: 'creatine-1', date: '2026-08-14', value: 5, actual_unit: 'g' }],
    },
    {
      module_id: 'readiness', label: '训练状态', category_id: 'training', status: 'active',
      display_surface: { value: 'category_page' },
      history: [{ record_id: 'readiness-1', date: '2026-08-13', value: 8, actual_unit: '' }],
    },
    {
      module_id: 'sleep_score', label: '睡眠评分', category_id: 'recovery', status: 'active',
      display_surface: { value: 'page_widget' }, display_page: { value: 'home' },
      history: [{ record_id: 'sleep-1', date: '2026-08-15', value: 7, actual_unit: '' }],
    },
    {
      module_id: 'private_metric', label: '隐藏指标', category_id: 'extension', status: 'active',
      display_surface: { value: 'record_only' },
      history: [{ record_id: 'private-1', date: '2026-08-15', value: 9, actual_unit: '' }],
    },
  ],
})

assert.strictEqual(contract.modules.length, 5)
assert.strictEqual(tools.categoryEntriesForDate(contract, 'body', '2026-08-15')[0].value, '82.5 cm')
assert.strictEqual(tools.categoryEntriesForDate(contract, 'diet', '2026-08-14')[0].value, '5 g')
assert.strictEqual(tools.categoryEntriesForDate(contract, 'training', '2026-08-13')[0].value, '8')

const dietRows = tools.mergeRecordsWithCategoryDates([], contract, 'diet')
assert.deepStrictEqual(dietRows, [{ Date: '2026-08-14', __module_only: true }])
const bodyRows = tools.mergeRecordsWithCategoryDates([{ Date: '2026-08-15', 'Weight (kg)': 70 }], contract, 'body')
assert.strictEqual(bodyRows.length, 1, 'a native date must not be duplicated')

const widgets = tools.widgetEntriesForPage(contract, 'home')
assert.deepStrictEqual(widgets.map(item => item.module.module_id), ['sleep_score'])
assert.strictEqual(tools.extensionEntriesForDate(contract, '2026-08-15')[0].module.module_id, 'sleep_score')
assert.ok(!tools.detailEntriesForDate(contract, '2026-08-15').some(item => item.module.module_id === 'private_metric'))

console.log('DATA_MODULE_PWA_CONTRACT_OK')
