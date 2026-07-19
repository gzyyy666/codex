"""Local HTTP contract tests: UTF-8, error layers, keep_alive and one slot."""
from __future__ import annotations
import json, socket, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from fitness_ledger_core.local_model_adapter import INTENT_MODEL_CONFIG, LocalModelError, ModelConfig, OllamaNativeAdapter

class State:
    def __init__(self): self.bodies=[]; self.active=0; self.max_active=0; self.mode="ok"
state=State()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        body=json.dumps({"models":[{"name":"fake"}]}).encode(); self.send_response(200); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get("Content-Length","0"))); state.bodies.append(raw)
        state.active+=1; state.max_active=max(state.max_active,state.active)
        try:
            if state.mode=="timeout": time.sleep(.15); return
            if state.mode=="abort": self.connection.shutdown(socket.SHUT_RDWR); self.connection.close(); return
            content="" if state.mode=="empty" else "{\"ok\":true}"
            result={"message":{"content":content},"done":True,"done_reason":"length" if state.mode=="truncated" else "stop","load_duration":11,"prompt_eval_duration":22,"eval_duration":33}
            body=json.dumps(result).encode(); self.send_response(200); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
        finally: state.active-=1

def main():
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start(); adapter=OllamaNativeAdapter(f"http://127.0.0.1:{server.server_port}")
    cfg=replace(INTENT_MODEL_CONFIG,timeout=1.0,keep_alive="2m")
    result=adapter.generate_json(system_prompt="Return JSON",user_payload={"request":"中文测试：低碳与训练"},response_schema={"type":"object"},config=cfg)
    sent=json.loads(state.bodies[-1].decode("utf-8")); assert "中文测试" in sent["messages"][1]["content"]; assert sent["keep_alive"]=="2m"; assert result.http_status==200 and result.load_duration_ns==11
    state.mode="empty"
    try: adapter.generate_json(system_prompt="x",user_payload={},response_schema={"type":"object"},config=cfg)
    except LocalModelError as exc: assert exc.code=="MODEL_EMPTY_RESPONSE"
    else: raise AssertionError("empty response not classified")
    state.mode="truncated"; result=adapter.generate_json(system_prompt="x",user_payload={},response_schema={"type":"object"},config=cfg); assert result.truncated and result.finish_reason=="length"
    state.mode="timeout"
    try: adapter.generate_json(system_prompt="x",user_payload={},response_schema={"type":"object"},config=replace(cfg,timeout=.03))
    except LocalModelError as exc: assert exc.code=="MODEL_TIMEOUT"
    else: raise AssertionError("timeout not classified")
    state.mode="abort"
    try: adapter.generate_json(system_prompt="x",user_payload={},response_schema={"type":"object"},config=cfg)
    except LocalModelError as exc: assert exc.code in {"MODEL_CONNECTION_ERROR","MODEL_UNAVAILABLE"}
    else: raise AssertionError("connection abort not classified")
    server.shutdown(); server.server_close(); print("FITNESS_LEDGER_INTELLIGENT_EXPORT_ADAPTER_OK")
if __name__=="__main__": main()
