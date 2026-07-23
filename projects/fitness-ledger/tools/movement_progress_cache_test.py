from __future__ import annotations

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


def browser_contract() -> None:
    edge = edge_path()
    if edge is None:
        return
    index = (PROJECT / "web_desktop/frontend/index.html").read_text(encoding="utf-8")
    app = (PROJECT / "web_desktop/frontend/app.js").read_text(encoding="utf-8")
    script = '<script type="module" src="app.js"></script>'
    assert index.count(script) == 1
    harness = r"""
const emptyState=()=>({
  today:{date:'2099-01-01'},recent:[],body:[],diet:[],training:[],dictionary:[],
  movements:[{movement_id:'MOV_A',display_name:'Test Press',english_name:'Test Press',muscle_group:'Chest',active:true}],
  movementGroups:['Chest'],sync:{sync_status:'SYNCED'},build:{status:'PREVIEW',short_sha:'test'}
});
let historyRows=[{date:'2099-01-01',id:'h1',sets_lines:['10kg x 8 x 2']}];
let movementHistoryRequests=0,saveStatus='UPDATED',failSave=false,historyEditStatus='UPDATED';
window.confirm=()=>true;
window.fetch=async (path,options={})=>{
  const method=options.method||'GET';
  const url=String(path);
  const state=emptyState();
  if(method==='POST'&&url.includes('/api/save')){
    if(failSave)return {ok:false,status:500,json:async()=>({error:'save failed'})};
    if(saveStatus!=='NO_CHANGES')historyRows=[{date:'2099-01-02',id:'h2',sets_lines:['12kg x 8 x 2']},...historyRows];
    return {ok:true,status:200,json:async()=>({ok:true,status:saveStatus,training_updated:saveStatus!=='NO_CHANGES',saved_movements:saveStatus==='NO_CHANGES'?0:1,date:'2099-01-02'})};
  }
  if(method==='POST'&&url.includes('/api/movement-history/update')){
    if(historyEditStatus!=='NO_CHANGES')historyRows=[{date:'2099-01-03',id:'h3',sets_lines:['14kg x 8 x 2']}];
    return {ok:true,status:200,json:async()=>({ok:true,status:historyEditStatus,history:historyRows[0]})};
  }
  if(url.includes('/api/movement-history')){
    movementHistoryRequests++;
    return {ok:true,status:200,json:async()=>({movement:state.movements[0],history:historyRows,progress_history:historyRows})};
  }
  if(method==='POST'&&url.includes('/api/record/update')){
    return {ok:true,status:200,json:async()=>({ok:true,status:'UPDATED',training_updated:true})};
  }
  if(method==='POST'&&url.includes('/api/undo')){
    historyRows=[{date:'2099-01-01',id:'h1',sets_lines:['10kg x 8 x 2']}];
    return {ok:true,status:200,json:async()=>({ok:true,undone:true})};
  }
  if(url.includes('/api/today'))return {ok:true,status:200,json:async()=>state.today};
  if(url.includes('/api/recent'))return {ok:true,status:200,json:async()=>state.recent};
  if(url.includes('/api/body'))return {ok:true,status:200,json:async()=>state.body};
  if(url.includes('/api/diet'))return {ok:true,status:200,json:async()=>state.diet};
  if(url.includes('/api/training'))return {ok:true,status:200,json:async()=>state.training};
  if(url.includes('/api/movements?'))return {ok:true,status:200,json:async()=>state.movements};
  if(url.includes('/api/dictionary'))return {ok:true,status:200,json:async()=>state.dictionary};
  if(url.includes('/api/movement-groups'))return {ok:true,status:200,json:async()=>state.movementGroups};
  if(url.includes('/api/cloud-sync/status'))return {ok:true,status:200,json:async()=>state.sync};
  if(url.includes('/api/archive-health'))return {ok:true,status:200,json:async()=>({status:'OK',issue_count:0})};
  if(url.includes('/api/build-info'))return {ok:true,status:200,json:async()=>state.build};
  if(url.includes('/api/undo-status'))return {ok:true,status:200,json:async()=>({available:true})};
  return {ok:true,status:200,json:async()=>({})};
};
"""
    assertions = r"""
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
await wait(250);
navigate('movements');
await wait(350);
const initialRequests=movementHistoryRequests;
const initialLoaded=state.usageLoaded===true&&state.movementUsage.MOV_A.count===1;
navigate('movements');
await wait(120);
const cachedBrowsing=movementHistoryRequests===initialRequests;

document.body.insertAdjacentHTML('beforeend','<button data-review-save>Save</button>');
state.reviewPayload={review_id:'review-1',review:{training:{movements:[]}},duplicates:{}};
await saveWebReview();
const invalidatedAfterSave=state.usageLoaded===false&&Object.keys(state.movementUsage).length===0;
navigate('movements');
await wait(350);
const reloadedAfterSave=movementHistoryRequests>initialRequests&&state.usageLoaded===true&&state.movementUsage.MOV_A.count===2&&state.movementUsage.MOV_A.payload.history[0].date==='2099-01-02';

const requestsAfterReload=movementHistoryRequests;
state.reviewPayload={review_id:'review-2',review:{training:{movements:[]}},duplicates:{}};
saveStatus='NO_CHANGES';
await saveWebReview();
const noChangesKeptCache=state.usageLoaded===true&&movementHistoryRequests===requestsAfterReload;

state.reviewPayload={review_id:'review-3',review:{training:{movements:[]}},duplicates:{}};
failSave=true;
await saveWebReview();
const failureKeptCache=state.usageLoaded===true&&movementHistoryRequests===requestsAfterReload;
failSave=false;

state.movementSelection='MOV_A';
document.body.insertAdjacentHTML('beforeend','<form id="movement-history-form" data-movement-id="MOV_A" data-history-id="h2"><input name="sets_text" value="14kg x 8 x 2"></form><button data-movement-history-save>History</button>');
await saveMovementHistory();
const historyEditReloaded=state.usageLoaded===false&&state.movementUsage.MOV_A===undefined&&state.movementHistory.history[0].date==='2099-01-03';

await loadMovementUsage();
const requestsBeforeUndo=movementHistoryRequests;
await undoLastWebWrite();
const undoInvalidated=state.usageLoaded===false&&Object.keys(state.movementUsage).length===0&&movementHistoryRequests===requestsBeforeUndo;

const report=document.createElement('div');
report.id='movement-cache-report';
report.dataset.value=encodeURIComponent(JSON.stringify({
  initialLoaded,cachedBrowsing,invalidatedAfterSave,reloadedAfterSave,noChangesKeptCache,
  failureKeptCache,historyEditReloaded,undoInvalidated,requests:movementHistoryRequests
}));
document.body.appendChild(report);
"""
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-movement-cache-browser-") as temp:
        page = Path(temp) / "index.html"
        page.write_text(index.replace(script, f"<script type=\"module\">\n{harness}\n{app}\n{assertions}\n</script>"), encoding="utf-8")
        output = subprocess.run(
            [str(edge), "--headless=new", "--disable-gpu", "--virtual-time-budget=6000", "--dump-dom", page.as_uri()],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        ).stdout
    match = re.search(r'id="movement-cache-report" data-value="([^"]+)"', output)
    assert match, "Movement cache browser report was not rendered."
    report = json.loads(unquote(match.group(1)))
    assert all(value is True for key, value in report.items() if key != "requests"), report


def main() -> None:
    js = (PROJECT / "web_desktop/frontend/app.js").read_text(encoding="utf-8")
    assert "function invalidateMovementUsage()" in js
    assert "state.movementUsage={};state.usageLoaded=false;state.movementHistory=null" in js
    assert "if(result.status!=='NO_CHANGES'&&(result.training_updated||Number(result.saved_movements||0)>0))invalidateMovementUsage()" in js
    assert "if(result.status!=='NO_CHANGES')invalidateMovementUsage();await refreshWebState();await loadMovementFocus" in js
    assert "if(form.dataset.recordType==='training'&&result.status!=='NO_CHANGES')invalidateMovementUsage()" in js
    assert "await postApi('/api/undo',{});invalidateMovementUsage();await refreshWebState()" in js
    assert "state.usageLoaded=false" not in js.replace("state.movementUsage={};state.usageLoaded=false;state.movementHistory=null", "")
    browser_contract()
    print("FITNESS_LEDGER_MOVEMENT_PROGRESS_CACHE_OK")


if __name__ == "__main__":
    main()
