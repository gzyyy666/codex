let latest = null;
const $ = id => document.getElementById(id);
const csv = id => $(id).value.split(',').map(value => value.trim()).filter(Boolean);

function annotation() {
  return {
    expected_capabilities: csv('required'),
    optional_capabilities: csv('optional'),
    forbidden_capabilities: csv('forbidden'),
    expected_abstain: false,
    explanation: $('explanation').value.trim()
  };
}

function render(value) {
  latest = value;
  $('status').textContent = value.status || 'unknown';
  $('summary').textContent = [
    `Gate: ${value.gate?.status || '-'}`,
    `Planner: ${value.planner?.status || '-'} / ${value.planner?.latency_ms || 0}ms`,
    `Validation: ${value.validation?.status || '-'}`,
    `Evidence: ${value.analysis_evaluation?.status || '-'}`,
    `Claims: ${value.analysis_evaluation?.allowed_claim_mode || '-'}`,
    `Executor: ${value.execution?.executor_called === false ? 'not called' : 'check required'}`,
    `Raw: ${value.gpt_analysis_package_preview?.raw_included === false ? 'not included' : 'not packaged'}`
  ].join(' · ');
  $('result').textContent = JSON.stringify(value, null, 2);
  $('raw').textContent = value.planner?.raw_output || '(no model output; Gate or transport stopped before Planner)';
}

$('preview').onclick = async () => {
  $('status').textContent = 'running…';
  const payload = { request: $('request').value, budget_mode: $('budget').value, confirmations: {} };
  try {
    const response = await fetch('/api/preview', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    render(await response.json());
  } catch (error) {
    render({status: 'ui_error', error: String(error)});
  }
};
$('download').onclick = () => {
  if (!latest) {
    alert('请先运行 Preview');
    return;
  }
  const bundle = {
    schema_version: 'fitness-ledger-review-case-v1',
    anonymous_intent_required: true,
    user_input: $('request').value,
    response: latest,
    human_annotation: annotation()
  };
  const blob = new Blob([JSON.stringify(bundle, null, 2)], {type: 'application/json'});
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = 'fitness-ledger-review-case.json';
  link.click();
  URL.revokeObjectURL(link.href);
};
