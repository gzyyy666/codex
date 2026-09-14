"""Contracts for Session filtering and optional Web effects."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote


PROJECT = Path(__file__).resolve().parents[1]


def edge_path() -> Path | None:
    for root in (os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMFILES", "")):
        candidate = Path(root) / "Microsoft/Edge/Application/msedge.exe"
        if candidate.is_file():
            return candidate
    return None


def browser_contract(app: str) -> None:
    edge = edge_path()
    if edge is None:
        return
    index = (PROJECT / "web_desktop/frontend/index.html").read_text(encoding="utf-8")
    script = re.search(r'<script type="module" src="app\.js(?:\?[^" ]+)?"></script>', index).group(0)
    harness = """
const ok=value=>({ok:true,status:200,json:async()=>value});let testSync=false,syncStatusReads=0;
window.fetch=async path=>{const url=String(path);
 if(url.includes('/api/training-organization'))return ok({session_themes:[{theme_id:'theme:push',display_name:'Push',active:true}],movement_categories:[]});
 if(url.includes('/api/training'))return ok([{Date:'2099-01-02',session_theme_ids:[],movement_refs:[]},{Date:'2099-01-01',session_theme_ids:['theme:push'],movement_refs:[]}]);
 if(url.includes('/api/cloud-sync/status')){if(!testSync)return ok({sync_status:'SYNCED'});syncStatusReads++;return ok({sync_status:syncStatusReads>=3?'SYNCED':'LOCAL_NEWER',auto_sync_enabled:true,upload_provider_ready:true})}
 if(url.includes('/api/cloud-sync/sync')){const error=Error('simulated timeout');error.name='AbortError';throw error}
 if(url.includes('/api/archive-health'))return ok({status:'OK',issue_count:0});
 if(url.includes('/api/build-info'))return ok({status:'PREVIEW'});
 if(url.includes('/api/undo-status'))return ok({available:false});
 return ok([])};
