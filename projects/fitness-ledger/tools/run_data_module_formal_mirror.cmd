@echo off
setlocal
cd /d "%~dp0.."
python tools\run_data_module_formal_mirror.py --open %*
endlocal
