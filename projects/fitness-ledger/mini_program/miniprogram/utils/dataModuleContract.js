const SUPPORTED_RENDERERS = new Set(['single_metric', 'metric_history'])

function assertContract(condition, message, code) {
  if (!condition) {
    const error = new Error(message)
    error.code = code
    throw error
  }
}

function validateDataModuleContract(payload) {
  assertContract(payload && payload.schema === 'fitness-ledger-mini-module-contract-v1', 'Invalid Data Module contract schema.', 'MODULE_CONTRACT_SCHEMA_INVALID')
  assertContract(Array.isArray(payload.modules), 'Data Module contract modules must be a list.', 'MODULE_CONTRACT_MODULES_INVALID')
  const seen = new Set()
  payload.modules.forEach((module) => {
    assertContract(module && typeof module.module_id === 'string' && module.module_id.length > 0, 'Data Module module_id is required.', 'MODULE_CONTRACT_ID_REQUIRED')
    assertContract(!seen.has(module.module_id), 'Data Module module_id is duplicated.', 'MODULE_CONTRACT_ID_DUPLICATE')
    seen.add(module.module_id)
    assertContract(SUPPORTED_RENDERERS.has(module.renderer), 'Data Module renderer is unsupported.', 'MODULE_CONTRACT_RENDERER_UNSUPPORTED')
    if (module.display_surface !== undefined) {
      assertContract(module.display_surface && typeof module.display_surface.value === 'string', 'Data Module display surface is invalid.', 'MODULE_CONTRACT_SURFACE_INVALID')
    }
    if (module.display_page !== undefined && module.display_page !== null) {
      assertContract(typeof module.display_page.value === 'string', 'Data Module display page is invalid.', 'MODULE_CONTRACT_PAGE_INVALID')
    }
    assertContract(Array.isArray(module.history), 'Data Module history must be a list.', 'MODULE_CONTRACT_HISTORY_INVALID')
    if (module.latest !== null) {
      assertContract(module.history.length > 0, 'Data Module latest requires history.', 'MODULE_CONTRACT_LATEST_INVALID')
    }
  })
  return payload
}

function renderDataModuleCard(module) {
  validateDataModuleContract({ schema: 'fitness-ledger-mini-module-contract-v1', modules: [module] })
  const history = module.history.slice()
  const empty = module.latest === null && history.length === 0
  if (module.renderer === 'single_metric') {
    return {
      module_id: module.module_id,
      category_id: module.category_id || 'extension',
      renderer: module.renderer,
      label: module.label,
      status: module.status || 'active',
      record_level: module.record_level || { value: 'daily_scalar', label: '每日一个数值' },
      display_surface: module.display_surface || { value: 'category_page', label: '跟随所属类别页面' },
      display_page: module.display_page || null,
      state: empty ? 'empty' : 'ready',
      latest: displayRecord(module.latest),
      history: [],
      record_history: history.map(displayRecord),
      empty_state: empty ? (module.empty_state || { kind: 'empty', message: '暂无记录' }) : null,
    }
  }
  if (module.renderer === 'metric_history') {
    return {
      module_id: module.module_id,
      category_id: module.category_id || 'extension',
      renderer: module.renderer,
      label: module.label,
      status: module.status || 'active',
      record_level: module.record_level || { value: 'daily_scalar', label: '每日一个数值' },
      display_surface: module.display_surface || { value: 'category_page', label: '跟随所属类别页面' },
      display_page: module.display_page || null,
      state: empty ? 'empty' : 'ready',
      latest: displayRecord(module.latest),
      history: history.map(displayRecord),
      record_history: history.map(displayRecord),
      empty_state: empty ? (module.empty_state || { kind: 'empty', message: '暂无记录' }) : null,
    }
  }
  // validateDataModuleContract makes this unreachable, but keeps the finite
  // renderer boundary explicit if a new renderer is proposed later.
  throw new Error('Unsupported Data Module renderer.')
}

function displayRecord(record) {
  if (!record) return null
  return {
    ...record,
    value_label: record.display_value !== undefined && record.display_value !== null ? record.display_value : record.value,
    unit_label: record.display_unit || record.actual_unit || '',
  }
}

function modulesForDate(model, categoryId, date) {
  const targetDate = String(date || '').slice(0, 10)
  return (model && Array.isArray(model.modules) ? model.modules : []).map((module) => {
    if (categoryId && module.category_id !== categoryId) return null
    const records = (module.record_history || module.history || []).filter((record) => String(record.date || '').slice(0, 10) === targetDate)
    if (!records.length) return null
    return {
      ...module,
      latest: records[0],
      history: module.renderer === 'metric_history' ? records : [],
      record_history: records,
      state: 'ready',
    }
  }).filter(Boolean)
}

function modulesForExtension(model) {
  return (model && Array.isArray(model.modules) ? model.modules : []).filter((module) => {
    if (module.category_id !== 'extension' || module.status === 'retired') return false
    const surface = module.display_surface && module.display_surface.value
    const page = module.display_page && module.display_page.value
    if (surface === 'record_only' || surface === 'history_only') return false
    return !(surface === 'page_widget' && (!page || page === 'home'))
  })
}

function buildDataModuleReadModel(contract) {
  validateDataModuleContract(contract)
  return {
    schema: 'fitness-ledger-mini-module-read-model-v1',
    modules: contract.modules.map(renderDataModuleCard),
    renderers: Array.from(new Set(contract.modules.map((module) => module.renderer))).sort(),
  }
}

module.exports = {
  SUPPORTED_RENDERERS,
  validateDataModuleContract,
  renderDataModuleCard,
  buildDataModuleReadModel,
  safeBuildDataModuleReadModel,
  modulesForDate,
  modulesForExtension,
}

function safeBuildDataModuleReadModel(contract) {
  try {
    return buildDataModuleReadModel(contract)
  } catch (_error) {
    return { schema: 'fitness-ledger-mini-module-read-model-v1', modules: [], renderers: [], error: 'MODULE_CONTRACT_INVALID' }
  }
}
