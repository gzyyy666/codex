"""Read-only Edge regression: a slow pet must not gate the page or stay blank."""
import argparse
import asyncio
import json
import time
from pathlib import Path

from playwright.async_api import async_playwright


async def until(page, expression, arg=None):
    # Poll through the debugger; the read-only preview deliberately forbids eval.
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if await page.evaluate(expression, arg):
            return
        await page.wait_for_timeout(100)
    raise AssertionError('Timed out: ' + expression)


async def run(args):
    report = {'url': args.url, 'checks': []}
    args.output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel='msedge', headless=not args.headed)
        context = await browser.new_context(viewport={'width': 1440, 'height': 900})
        page = await context.new_page()
        errors, textures, assets = [], [], []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: textures.append(m.text) if 'blob:' in m.text or "Couldn't load texture" in m.text else None)

        async def slow_model(route):
            assets.append(route.request.url)
            await asyncio.sleep(3)
            await route.continue_()

        await page.route('**/*.glb', slow_model)
        await page.goto(args.url + '/#training', wait_until='domcontentloaded')
        await page.wait_for_selector('#session-grid>article')
        assert await page.locator('#session-grid>article').count() > 0
        assert not await page.evaluate('Boolean(window.__fitnessLedgerGuardianPet?.getDiagnostics().readyNotified)'), 'Page waited for pet'
        report['checks'].append({'name': 'page-ready-before-slow-pet', 'page_ms': await page.evaluate('performance.now()')})
        await until(page, 'window.__fitnessLedgerGuardianPet?.getDiagnostics().readyNotified')
        await until(page, 'window.__fitnessLedgerGuardianPet?.getDiagnostics().render.triangles>0')
        await page.wait_for_timeout(1600)
        diagnostics = await page.evaluate('window.__fitnessLedgerGuardianPet.getDiagnostics()')
        assert diagnostics['loadedAssets'] == ['front_double_biceps'], diagnostics
        assert not errors, errors
        assert not textures, textures
        report['checks'].append({'name': 'slow-first-model-painted-with-textures', 'assets': assets.copy(), 'diagnostics': diagnostics})
        await page.locator('.tools-pet-guardian-canvas').screenshot(path=str(args.output / 'pet-textured.png'))

        before = diagnostics['render']['frame']
        await page.wait_for_timeout(500)
        assert await page.evaluate('window.__fitnessLedgerGuardianPet.getDiagnostics().render.frame') == before, 'Idle pet kept drawing'
        await page.evaluate("window.__fitnessLedgerGuardianPet.setPose('front_double_biceps',{immediate:true})")
        await page.wait_for_timeout(400)
        assert await page.evaluate('window.__fitnessLedgerGuardianPet.getDiagnostics().render.frame') == before, 'Unchanged pose restarted drawing'
        report['checks'].append({'name': 'idle-and-unchanged-pose-stop-drawing', 'pass': True})

        await page.evaluate("__fitnessLedgerFormalMirrorBridge.navigate('diet')")
        await page.wait_for_selector('#diet-rows>.diet-slip')
        assert await page.evaluate("window.__fitnessLedgerGuardianPet.getDiagnostics().renderer.poseId==='front_double_biceps'"), 'Page waited for next pose'
        await until(page, 'window.__fitnessLedgerGuardianPet.getDiagnostics().inFlightLoads>0')
        await until(page, "window.__fitnessLedgerGuardianPet.getDiagnostics().renderer.poseId==='standing'")
        await page.wait_for_timeout(250)
        d = await page.evaluate('window.__fitnessLedgerGuardianPet.getDiagnostics()')
        assert d['visibleRoots'] == 1 and d['render']['triangles'] > 0, d
        assert not errors and not textures, [errors, textures]
        report['checks'].append({'name': 'route-ready-before-next-pose-and-one-visible-model', 'pass': True})
        await page.close()
        page = await context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.route('**/*.glb', slow_model)
        await page.goto(args.url + '/#quick', wait_until='domcontentloaded')
        await page.wait_for_selector('.entry-page')
        assert not await page.evaluate('Boolean(window.__fitnessLedgerGuardianPet?.getDiagnostics().readyNotified)')
        await until(page, 'window.__fitnessLedgerGuardianPet?.getDiagnostics().readyNotified')
        await until(page, 'window.__fitnessLedgerGuardianPet?.getDiagnostics().render.triangles>0')
        assert not errors, errors
        report['checks'].append({'name': 'slow-neutral-pose-wakes-after-idle-window', 'pass': True})
        await context.close()
        await browser.close()
    (args.output / 'pet-loading-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8878')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--headed', action='store_true')
    asyncio.run(run(parser.parse_args()))
