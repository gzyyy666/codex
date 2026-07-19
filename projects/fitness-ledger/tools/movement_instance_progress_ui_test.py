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
  today:{date:'2099-01-05'},recent:[],body:[],diet:[],
  training:[],dictionary:[],movements:[{movement_id:'MOV_A',display_name:'Bench Press',english_name:'Bench Press',muscle_group:'Chest',active:true}],
  movementGroups:['Chest'],sync:{sync_status:'SYNCED'},build:{status:'PREVIEW',short_sha:'instance-test'}
});
let savedReview=null,updateRequests=[],archiveRefs=[
  {history_id:'history-main',movement_id:'MOV_A',display_name:'Bench Press',english_name:'Bench Press',muscle_group:'Chest',is_linkable:true,order:1,sets_lines:['100kg x 8 x 3'],notes:'main',exclude_from_progress:false,has_structured_sets:true},
  {history_id:'history-volume',movement_id:'MOV_A',display_name:'Bench Press',english_name:'Bench Press',muscle_group:'Chest',is_linkable:true,order:2,sets_lines:['60kg x 12 x 2'],notes:'volume',exclude_from_progress:true,has_structured_sets:true}
];
const parsePayload={review_id:'review-instance-1',review:{id:'review-instance-1',date:'2099-01-05',raw:'training: Bench Press',body:{},diet:{},training:{split:'Chest',standardized_summary:'Bench Press',notes:'',movements:[
  {name:'Bench Press',display_name:'Bench Press',movement_id:'MOV_A',order:1,sets:[{weight:100,reps:8,sets:3}],notes:'main',_review_action:'use',exclude_from_progress:false},
  {name:'Bench Press',display_name:'Bench Press',movement_id:'MOV_A',order:2,sets:[{weight:60,reps:12,sets:2}],notes:'volume',_review_action:'use',exclude_from_progress:false},
  {name:'Mystery Movement',display_name:'Mystery Movement',movement_id:'',order:3,sets:[],notes:'raw only',_review_action:'skip',exclude_from_progress:false}
] }},summary:{date:'2099-01-05',movement_count:3,progress_excluded_count:0},warnings:[],duplicates:{},mapping_options:[]};
function json(value){return {ok:true,status:200,json:async()=>value};}
window.confirm=()=>true;
window.fetch=async (path,options={})=>{
  const method=options.method||'GET',url=String(path),state=emptyState();
  if(method==='POST'&&url.includes('/api/parse'))return json(parsePayload);
  if(method==='POST'&&url.includes('/api/save')){
    savedReview=JSON.parse(options.body).review;
    archiveRefs=archiveRefs.map((ref,index)=>({...ref,exclude_from_progress:Boolean(savedReview.training.movements[index]?.exclude_from_progress)}));
    return json({ok:true,status:'CREATED',date:'2099-01-05',training_updated:true,saved_movements:3,working_sets:5,progress_excluded_count:1});
  }
  if(method==='POST'&&url.includes('/api/movement-history/update')){
    const payload=JSON.parse(options.body);updateRequests.push(payload);
    const ref=archiveRefs.find(row=>row.history_id===payload.history_id);
    if(ref&&typeof payload.values.exclude_from_progress==='boolean')ref.exclude_from_progress=payload.values.exclude_from_progress;
    return json({ok:true,status:'UPDATED',movement_id:payload.movement_id,history:{...ref,id:payload.history_id}});
  }
  if(url.includes('/api/training'))return json([{Date:'2099-01-05','No.':1,Split:'Chest',Notes:'',movement_refs:archiveRefs}]);
  if(url.includes('/api/movement-history'))return json({movement:{movement_id:'MOV_A',display_name:'Bench Press',english_name:'Bench Press',muscle_group:'Chest',active:true},history:archiveRefs.map(ref=>({id:ref.history_id,date:'2099-01-05',training_day:1,order:ref.order,sets_lines:ref.sets_lines,notes:ref.notes,exclude_from_progress:ref.exclude_from_progress})),progress_history:archiveRefs.filter(ref=>!ref.exclude_from_progress)});
  if(url.includes('/api/today'))return json(state.today);
  if(url.includes('/api/recent'))return json(state.recent);
  if(url.includes('/api/body'))return json(state.body);
  if(url.includes('/api/diet'))return json(state.diet);
  if(url.includes('/api/movements?'))return json(state.movements);
  if(url.includes('/api/dictionary'))return json(state.dictionary);
  if(url.includes('/api/movement-groups'))return json(state.movementGroups);
  if(url.includes('/api/cloud-sync/status'))return json(state.sync);
  if(url.includes('/api/archive-health'))return json({status:'OK',issue_count:0});
  if(url.includes('/api/build-info'))return json(state.build);
  if(url.includes('/api/undo-status'))return json({available:false});
  return json({});
};
"""
    assertions = r"""
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
await wait(180);
document.body.insertAdjacentHTML('beforeend','<textarea id="raw-entry">training: Bench Press</textarea>');
await parseWebEntry();
await wait(80);
const reviewToggles=[...document.querySelectorAll('[data-progress-review-toggle]')];
const reviewHasTwoIndependentToggles=reviewToggles.length===2;
const unknownIsSeparated=Boolean(document.querySelector('.instance-progress-note.is-unrecognized'));
reviewToggles[1].checked=false;
await saveWebReview();
await wait(120);
const savedTwoStates=savedReview?.training?.movements?.slice(0,2).map(row=>row.exclude_from_progress);
const saveCarriesInstanceState=JSON.stringify(savedTwoStates)===JSON.stringify([false,true]);
navigate('training');
await wait(160);
const archiveRows=[...document.querySelectorAll('[data-instance-progress-toggle]')];
const archiveKeepsBoth=archiveRows.length===2&&document.querySelectorAll('.training-movement-row-shell').length===2;
archiveRows[1].checked=true;
archiveRows[1].dispatchEvent(new Event('change',{bubbles:true}));
await wait(180);
const archiveEditUsesStableIds=updateRequests[0]?.movement_id==='MOV_A'&&updateRequests[0]?.history_id==='history-volume'&&updateRequests[0]?.values?.exclude_from_progress===false;
const archiveRowsAfter=[...document.querySelectorAll('[data-instance-progress-toggle]')];
archiveRowsAfter[1].checked=false;
archiveRowsAfter[1].dispatchEvent(new Event('change',{bubbles:true}));
await wait(180);
state.movementSelection='MOV_A';
await loadMovementFocus('MOV_A');
await wait(80);
const movementProgressChartLabelCount=document.querySelectorAll('.movement-progress-panel .chart-labels text').length;
const movementProgressChartFiltered=movementProgressChartLabelCount===1;
const movementTrajectoryEntries=[...document.querySelectorAll('.trajectory-entry')];
const movementTrajectoryFiltered=movementTrajectoryEntries.length===1&&movementTrajectoryEntries[0].textContent.includes('100kg x 8 x 3')&&!movementTrajectoryEntries[0].textContent.includes('60kg x 12 x 2');
document.querySelector('[data-movement-history-edit]')?.click();
await wait(40);
const editToggle=document.querySelector('#movement-history-form [name="exclude_from_progress"]');
const editControlVisible=Boolean(editToggle);
if(editToggle){editToggle.checked=false;await saveMovementHistory();}
await wait(160);
const historyEditUsesStableIds=updateRequests.some(row=>row.history_id==='history-main'&&row.values?.exclude_from_progress===true);
const report=document.createElement('div');report.id='movement-instance-report';report.dataset.value=encodeURIComponent(JSON.stringify({reviewHasTwoIndependentToggles,unknownIsSeparated,saveCarriesInstanceState,archiveKeepsBoth,archiveEditUsesStableIds,editControlVisible,historyEditUsesStableIds,movementProgressChartFiltered,movementTrajectoryFiltered,movementProgressChartLabelCount,updateRequests}));document.body.appendChild(report);
"""
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-instance-progress-browser-") as temp:
        page = Path(temp) / "index.html"
        page.write_text(index.replace(script, f'<script type="module">\n{harness}\n{app}\n{assertions}\n</script>'), encoding="utf-8")
        output = subprocess.run(
            [str(edge), "--headless=new", "--disable-gpu", "--virtual-time-budget=7000", "--dump-dom", page.as_uri()],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=35,
        ).stdout
    match = re.search(r'id="movement-instance-report" data-value="([^"]+)"', output)
    assert match, "Movement instance report was not rendered."
    report = json.loads(unquote(match.group(1)))
    assert all(report[key] is True for key in (
        "reviewHasTwoIndependentToggles", "unknownIsSeparated", "saveCarriesInstanceState",
        "archiveKeepsBoth", "archiveEditUsesStableIds", "editControlVisible", "historyEditUsesStableIds", "movementProgressChartFiltered", "movementTrajectoryFiltered",
    )), report


def main() -> None:
    app = (PROJECT / "web_desktop/frontend/app.js").read_text(encoding="utf-8")
    assert "data-progress-review-toggle" in app
    assert "data-instance-progress-toggle" in app
    assert "exclude_from_progress" in app
    assert "/api/movement-history/update" in app
    browser_contract()
    print("FITNESS_LEDGER_MOVEMENT_INSTANCE_PROGRESS_UI_OK")


if __name__ == "__main__":
    main()
