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
const bodyRows=[
  {Date:'2099-01-05','Weight (kg)':70.5,'Bowel Movement':'yes',Training:'Back','Cardio':'none',Notes:'body row five'},
  {Date:'2099-01-04','Weight (kg)':70.4,'Bowel Movement':'yes',Training:'Chest','Cardio':'walk',Notes:'body row four'},
  {Date:'2099-01-03','Weight (kg)':70.3,'Bowel Movement':'yes',Training:'Legs','Cardio':'bike',Notes:'body row three'},
  {Date:'2099-01-02','Weight (kg)':70.2,'Bowel Movement':'yes',Training:'Shoulders','Cardio':'none',Notes:'body row two'},
  {Date:'2099-01-01','Weight (kg)':70.1,'Bowel Movement':'yes',Training:'Arms','Cardio':'run',Notes:'body row one'}
];
const dietRows=[
  {Date:'2099-01-03','Calories (kcal)':2100,'Protein (g)':150,'Carbs (g)':240,'Fat (g)':70,'Food Summary':'rice beef eggs yogurt',Notes:'long stable note'}
];
const movements=[
  {movement_id:'MOV_VALID',display_name:'Valid Press',english_name:'Valid Press',muscle_group:'Chest',active:true},
  {movement_id:'MOV_EXCLUDED',display_name:'Excluded Row',english_name:'Excluded Row',muscle_group:'Back',active:true},
  {movement_id:'MOV_EMPTY',display_name:'Empty Row',english_name:'Empty Row',muscle_group:'Legs',active:true}
];
const historyById={
  MOV_VALID:{movement:movements[0],history:[{date:'2099-01-03',sets_lines:['80kg x 8 x 3']}],progress_history:[{date:'2099-01-03',sets_lines:['80kg x 8 x 3']}]},
  MOV_EXCLUDED:{movement:movements[1],history:[{date:'2099-01-02',sets_lines:['40kg x 12 x 2'],exclude_from_progress:true}],progress_history:[]},
  MOV_EMPTY:{movement:movements[2],history:[],progress_history:[]}
};
function ok(value){return {ok:true,status:200,json:async()=>value};}
window.fetch=async path=>{
  const url=String(path);
  if(url.includes('/api/today'))return ok({date:'2099-01-03'});
  if(url.includes('/api/recent'))return ok([]);
  if(url.includes('/api/body'))return ok(bodyRows);
  if(url.includes('/api/diet'))return ok(dietRows);
  if(url.includes('/api/training'))return ok([]);
  if(url.includes('/api/movements?'))return ok(movements);
  if(url.includes('/api/dictionary'))return ok([]);
  if(url.includes('/api/movement-groups'))return ok(['Chest','Back','Legs']);
  if(url.includes('/api/movement-history')){
    const id=new URL(url,location.href).searchParams.get('movement_id');
    return ok(historyById[id]||{history:[],progress_history:[]});
  }
  if(url.includes('/api/cloud-sync/status'))return ok({sync_status:'SYNCED'});
  if(url.includes('/api/archive-health'))return ok({status:'OK',issue_count:0});
  if(url.includes('/api/build-info'))return ok({status:'PREVIEW',short_sha:'polish'});
  if(url.includes('/api/undo-status'))return ok({available:false});
  return ok({});
};
"""
    assertions = r"""
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
const bodyToneOf=node=>[...node.classList].filter(name=>name.startsWith('tone-')||name.startsWith('body-offset-')).sort().join(' ');
await wait(220);
navigate('movements');
await wait(450);
const movementNames=[...document.querySelectorAll('.movement-tile strong')].map(node=>node.textContent.trim());
const movementIndexFiltersEmpty=JSON.stringify(movementNames)===JSON.stringify(['Valid Press']);
const movementCountLabel=document.querySelector('.result-count')?.textContent||'';
const movementCountUsesProgress=movementCountLabel.includes('1 movements');

