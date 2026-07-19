"""Error taxonomy, parser boundaries and task timeout checks."""
from __future__ import annotations
import sys, time, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from fitness_ledger_core.intelligent_export_errors import error_info
from fitness_ledger_core.intent_interpreter import parse_json_object
from fitness_ledger_core.intelligent_export_models import ContractError
from fitness_ledger_core.local_model_adapter import FakeLocalModelAdapter, ModelCallResult, ModelConfig

class SlowAdapter(FakeLocalModelAdapter):
    def generate_json(self, **kwargs):
        time.sleep(.05); return super().generate_json(**kwargs)

def main():
    assert parse_json_object('{"ok":true}') == {"ok": True}
    for raw, code in (("", "MODEL_EMPTY_RESPONSE"), ("{", "MODEL_OUTPUT_TRUNCATED"), ("not json", "MODEL_INVALID_JSON")):
        try: parse_json_object(raw)
        except ContractError as exc: assert exc.code == code
        else: raise AssertionError(code)
    for code in ("MODEL_TIMEOUT","MODEL_CONNECTION_ERROR","MODEL_SELECTION_INVALID","MODEL_REPAIR_FAILED","SOURCE_CHANGED","CANCELLED"):
        info=error_info(code); assert info["code"]==code and isinstance(info["user"],str) and "tracker" not in info["user"]
    cfg=ModelConfig(.05,4096,800,1,keep_alive="2m",ensure_ascii=True); assert cfg.keep_alive=="2m" and cfg.ensure_ascii
    result=SlowAdapter([{"ok":True}]).generate_json(system_prompt="x",user_payload={},response_schema={"type":"object"},config=cfg); assert isinstance(result,ModelCallResult)
    print("FITNESS_LEDGER_INTELLIGENT_EXPORT_ERRORS_OK")
if __name__=="__main__": main()
