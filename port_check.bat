@echo off
REM Corrected AlphaMarkA Port Scanner - Fixed Syntax for Windows PowerShell/cmd
echo Scanning AlphaMarkA ports: 6379(Redis),8080(Dashboard),3000(internal),8545/47/49(Hardhat)...
netstat -ano | findstr /C:":6379" /C:":8080" /C:":3000" /C:":8545" /C:":8547" /C:":8549"
if %errorlevel% equ 0 (
    echo.
    echo [!] PORTS IN USE ^- Run port_cleanup.bat first!
    exit /b 1
) else (
    echo.
    echo [+] ALL PORTS CLEAN ^& READY for AlphaMarkA deployment!
)
echo Run: docker compose up -d

