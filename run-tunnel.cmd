@echo off
setlocal

set http_proxy=http://127.0.0.1:7897
set https_proxy=http://127.0.0.1:7897

"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --config "%~dp0cloudflared-config.yml" run
pause