navigate('body');
await wait(120);
const firstMap=Object.fromEntries([...document.querySelectorAll('.body-slip')].map(node=>[node.querySelector('.body-slip-date strong').textContent.trim(),bodyToneOf(node)]));
document.querySelector('#body-order').value='oldest';
document.querySelector('#body-order').dispatchEvent(new Event('change',{bubbles:true}));
await wait(80);
const secondMap=Object.fromEntries([...document.querySelectorAll('.body-slip')].map(node=>[node.querySelector('.body-slip-date strong').textContent.trim(),bodyToneOf(node)]));
const bodyStableAfterSort=Object.keys(firstMap).every(date=>firstMap[date]===secondMap[date]);
bodyRows.unshift({Date:'2099-01-06','Weight (kg)':70.6,'Bowel Movement':'yes',Training:'Rest','Cardio':'none',Notes:'new body row'});
document.querySelector('#body-order').value='recent';
renderBodyRows();
await wait(80);
const thirdMap=Object.fromEntries([...document.querySelectorAll('.body-slip')].map(node=>[node.querySelector('.body-slip-date strong').textContent.trim(),bodyToneOf(node)]));
const bodyStableAfterInsert=Object.keys(firstMap).every(date=>firstMap[date]===thirdMap[date]);
const bodyUsesStableClasses=[...document.querySelectorAll('.body-slip')].every(node=>/tone-(feature|training|rest|cardio|purple)/.test(node.className)&&node.className.includes('body-offset-'));
const bodyUsesMultipleWarmTones=[...document.querySelectorAll('.body-slip')].some(node=>node.classList.contains('tone-feature')||node.classList.contains('tone-training'));

navigate('diet');
await wait(80);
const dietReturnedToSlipOffset=[...document.querySelectorAll('.diet-slip')].every(node=>!node.className.includes('diet-tone-')&&!node.className.includes('diet-offset-'));

const report=document.createElement('div');
report.id='web-polish-report';
report.dataset.value=encodeURIComponent(JSON.stringify({movementIndexFiltersEmpty,movementCountUsesProgress,bodyStableAfterSort,bodyStableAfterInsert,bodyUsesStableClasses,bodyUsesMultipleWarmTones,dietReturnedToSlipOffset,movementNames,firstMap,secondMap,thirdMap}));
document.body.appendChild(report);
}catch(error){
  const report=document.createElement('div');
  report.id='web-polish-report';
  report.dataset.value=encodeURIComponent(JSON.stringify({error:String(error&&error.stack||error)}));
  document.body.appendChild(report);
}
"""
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-web-polish-browser-") as temp:
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
    match = re.search(r'id="web-polish-report" data-value="([^"]+)"', output)
    assert match, "Web polish report was not rendered."
    report = json.loads(unquote(match.group(1)))
    assert all(report[key] is True for key in (
        "movementIndexFiltersEmpty",
        "movementCountUsesProgress",
        "bodyStableAfterSort",
        "bodyStableAfterInsert",
        "bodyUsesStableClasses",
        "bodyUsesMultipleWarmTones",
        "dietReturnedToSlipOffset",
    )), report


def main() -> None:
    app = (PROJECT / "web_desktop/frontend/app.js").read_text(encoding="utf-8")
    css = (PROJECT / "web_desktop/frontend/styles.css").read_text(encoding="utf-8")
    assert "usage(m)>0&&fuzzyMatch(m,q)" in app
    assert "payload?.history?.[0]" not in app
    assert "function bodySlipKey(record)" in app
    assert "Math.random()" not in app
    assert "transform:scale(1.36)" not in css
    assert "object-fit:contain" in css
    assert ".diet-slip.diet-tone-0" not in css
    assert "body-offset-1" in css
    browser_contract()
    print("FITNESS_LEDGER_WEB_POLISH_UI_OK")


if __name__ == "__main__":
    main()
