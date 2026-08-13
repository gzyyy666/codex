@echo off
setlocal
cd /d "%~dp0.."
python tools\run_data_module_candidate_preview.py --open
endlocal
