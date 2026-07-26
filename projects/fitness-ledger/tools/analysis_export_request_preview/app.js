const exampleSelect = document.querySelector('#exampleSelect');
const requestInput = document.querySelector('#requestInput');
const result = document.querySelector('#result');
const status = document.querySelector('#status');
let examples = [];

async function loadExamples() {
  const response = await fetch('/api/examples');
  const payload = await response.json();
  examples = payload.examples || [];
  exampleSelect.replaceChildren(...examples.map((item, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = item.name;
    return option;
  }));
  if (examples.length) loadSelectedExample();
}

function loadSelectedExample() {
  const item = examples[Number(exampleSelect.value)];
  if (item) requestInput.value = JSON.stringify(item.request, null, 2);
}

async function validateRequest() {
  status.className = 'status neutral';
  status.textContent = 'Validating…';
  const response = await fetch('/api/validate', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: requestInput.value });
  const payload = await response.json();
  status.className = `status ${payload.valid ? 'valid' : 'invalid'}`;
  status.textContent = payload.valid ? 'VALID · preview only' : `REJECTED · ${payload.errors.length} error(s)`;
  result.textContent = JSON.stringify(payload, null, 2);
}

document.querySelector('#loadExample').addEventListener('click', loadSelectedExample);
document.querySelector('#validate').addEventListener('click', validateRequest);
loadExamples().catch((error) => { status.className = 'status invalid'; status.textContent = 'Preview unavailable'; result.textContent = String(error); });
