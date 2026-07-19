"""One-request stage probe; prints no model text or user data."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from fitness_ledger_core.shared_view_models import LedgerViewModels
from fitness_ledger_core.local_model_adapter import OllamaNativeAdapter
from fitness_ledger_core.data_catalog import DataCatalogBuilder, MovementResolver
from fitness_ledger_core.intent_interpreter import IntentInterpreter
from fitness_ledger_core.candidate_cards import CandidateSummarizer
from fitness_ledger_core.export_planner import ExportPlanner
from fitness_ledger_core.intelligent_export_models import ContractError
from fitness_ledger_core.export_plan_assembler import ExportPlanAssembler
from fitness_ledger_core.export_plan_validator import ExportPlanValidator, PlanValidationError
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--formal-dir',required=True); ap.add_argument('--request',default='看看我最近减脂怎么样，训练有没有受影响'); a=ap.parse_args(); root=Path(a.formal_dir); v=LedgerViewModels(root/'data/tracker.json',root/'data/movement_dictionary.json'); adapter=OllamaNativeAdapter(); cat=DataCatalogBuilder(v).build(); out={}
    try:
        intent,ir=IntentInterpreter(adapter).interpret(a.request,{'date_range':cat.date_range,'modules':[],'budget_mode':'concise'}); out['intent']={'ok':True,'duration_ms':ir.duration_ms,'output_chars':ir.output_chars,'finish_reason':ir.finish_reason,'truncated':ir.truncated}
        package=CandidateSummarizer(cat,MovementResolver(v)).build(a.request,intent,'concise'); out['candidates']={'modules':len(package.modules),'movements':len(package.movements),'notes':len(package.notes),'records':len(package.candidate_records)}
        planner=ExportPlanner(adapter)
        try:
            selection,pr=planner.plan(a.request,intent,package); out['planning']={'ok':True,'duration_ms':pr.duration_ms,'output_chars':pr.output_chars,'finish_reason':pr.finish_reason,'truncated':pr.truncated,'needs_fallback':selection.needs_fallback,'modules':len(selection.selected_modules),'movements':len(selection.selected_movements),'notes':len(selection.selected_note_candidate_ids),'records':len(selection.selected_candidate_record_ids)}
            try:
                draft=ExportPlanAssembler(package).assemble(selection,a.request,intent); plan=ExportPlanValidator().validate(draft,package,a.request); out['validation']={'ok':True,'selected_modules':len(plan.selected_modules)}
            except PlanValidationError as exc: out['validation']={'ok':False,'error_code':exc.code}
        except Exception as exc:
            result=planner.last_result; out['planning']={'ok':False,'error_code':type(exc).__name__,'error':str(exc)[:160],'duration_ms':getattr(result,'duration_ms',0),'output_chars':getattr(result,'output_chars',0),'finish_reason':getattr(result,'finish_reason',''),'truncated':getattr(result,'truncated',False)}
    except Exception as exc: out['error']={'error_code':type(exc).__name__,'error':str(exc)[:160]}
    print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__': main()
