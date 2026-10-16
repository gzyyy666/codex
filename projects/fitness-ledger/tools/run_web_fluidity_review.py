"""Serve current installed Web and a narrowly overlaid candidate on data copies.

The baseline source ref anchors only the candidate diff, not the installed UI.
No formal files, provider operations, or browser profiles are modified.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlparse

sys.dont_write_bytecode = True
PROJECT = Path(__file__).resolve().parents[1]
FILES = ['app.js', 'formal-mirror-data-modules.js', 'tools-css3d-panels.js', 'motion-lab/guardian/pet-guardian-static.js']


def apply_source_changes(base: str, candidate: str, installed: str) -> str:
    """Fail closed if a modified source region overlaps installed-only edits."""
    old, new = base.splitlines(keepends=True), candidate.splitlines(keepends=True)
    changes = list(difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes())
    for kind, start, end, nstart, nend in reversed(changes):
        if kind == 'equal':
            continue
        needle, replacement = ''.join(old[start:end]), ''.join(new[nstart:nend])
        if not needle:
            if not start or end == len(old):
                raise ValueError('Insertion must have stable surrounding context')
            needle = old[start-1] + old[end]
            replacement = old[start-1] + replacement + old[end]
        if installed.count(needle) > 1:
            # Identical helpers may occur in both language branches. Require
            # exact surrounding lines rather than choosing an arbitrary match.
            for context in range(1,4):
                lo, hi = max(0,start-context), min(len(old),end+context)
                extended = ''.join(old[lo:hi])
                if installed.count(extended) == 1:
                    needle = extended
                    replacement = ''.join(old[lo:start])+''.join(new[nstart:nend])+''.join(old[end:hi])
                    break
        if installed.count(needle) != 1:
            raise ValueError(f'Installed/source overlap: expected one unchanged region at source line {start+1}')
        installed = installed.replace(needle, replacement, 1)
    return installed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--formal', type=Path, default=Path(r'D:\FitnessLedger\app'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-ref', default='064548c4c1c31681f695e8ede02f1fba13d3d66c')
    parser.add_argument('--baseline-port', type=int, default=8876)
    parser.add_argument('--candidate-port', type=int, default=8877)
    args = parser.parse_args()
    formal, output = args.formal.resolve(), args.output.resolve()
    if output == formal or formal in output.parents or PROJECT in output.parents:
        raise ValueError('Review output must be outside formal and source directories')
    output.mkdir(parents=True, exist_ok=True)
    frontend = formal/'web_desktop/frontend'
    source_commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=PROJECT,text=True).strip()
    installed_info = json.loads((formal/'web_desktop/runtime_build_info.json').read_text(encoding='utf-8-sig'))
    installed_commit = installed_info.get('commit_sha','')
    overlay = output/'frontend';overlay.mkdir(exist_ok=True)
    fingerprints = {}
    for name in FILES:
        installed = (frontend/name).read_text(encoding='utf-8-sig')
        path = 'projects/fitness-ledger/web_desktop/frontend/'+name
        base = subprocess.check_output(['git', 'show', args.baseline_ref+':'+path], cwd=PROJECT).decode('utf-8-sig').replace('\r\n','\n')
        candidate = (PROJECT/'web_desktop/frontend'/name).read_text(encoding='utf-8-sig')
        merged = apply_source_changes(base, candidate, installed)
        target = overlay/name;target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(merged, encoding='utf-8', newline='')
        fingerprints[name] = {'installed':hashlib.sha256(installed.encode()).hexdigest(), 'candidate':hashlib.sha256(merged.encode()).hexdigest()}
    data = output/'data';data.mkdir(exist_ok=True)
    for name in ['tracker.json','movement_dictionary.json','data_module_definitions.json','data_check_state.json','phone_inbox.json']:
        origin=formal/'data'/name
        if origin.exists():
            shutil.copy2(origin,data/name)
            fingerprints['data/'+name] = hashlib.sha256(origin.read_bytes()).hexdigest()
    os.environ['FITNESS_LEDGER_FORMAL_DIR']=str(output)
    os.environ['FITNESS_LEDGER_DATA_MODULE_REGISTRY']=str(data/'data_module_definitions.json')
    sys.path.insert(0,str(formal))
    # Constructors and all read paths must remain unable to mutate the installation.
    formal_prefix = str(formal).lower()+os.sep
    def audit(event, values):
        if event == 'open' and isinstance(values[0],(str,bytes,os.PathLike)):
            mode, flags = values[1:3]
            writing = (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if writing and str(Path(os.fsdecode(values[0])).resolve()).lower().startswith(formal_prefix):
                raise PermissionError('Review cannot write formal files')
        if event in ('os.remove','os.rename','os.mkdir','os.rmdir'):
            for value in values[:2]:
                if isinstance(value,(str,bytes,os.PathLike)) and str(Path(os.fsdecode(value)).resolve()).lower().startswith(formal_prefix):
                    raise PermissionError('Review cannot mutate formal files')
    sys.addaudithook(audit)
    from web_desktop.backend import server as backend
    servers=[]
    for candidate, port in [(False,args.baseline_port),(True,args.candidate_port)]:
        class Handler(backend.LedgerRequestHandler):
            is_candidate=candidate
            def do_POST(self):
                self.send_json({'error':'体验预览仅支持浏览与输入，保存和云同步未启用。'},backend.HTTPStatus.METHOD_NOT_ALLOWED)
            def end_headers(self):
                self.send_header('Content-Security-Policy',"connect-src 'self'; script-src 'self' 'unsafe-inline'; object-src 'none'")
                super().end_headers()
            def send_file(self, path):
                relative=path.relative_to(frontend) if path.is_relative_to(frontend) else None
                if relative == Path('index.html'):
                    html=path.read_text(encoding='utf-8-sig')
                    if self.is_candidate:
                        source_index=(PROJECT/'web_desktop/frontend/index.html').read_text(encoding='utf-8-sig')
                        for module in ['app.js','formal-mirror-data-modules.js']:
                            reference=re.search(re.escape(module)+r'\?v=[^"\s]+',source_index)
                            if reference is None:raise ValueError('Missing candidate module reference')
                            html,count=re.subn(re.escape(module)+r'\?v=[^"\s]+',lambda _:reference.group(0),html)
                            if count != 1:raise ValueError('Expected one '+module)
                    label='优化版' if self.is_candidate else '当前版本对照'
                    html=html.replace('<body>',f'<body><div style="position:fixed;bottom:8px;left:12px;z-index:1000000;padding:6px 12px;background:#fff8df;border:1px solid #b49b63;border-radius:8px;font:12px sans-serif;pointer-events:none">{label} · 体验预览 · 保存和云同步未启用</div>')
                    self.send_bytes(html.encode('utf-8'),'text/html; charset=utf-8');return
                selected=overlay/relative if self.is_candidate and relative is not None else path
                super().send_file(selected if selected.is_file() else path)
        Handler.service=backend.LedgerWebService(data_file=data/'tracker.json',dictionary_file=data/'movement_dictionary.json',backup_dir=output/'backups',data_module_registry_file=data/'data_module_definitions.json',build_info_override={'commit_sha':source_commit if candidate else installed_commit,'short_sha':'REVIEW','status':'REVIEW_ONLY','label':'fluidity overlay on installed files' if candidate else 'installed baseline'})
        servers.append(backend.ExclusiveThreadingHTTPServer(('127.0.0.1',port),Handler))
    manifest={'source_base':args.baseline_ref,'source_commit':source_commit,'installed_commit':installed_commit,'source_worktree':str(PROJECT),'formal':str(formal),'fingerprints':fingerprints,'baseline_url':f'http://127.0.0.1:{args.baseline_port}','candidate_url':f'http://127.0.0.1:{args.candidate_port}','pid':os.getpid(),'writes_enabled':False,'cloud_enabled':False}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
    print(json.dumps({k:manifest[k] for k in ['baseline_url','candidate_url','pid']},ensure_ascii=False),flush=True)
    try:threading.Event().wait()
    except KeyboardInterrupt:pass
    finally:
        for server in servers:server.shutdown();server.server_close()

if __name__=='__main__':main()
