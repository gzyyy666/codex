@echo off
setlocal
cd /d "%~dp0\.."
python tools\run_data_module_pwa_review.py --open
endlocal
