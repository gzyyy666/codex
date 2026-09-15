from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


def function_source(source: str, name: str) -> str:
    match = re.search(rf"^function {re.escape(name)}\([^\n]*\)\{{.*?^\}}", source, re.M | re.S)
    assert match, f"Missing {name} in Web app bundle."
    return match.group(0)


def main() -> None:
    source = (PROJECT / "web_desktop/frontend/app.js").read_text(encoding="utf-8")
    metrics = function_source(source, "movementRecordMetrics")
    chart = function_source(source, "movementProgressChart")
    script = f"""
const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('\\"','&quot;');
{metrics}
{chart}
const complexOld={{date:'2099-01-04',sets_lines:['7.5kg × 6 + 5kg × 8 × 3组'],metrics:{{max_weight:7.5,total_reps:42,volume:255,has_structured_sets:true,has_complex_sets:true,scalar_metric_eligible:false}}}};
const regular={{date:'2099-01-05',sets_lines:['20kg × 10 × 2'],metrics:{{max_weight:20,total_reps:20,volume:400,has_structured_sets:true,has_complex_sets:false,scalar_metric_eligible:true}}}};
const complexNew={{date:'2099-01-06',sets_lines:['10kg × 8 + 7.5kg × 6 × 2组'],metrics:{{max_weight:10,total_reps:28,volume:250,has_structured_sets:true,has_complex_sets:true,scalar_metric_eligible:false}}}};
const superset={{date:'2099-01-07',sets_lines:['90kg × 12 × 3'],metrics:{{max_weight:90,total_reps:36,volume:3240,has_structured_sets:true,has_complex_sets:false,scalar_metric_eligible:true}},organization_relations:[{{type:'superset',members:['press','pushdown'],co_members:[{{movement_id:'pushdown',sets_lines:['30kg × 12 × 3']}}]}}]}};
const mixed=movementProgressChart([superset,complexNew,regular,complexOld]);
const complexOnly=movementProgressChart([complexOld]);
const supersetOnly=movementProgressChart([superset]);
const fallback=movementRecordMetrics({{sets_lines:['7.5kg × 6 + 5kg × 8 × 3组']}});
const lineValues=Array.from(mixed.matchAll(/<circle data-chart-value="([^\"]+)" data-chart-capacity="([^\"]+)"/g),match=>[Number(match[1]),Number(match[2])]);
const barValues=Array.from(mixed.matchAll(/<rect data-chart-value="([^\"]+)"/g),match=>Number(match[1]));
const dates=Array.from(mixed.matchAll(/<text[^>]*>([^<]+)<\\/text>/g),match=>match[1]);
const overflowSupersets=Array.from({{length:9}},(_,index)=>({{...superset,date:'2099-02-'+String(20-index).padStart(2,'0')}}));
const olderStandalone=movementProgressChart([...overflowSupersets,complexOld]);
console.log(JSON.stringify({{
  mixedLineAndCapacity:[lineValues,barValues,dates],
  complexOnlyKeepsBothMetrics:complexOnly.includes('data-chart-metric="load"')&&complexOnly.includes('data-chart-value="7.5"')&&complexOnly.includes('data-chart-capacity="255"')&&complexOnly.includes('<rect data-chart-value="255"'),
  supersetRecordExcluded:!mixed.includes('3240')&&!mixed.includes('01-07')&&supersetOnly.includes('is-empty'),
  olderStandaloneFillsRecentEligibleWindow:olderStandalone.includes('data-chart-value="7.5"')&&olderStandalone.includes('01-04'),
  textFallbackCapacity:fallback.volume,
  textFallbackReps:fallback.totalReps,
  textFallbackMaxWeight:fallback.maxLoad,
  textFallbackComplex:fallback.complex
}}));
"""
    result = subprocess.run(["node", "-e", script], cwd=PROJECT, check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    report = json.loads(result.stdout)
    assert report["mixedLineAndCapacity"] == [[[7.5, 255], [20, 400], [10, 250]], [255, 400, 250], ["01-04", "01-05", "01-06"]], report
    assert report["complexOnlyKeepsBothMetrics"] is True, report
    assert report["supersetRecordExcluded"] is True, report
    assert report["olderStandaloneFillsRecentEligibleWindow"] is True, report
    assert len(re.findall(r"filter\(record=>!record\.superset&&record\.structured", source)) == 2, source
    assert report["textFallbackCapacity"] == 255 and report["textFallbackReps"] == 42 and report["textFallbackMaxWeight"] == 7.5 and report["textFallbackComplex"] is True, report
    print("MOVEMENT_PROGRESS_COMPLEX_VOLUME_SUPERSET_EXCLUSION_OK")


if __name__ == "__main__":
    main()
