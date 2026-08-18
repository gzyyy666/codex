(function attachFitnessLedgerDataModules(root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.FLDataModules = api;
})(typeof window !== "undefined" ? window : globalThis, function createFitnessLedgerDataModules() {
  const NATIVE_CATEGORIES = new Set(["body", "diet", "training"]);

  function scalar(value, fallback = "") {
    if (value === undefined || value === null) return fallback;
    const text = String(value).trim();
    return text || fallback;
  }

  function surfaceValue(value, fallback) {
    if (value && typeof value === "object") return scalar(value.value, fallback);
    return scalar(value, fallback);
  }

  function normalizeRecord(record, moduleId) {
    if (!record || typeof record !== "object") return null;
    const date = scalar(record.date || record.Date).slice(0, 10);
    if (!date) return null;
    return {
      record_id: scalar(record.record_id || record.id || record._id),
      module_id: scalar(record.module_id, moduleId),
      date,
      value: record.value,
      actual_unit: scalar(record.actual_unit || record.display_unit),
      display_value: record.display_value,
      display_unit: scalar(record.display_unit),
    };
  }

  function normalizeModule(module) {
    const moduleId = scalar(module && module.module_id);
    if (!moduleId) return null;
    const records = [];
    const sourceRecords = Array.isArray(module.history) ? module.history : [];
    sourceRecords.forEach(record => {
      const normalized = normalizeRecord(record, moduleId);
      if (normalized) records.push(normalized);
    });
    const latest = normalizeRecord(module.latest, moduleId);
    if (latest && !records.some(record => record.record_id && record.record_id === latest.record_id)) records.push(latest);
    records.sort((a, b) => b.date.localeCompare(a.date) || b.record_id.localeCompare(a.record_id));
    return {
      module_id: moduleId,
      label: scalar(module.label, moduleId),
      category_id: scalar(module.category_id, "extension"),
      renderer: scalar(module.renderer, "single_metric"),
      status: scalar(module.status, "active"),
      recording_enabled: module.recording_enabled !== false,
      display_surface: surfaceValue(module.display_surface, "category_page"),
      display_page: surfaceValue(module.display_page, ""),
      history: records,
      latest: records[0] || null,
    };
  }

  function normalizeContract(payload) {
    const modules = (Array.isArray(payload && payload.modules) ? payload.modules : [])
      .map(normalizeModule)
      .filter(Boolean);
    return { schema: "fitness-ledger-mobile-module-read-model-v1", modules };
  }

  function recordForDate(module, date) {
    const target = scalar(date).slice(0, 10);
    return (module && Array.isArray(module.history) ? module.history : []).find(record => record.date === target) || null;
  }

  function formattedValue(record) {
    if (!record) return "";
    const value = record.display_value !== undefined && record.display_value !== null
      ? record.display_value
      : record.value;
    const unit = scalar(record.display_unit || record.actual_unit);
    return `${scalar(value, "-")}${unit ? ` ${unit}` : ""}`;
  }

  function categoryEntriesForDate(contract, categoryId, date) {
    return (contract && Array.isArray(contract.modules) ? contract.modules : []).map(module => {
      if (module.category_id !== categoryId || module.display_surface !== "category_page") return null;
      const record = recordForDate(module, date);
      return record ? { module, record, value: formattedValue(record) } : null;
    }).filter(Boolean);
  }

  function detailEntriesForDate(contract, date) {
    return (contract && Array.isArray(contract.modules) ? contract.modules : []).map(module => {
      if (module.display_surface === "record_only") return null;
      const record = recordForDate(module, date);
      return record ? { module, record, value: formattedValue(record) } : null;
    }).filter(Boolean);
  }

  function extensionEntriesForDate(contract, date) {
    return detailEntriesForDate(contract, date).filter(entry => !NATIVE_CATEGORIES.has(entry.module.category_id));
  }

  function widgetEntriesForPage(contract, page) {
    return (contract && Array.isArray(contract.modules) ? contract.modules : []).map(module => {
      if (module.status === "retired" || module.display_surface !== "page_widget") return null;
      if ((module.display_page || "home") !== page || !module.latest) return null;
      return { module, record: module.latest, value: formattedValue(module.latest) };
    }).filter(Boolean);
  }

  function mergeRecordsWithCategoryDates(records, contract, categoryId) {
    const rows = Array.isArray(records) ? records.map(record => ({ ...record })) : [];
    const seen = new Set(rows.map(record => scalar(record.Date || record.date).slice(0, 10)).filter(Boolean));
    (contract && Array.isArray(contract.modules) ? contract.modules : []).forEach(module => {
      if (module.category_id !== categoryId || module.display_surface !== "category_page") return;
      module.history.forEach(record => {
        if (!seen.has(record.date)) {
          rows.push({ Date: record.date, __module_only: true });
          seen.add(record.date);
        }
      });
    });
    return rows.sort((a, b) => scalar(b.Date || b.date).localeCompare(scalar(a.Date || a.date)));
  }

  return {
    NATIVE_CATEGORIES,
    normalizeContract,
    recordForDate,
    formattedValue,
    categoryEntriesForDate,
    detailEntriesForDate,
    extensionEntriesForDate,
    widgetEntriesForPage,
    mergeRecordsWithCategoryDates,
  };
});
