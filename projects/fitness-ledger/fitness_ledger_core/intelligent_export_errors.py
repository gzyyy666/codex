"""Stable, privacy-safe error taxonomy for the local-model export boundary."""

ERRORS = {
    "MODEL_UNAVAILABLE": {"user": "本地模型当前不可用。", "retry": True, "repair": False},
    "MODEL_BUSY": {"user": "本地模型正忙，请稍后重试。", "retry": True, "repair": False},
    "MODEL_TIMEOUT": {"user": "本地模型处理超时。", "retry": True, "repair": False},
    "MODEL_CONNECTION_ERROR": {"user": "本地模型连接中断。", "retry": True, "repair": False},
    "MODEL_EMPTY_RESPONSE": {"user": "本地模型没有返回结果。", "retry": True, "repair": True},
    "MODEL_INVALID_JSON": {"user": "本地模型返回格式不可读。", "retry": False, "repair": True},
    "MODEL_SCHEMA_INVALID": {"user": "本地模型返回未符合选择协议。", "retry": False, "repair": True},
    "MODEL_SELECTION_INVALID": {"user": "本地模型选择无法安全确认。", "retry": False, "repair": True},
    "MODEL_REPAIR_FAILED": {"user": "本地模型修复失败，已安全回退。", "retry": False, "repair": False},
    "MODEL_OUTPUT_TRUNCATED": {"user": "本地模型输出不完整，已安全回退。", "retry": True, "repair": True},
    "SOURCE_CHANGED": {"user": "导出期间数据发生变化，请重新尝试。", "retry": True, "repair": False},
    "PLAN_OVER_BUDGET": {"user": "请求超出本次导出预算。", "retry": False, "repair": True},
    "LOW_CONFIDENCE": {"user": "当前证据不足以安全生成分析。", "retry": False, "repair": False},
    "CANCELLED": {"user": "导出已取消。", "retry": False, "repair": False},
    "INTERNAL_ERROR": {"user": "导出内部处理失败，已安全回退。", "retry": False, "repair": False},
}


def error_info(code: str) -> dict:
    return {"code": code, **ERRORS.get(code, ERRORS["INTERNAL_ERROR"])}
