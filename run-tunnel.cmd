@echo off
setlocal

where cloudflared >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set CLOUDFLARED_BIN=cloudflared
) else if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
    set CLOUDFLARED_BIN="C:\Program Files (x86)\cloudflared\cloudflared.exe"
) else if exist "C:\Program Files\cloudflared\cloudflared.exe" (
    set CLOUDFLARED_BIN="C:\Program Files\cloudflared\cloudflared.exe"
) else (
    echo [Error] cloudflared not found in PATH or standard Program Files directories.
    pause
    exit /b 1
)

if not exist "%~dp0cloudflared-config.yml" (
    echo [Warning] cloudflared-config.yml not found.
    echo Please copy cloudflared-config.example.yml to cloudflared-config.yml and fill in your details.
    pause
    exit /b 1
)

%CLOUDFLARED_BIN% tunnel --config "%~dp0cloudflared-config.yml" run
pause