"""
    assertions = """
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
await wait(250);navigate('training');await wait(80);
const themeLabels=[...document.querySelectorAll('.theme-cn')].map(node=>node.textContent.trim());
navigate('tools');await wait(80);
const switches=[...document.querySelectorAll('[data-web-effect]')];
const switchesInRail=switches.every(node=>node.closest('.admin-workspace-rail'));
const cursor=switches.find(node=>node.dataset.webEffect==='trophyCursor');cursor.click();await wait(20);
testSync=true;syncStatusReads=0;const syncOutcome=await autoSyncAfterSave(),autoSyncStatusReads=syncStatusReads;
navigate('home');await wait(80);const homeText=document.querySelector('.home-page')?.innerText||'';
navigate('quick');await wait(80);const quickText=document.querySelector('.entry-page')?.innerText||'';
navigate('training');await wait(80);const trainingText=document.querySelector('.training-theme-page')?.innerText||'';
navigate('body');await wait(80);
navigate('tools',{panel:'sync'});await wait(120);const cloud=document.querySelector('.cloud-sync-business'),cloudText=cloud?.innerText||'';
const result={themeLabels,switchCount:switches.length,switchesInRail,cursorStored:localStorage.getItem('fitness-ledger.web-effect.trophy-cursor.v1'),cursorDataset:document.documentElement.dataset.flTrophyCursor,syncStatus:syncOutcome.status,reconciled:syncOutcome.reconciled,autoSyncStatusReads,homeBilingual:homeText.includes('LOCAL FITNESS JOURNAL')&&homeText.includes('记录今天')&&homeText.includes('查看动作档案'),quickBilingual:quickText.includes('Write the day.')&&quickText.includes('识别并复核')&&quickText.includes('撤销上次保存'),trainingChinese:trainingText.includes('训练记录')&&trainingText.includes('最新训练在前'),cloudBusiness:Boolean(cloud),cloudHasUserStatus:Boolean(cloud?.querySelector('.cloud-sync-user-grid')),cloudHidesRoute:Boolean(!cloud?.querySelector('.admin-route-track')&&!cloud?.querySelector('.admin-verification-panel')),cloudAdvancedClosed:Boolean(cloud?.querySelector('.cloud-sync-advanced:not([open])')),cloudBilingual:cloudText.includes('Cloud Sync')&&cloudText.includes('本地记录')&&cloudText.includes('云端副本')&&cloudText.includes('手机端读取')};
const report=document.createElement('div');report.id='web-session-effects-report';report.dataset.value=encodeURIComponent(JSON.stringify(result));document.body.appendChild(report);
"""
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-web-effects-") as temp:
        page = Path(temp) / "index.html"
        page.write_text(index.replace(script, f'<script type="module">\n{harness}\n{app}\n{assertions}\n</script>'), encoding="utf-8")
        output = subprocess.run([str(edge), "--headless=new", "--disable-gpu", "--virtual-time-budget=3000", "--dump-dom", page.as_uri()], check=True, capture_output=True, text=True, encoding="utf-8", timeout=25).stdout
    match = re.search(r'id="web-session-effects-report" data-value="([^"]+)"', output)
    assert match, "Web effects report was not rendered"
    result = json.loads(unquote(match.group(1)))
    assert result == {"themeLabels": ["Push"], "switchCount": 2, "switchesInRail": True, "cursorStored": "off", "cursorDataset": "off", "syncStatus": "SYNCED", "reconciled": True, "autoSyncStatusReads": 3, "homeBilingual": True, "quickBilingual": True, "trainingChinese": True, "cloudBusiness": True, "cloudHasUserStatus": True, "cloudHidesRoute": True, "cloudAdvancedClosed": True, "cloudBilingual": True}, result


def main() -> None:
    app = (PROJECT / "web_desktop/frontend/app.js").read_text(encoding="utf-8")
    pet = (PROJECT / "web_desktop/frontend/tools-css3d-panels.js").read_text(encoding="utf-8")
    css = (PROJECT / "web_desktop/frontend/final-pass.css").read_text(encoding="utf-8")
    index = (PROJECT / "web_desktop/frontend/index.html").read_text(encoding="utf-8")
    mirror = (PROJECT / "web_desktop/frontend/formal-mirror-data-modules.js").read_text(encoding="utf-8")

    active_ids = app.split("trainingThemeIds=function()", 1)[1].split("sessionThemeRows=function", 1)[0]
    assert "ids.push('__unthemed__')" not in active_ids
    assert "sessionThemeMembership(record).size===0" not in active_ids
    assert "data-web-effect=\"guardian\"" in app
    assert "data-web-effect=\"trophyCursor\"" in app
    assert "fitness-ledger.web-effect.guardian.v1" in app
    assert "fitness-ledger.web-effect.trophy-cursor.v1" in app
    assert "fitness-ledger-effects:change" in pet
    assert "data-fl-guardian-pet=\"off\"" in css
    assert "data-fl-trophy-cursor=\"off\"" in css
    assert "app.js?v=20260914-web-controls-r8" in index
    assert "formal-mirror-data-modules.js?v=20260914-v42" in index
    assert "final-pass.css?v=20260914-web-controls-r7" in index
    assert "搜索备注、饮食内容或日期…" in app
    assert "饮食摘要" in app
    assert "查看详情" in app
    assert "data-ui-language-toggle" in app
    assert "UI_LANGUAGE_PREF" in app
    assert ".collectiveos-dashboard{min-height:0!important;align-content:start!important}" in css
    assert "archive-title-cn" in app
    assert "tools-css3d-panels.js?v=20260913-web-controls-r1" in app
    assert "搜索备注或日期…" in app
    assert "全部时间" in app
    assert "打开记录" in app
    assert "shellLocaleObserver" not in app
    assert "document.documentElement.dataset.flUiLanguage==='en'" in mirror
    browser_contract(app)
    print("FITNESS_LEDGER_WEB_SESSION_EFFECTS_OK")


if __name__ == "__main__":
    main()
