const assert = require('assert')
const {
  buildDataModuleReadModel,
  validateDataModuleContract,
} = require('../mini_program/miniprogram/utils/dataModuleContract')

const contract = {
  schema: 'fitness-ledger-mini-module-contract-v1',
  modules: [
    {
      module_id: 'waist_cm',
      label: '腰围',
      renderer: 'single_metric',
      record_level: { value: 'daily_scalar', label: '每日一个数值' },
      display_surface: { value: 'category_page', label: '跟随所属类别页面' },
      latest: { value: 82.5, display_unit: 'cm' },
      history: [{ value: 82.5, date: '2026-08-12' }],
      empty_state: null,
    },
    {
      module_id: 'resting_hr',
      label: '静息心率',
      renderer: 'metric_history',
      latest: null,
      history: [],
      empty_state: { kind: 'empty', message: '暂无记录' },
    },
  ],
}

validateDataModuleContract(contract)
const model = buildDataModuleReadModel(contract)
assert.deepStrictEqual(model.renderers, ['metric_history', 'single_metric'])
assert.strictEqual(model.modules[0].history.length, 0)
assert.strictEqual(model.modules[1].state, 'empty')
assert.strictEqual(model.modules[0].display_surface.value, 'category_page')

assert.throws(() => buildDataModuleReadModel({
  ...contract,
  modules: [{ ...contract.modules[0], renderer: 'unsupported_renderer' }],
}), (error) => error.code === 'MODULE_CONTRACT_RENDERER_UNSUPPORTED')

console.log('data_module_mini_contract_test: PASS')
