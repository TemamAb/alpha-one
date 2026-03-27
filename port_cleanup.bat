@echo off
REM AlphaMarkA Port Cleanup & Reservation Script
echo Cleaning AlphaMarkA ports: 6379,8080,3000,8545,8547,8549...

set PORTS=6379 8080 3000 8545 8547 8549
for %%p in (%PORTS%) do (
    for /f "tokens=5" %%i in ('netstat -ano ^| findstr /C:":%%p" ^| findstr LISTENING') do taskkill /PID %%i /F 2>nul
)

REM Stop and remove all Docker containers (Windows Batch syntax)
docker version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('docker ps -q') do docker stop %%i 2>nul
    for /f "tokens=*" %%i in ('docker ps -aq') do docker rm %%i 2>nul
    docker system prune -f
) else (
    echo [!] Docker engine not running. Skipping container cleanup.
)

echo Verification...
netstat -ano | findstr /R ":6379 :8080 :3000 :8545 :8547 :8549"
echo Ports CLEAN ^& RESERVED for AlphaMarkA. Run: docker compose up -d
