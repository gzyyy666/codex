"""Fail-closed one-call task fallback contract; no transport is started here."""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any
from .analysis_registry import TASK_REGISTRY, normalize_string_list

TASK_FALLBACK_SCHEMA_VERSION="fitness-ledger-task-fallback-v1"

@dataclass(frozen=True)
class TaskFallbackOutput:
    task_id:str; slots:dict[str,Any]; abstain:bool; missing_slot_names:list[str]; schema_version:str=TASK_FALLBACK_SCHEMA_VERSION
    @classmethod
    def from_dict(cls,value:Any):
        if not isinstance(value,dict): raise ValueError("task fallback must be object")
        allowed={"schema_version","task_id","slots","abstain","missing_slot_names"}
        if set(value)-allowed: raise ValueError("task fallback has unknown fields")
        if value.get("schema_version")!=TASK_FALLBACK_SCHEMA_VERSION: raise ValueError("task fallback schema version invalid")
        task_id=value.get("task_id","")
        if not isinstance(task_id,str) or task_id not in TASK_REGISTRY: raise ValueError("task_id is not registered")
        if not isinstance(value.get("slots"),dict): raise ValueError("slots must be object")
        if not isinstance(value.get("abstain"),bool): raise ValueError("abstain must be bool")
        missing=normalize_string_list(value.get("missing_slot_names",[]),"missing_slot_names")
        return cls(task_id,dict(value["slots"]),value["abstain"],missing)
    @classmethod
    def model_validate_json(cls,raw:str): return cls.from_dict(json.loads(raw))
    @staticmethod
    def json_schema():
        return {"type":"object","additionalProperties":False,"properties":{"schema_version":{"type":"string","const":TASK_FALLBACK_SCHEMA_VERSION},"task_id":{"type":"string","enum":sorted(TASK_REGISTRY)},"slots":{"type":"object"},"abstain":{"type":"boolean"},"missing_slot_names":{"type":"array","items":{"type":"string"}}},"required":["schema_version","task_id","slots","abstain","missing_slot_names"]}
