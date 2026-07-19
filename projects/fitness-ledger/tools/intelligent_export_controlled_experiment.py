"""Controlled Chinese/English Ollama experiment with privacy-safe stage metrics."""
from __future__ import annotations
import argparse, json, os, sys, time, uuid
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from fitness_ledger_core.candidate_cards import CandidateSummarizer
from fitness_ledger_core.data_catalog import DataCatalogBuilder, MovementResolver
from fitness_ledger_core.intelligent_export_models import intent_json_schema
from fitness_ledger_core.intent_interpreter import INTENT_SYSTEM_PROMPT, IntentInterpreter
from fitness_ledger_core.local_model_adapter import INTENT_MODEL_CONFIG, LocalModelError, OllamaNativeAdapter
from fitness_ledger_core.shared_view_models import LedgerViewModels

ZH="\u5206\u6790\u6700\u8fd1\u4f4e\u78b3\u662f\u5426\u5bfc\u81f4\u80f8\u90e8\u8bad\u7ec3\u8868\u73b0\u4e0b\u964d"
EN="Analyze whether recent low-carbohydrate intake is associated with a decline in chest training performance."

def meta(result, started, payload, config, error=""):
    return {"request_id": "req:"+uuid.uuid4().hex[:12], "wall_time_ms": int((time.monotonic()-started)*1000), "timeout_seconds": config.timeout, "payload_chars": len(json.dumps(payload,ensure_ascii=False)), "schema_chars": len(json.dumps(intent_json_schema(),ensure_ascii=False)), "num_ctx": config.num_ctx, "num_predict": config.num_predict, "temperature": config.temperature, "keep_alive": config.keep_alive, "output_chars": getattr(result,"output_chars",0), "response_bytes": getattr(result,"response_bytes",0), "response_keys": getattr(result,"response_keys",[]), "message_keys": getattr(result,"message_keys",[]), "finish_reason": getattr(result,"finish_reason",""), "truncated": getattr(result,"truncated",False), "load_duration_ns": getattr(result,"load_duration_ns",0), "prompt_eval_duration_ns": getattr(result,"prompt_eval_duration_ns",0), "eval_duration_ns": getattr(result,"eval_duration_ns",0), "error_code": error}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--formal-dir",default=os.environ.get("FITNESS_LEDGER_FORMAL_DIR","")); ap.add_argument("--enable",action="store_true"); a=ap.parse_args()
    if not a.enable: print(json.dumps({"status":"skipped","reason":"pass --enable"})); return
    root=Path(a.formal_dir); tracker=root/"data/tracker.json"; dictionary=root/"data/movement_dictionary.json"
    if not tracker.is_file() or not dictionary.is_file(): print(json.dumps({"status":"skipped","reason":"formal directory missing"})); return
    adapter=OllamaNativeAdapter(); health=adapter.health_check()
    if not health.get("available"):
        print(json.dumps({"status":"blocked","layer":"health_check","health":health},ensure_ascii=False)); return
    views=LedgerViewModels(tracker,dictionary); catalog=DataCatalogBuilder(views).build(); summary={"date_range":catalog.date_range,"modules":[{"module_id":m.module_id,"record_count":m.record_count} for m in catalog.modules],"budget_mode":"concise"}
    rows=[]
    for language,request in (("zh",ZH),("en",EN)):
        for variant,system,ascii_mode in (("A",INTENT_SYSTEM_PROMPT,False),("B","Return one JSON object only. Use concise Chinese values when the request is Chinese.",False),("C","Return one JSON object only. Keep schema keys in English and values concise.",True)):
            config=replace(INTENT_MODEL_CONFIG,ensure_ascii=ascii_mode,keep_alive=0); payload={"request":request,"today":"2026-07-19","available_date_range":summary["date_range"],"available_modules":[m["module_id"] for m in summary["modules"]],"budget_mode":"concise"}
            started=time.monotonic()
            try:
                result=adapter.generate_json(system_prompt=system,user_payload={**payload,"intent_schema":intent_json_schema()},response_schema=intent_json_schema(),config=config)
                rows.append({"language":language,"variant":variant,"status":"http_ok","metrics":meta(result,started,payload,config)})
            except LocalModelError as exc:
                rows.append({"language":language,"variant":variant,"status":"error","metrics":meta(None,started,payload,config,exc.code)})
            except Exception as exc:
                rows.append({"language":language,"variant":variant,"status":"error","metrics":meta(None,started,payload,config,type(exc).__name__)})
    print(json.dumps({"status":"complete","health":health,"candidate_counts":{"modules":len(catalog.modules),"movements":len(catalog.movements),"notes":len(catalog.notes),"records":len(catalog.candidate_records)},"rows":rows},ensure_ascii=False))
if __name__=="__main__": main()
