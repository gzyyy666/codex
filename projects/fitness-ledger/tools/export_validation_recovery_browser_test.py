"""Reproduce error/clear/revalidate through actual Edge controls.

Default execution uses only a disposable anonymous application. --formal-probe
performs parsing and request validation only against the already running app.
It never exports or changes a ledger record.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.run_data_module_formal_mirror import ensure_sandbox
from tools.data_module_formal_mirror_browser_e2e_test import (
    _click, _close_process, _safe_cleanup, _set_css, _start_browser, _wait,
)
from web_desktop.backend.server import LedgerWebService, create_server

REQUEST = {'request_version': '1.1', 'purpose': 'Verify repeated export validation recovery',
           'datasets': [{'dataset_id': 'body_recent', 'type': 'body',
                         'time_range': {'mode': 'recent_days', 'days': 7},
                         'filters': {}, 'fields': ['date', 'weight_kg']}],
           'raw': False, 'output': {'formats': ['json', 'markdown']}}


def exercise(port: int, expect_bug: bool) -> None:
    edge = browser = edge_data = None
    try:
        edge, browser, edge_data = _start_browser(port)
        browser.evaluate("location.hash='tools?panel=export'")
        _wait(browser, "!!document.querySelector('#analysis-export-request')")
        _click(browser, '[data-analysis-export-mode="json"]')
        if browser.evaluate("!!document.querySelector('.analysis-export-json-tools summary')"):
            _click(browser, '.analysis-export-json-tools summary')
        if not expect_bug:
            assert browser.evaluate("document.querySelector('#analysis-export-request').getAttribute('translate')") == 'no'
        browser.evaluate("""window.__validationReplies=[];window.__originalExportFetch=window.fetch;
          window.fetch=async(...args)=>{const r=await window.__originalExportFetch(...args);
          if(String(args[0]).endsWith('/api/analysis-export/v1/validate'))
            window.__validationReplies.push(await r.clone().json());return r};true""")
        _set_css(browser, '#analysis-export-request', '{"request_version":')
        _click(browser, '[data-analysis-export-natural-preview]')
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='error'")
        containers_after_error = browser.evaluate("!!document.querySelector('#analysis-export-scope-digest')&&!!document.querySelector('#analysis-export-bundle-list')")
        _click(browser, '[data-analysis-export-clear]')
        _set_css(browser, '#analysis-export-request', json.dumps(REQUEST))
        _click(browser, '[data-analysis-export-natural-preview]')
        _wait(browser, "window.__validationReplies.length===1")
        result = browser.evaluate("({api:window.__validationReplies[0].status,stage:document.querySelector('.analysis-export-page').dataset.stage,containersAfterError:"+str(containers_after_error).lower()+",nextEnabled:!document.querySelector('#analysis-export-next').disabled})")
        assert result['api'] == 'valid', result
        if expect_bug:
            assert result['stage'] == 'validate' and not result['containersAfterError'], result
            print(json.dumps({'status': 'BUG_REPRODUCED', **result}))
            return
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='scope'")
        assert result['containersAfterError'] and result['nextEnabled'], result
        _set_css(browser, '#analysis-export-request', json.dumps(REQUEST) + '{“目的”: “测试”}')
        _click(browser, '[data-analysis-export-natural-preview]')
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='error'")
        explanation = browser.evaluate("document.querySelector('#analysis-export-error').innerText")
        assert '拼接' in explanation and '智能引号' in explanation, explanation
        _click(browser, '[data-analysis-export-clear]')
        _set_css(browser, '#analysis-export-request', json.dumps(REQUEST))
        _click(browser, '[data-analysis-export-natural-preview]')
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='scope'")
        # A schema rejection also has to recover by replacing input, with no
        # navigation or page rebuild.
        invalid = json.loads(json.dumps(REQUEST))
        invalid['datasets'][0]['fields'] = ['date', 'not_a_field']
        _set_css(browser, '#analysis-export-request', json.dumps(invalid))
        _click(browser, '[data-analysis-export-natural-preview]')
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='error'")
        _set_css(browser, '#analysis-export-request', json.dumps(REQUEST))
        _click(browser, '[data-analysis-export-natural-preview]')
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='scope'")
        # Switching modes and returning must not inherit stale error markup.
        _click(browser, '[data-analysis-export-mode="guided"]')
        _click(browser, '[data-analysis-export-mode="json"]')
        _set_css(browser, '#analysis-export-request', json.dumps(REQUEST))
        _click(browser, '[data-analysis-export-natural-preview]')
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='scope'")
        # A transient failure must recover on retry without requiring input
        # changes. Only this anonymous fixture test injects the network error.
        browser.evaluate("""window.__retryExportFetch=window.fetch;window.__failExportOnce=true;
          window.fetch=async(...args)=>{if(window.__failExportOnce&&String(args[0]).endsWith('/api/analysis-export/v1/validate')){
          window.__failExportOnce=false;throw new Error('anonymous validation network failure')}
          return window.__retryExportFetch(...args)};true""")
        _click(browser, '[data-analysis-export-natural-preview]')
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='error'")
        _click(browser, '[data-analysis-export-natural-preview]')
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='scope'")
        _click(browser, '[data-analysis-export-next]')
        _wait(browser, "document.querySelector('.analysis-export-page').dataset.stage==='preview'&&!!document.querySelector('#analysis-export-confirm')")
        print(json.dumps({'status': 'PASS', 'parse_error_clear_revalidate': True,
                          'schema_error_replace_revalidate': True, 'mode_switch_revalidate': True,
                          'network_error_retry_without_edit': True, 'next_stage_preview': True,
                          'damaged_copy_guidance': True}))
    finally:
        if browser is not None:
            browser.close()
        _close_process(edge)
        _safe_cleanup(edge_data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--formal-probe', action='store_true')
    parser.add_argument('--expect-bug', action='store_true')
    args = parser.parse_args()
    if args.formal_probe:
        exercise(8766, args.expect_bug)
    else:
        with tempfile.TemporaryDirectory(prefix='fl-export-recovery-') as temporary:
            tracker, dictionary, backups, registry = ensure_sandbox(Path(temporary))
            service = LedgerWebService(tracker, dictionary, backups, data_module_registry_file=registry)
            server = create_server('127.0.0.1', 0, service)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                exercise(server.server_port, args.expect_bug)
            finally:
                server.shutdown()
                server.server_close()
