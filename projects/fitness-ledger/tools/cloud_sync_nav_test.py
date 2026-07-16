from __future__ import annotations

import json
import subprocess
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
INDEX = PROJECT / "web_desktop" / "frontend" / "index.html"
APP = PROJECT / "web_desktop" / "frontend" / "app.js"
STYLES = PROJECT / "web_desktop" / "frontend" / "styles.css"


def browser_logic_contract(app: str) -> None:
    start = app.index("function updateSyncNav(){")
    end = app.index("function showSaveReceipt", start)
    function = app[start:end]
    script = f"""
const marker={{hidden:true,className:'health-nav-status sync-nav-status',textContent:''}};
const nav={{
  hidden:true,title:'',ariaLabel:'',
  querySelector:()=>marker,
  removeAttribute:name=>{{if(name==='title')nav.title=''}},
  setAttribute:(name,value)=>{{if(name==='aria-label')nav.ariaLabel=value}}
}};
const $=selector=>selector==='[data-sync-nav-entry]'?nav:null;
const state={{syncStatus:null}};
{function}
function snap(code){{
  state.syncStatus={{sync_status:code}};
  updateSyncNav();
  return {{hidden:nav.hidden,markerHidden:marker.hidden,text:marker.textContent,className:marker.className,title:nav.title,ariaLabel:nav.ariaLabel}};
}}
const values=['SYNCED','LOCAL_NEWER','UPLOAD_FAILED','CLOUD_MISMATCH','NO_CHANGES','LOCAL_NEWER','SYNCED'].map(snap);
console.log(JSON.stringify(values));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    synced, pending, failed, mismatch, no_changes, repeated, final = json.loads(
        completed.stdout
    )
    assert synced["hidden"] is True and synced["text"] == ""
    assert pending["hidden"] is False and pending["text"] == "•"
    assert "sync-pending" in pending["className"]
    assert pending["title"] == "本地记录尚未同步到只读云副本"
    assert failed["hidden"] is False and failed["text"] == "!"
    assert mismatch["text"] == "!" and "sync-error" in mismatch["className"]
    assert no_changes["hidden"] is True
    assert repeated == pending
    assert final == synced


def main() -> None:
    index = INDEX.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    styles = STYLES.read_text(encoding="utf-8")
    assert index.count("data-sync-nav-entry") == 1
    assert index.count("data-health-nav-entry") == 1
    assert "data-cloud-sync-open data-sync-nav-entry" in index
    assert "privacy-signals" in index
    assert "function updateSyncNav()" in app
    assert "state.syncStatus=state.cloudSync" in app
    assert "navigate('cloud-sync')" in app
    assert ".sync-nav-status.sync-pending" in styles
    assert ".sync-nav-status.sync-error" in styles
    assert ".privacy-signals" in styles
    browser_logic_contract(app)
    print("FITNESS_LEDGER_CLOUD_SYNC_NAV_OK")


if __name__ == "__main__":
    main()
