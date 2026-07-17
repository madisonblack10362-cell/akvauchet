@echo off
setlocal enableextensions
cd /d "%~dp0"

echo ============================================================
echo   Building Aquarium app (package version)
echo ============================================================
echo.

REM ---- 1. Check Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    echo Install Python 3.10+ from https://python.org and add it to PATH.
    echo.
    pause
    exit /b 1
)

echo [1/6] Python found:
python --version
echo.

REM ---- 2. Check PyInstaller ----
echo [2/6] Checking PyInstaller...
python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    echo PyInstaller not installed. Installing...
    python -m pip install --upgrade pip
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
) else (
    echo PyInstaller already installed.
)
echo.

REM ---- 3. Check source ----
if not exist "aquarium_app\__main__.py" (
    echo [ERROR] aquarium_app\__main__.py not found.
    echo Make sure aquarium_app/ package is in current folder.
    pause
    exit /b 1
)

REM ---- 4. Check icon ----
echo [3/6] Checking icon...
if not exist "aquarium_app.ico" (
    echo [WARNING] aquarium_app.ico not found - building without icon.
    pause
    exit /b 1
)
echo Icon found: aquarium_app.ico
echo.

REM ---- 5. Delete old .exe BEFORE build ----
echo [4/6] Deleting old .exe...
if exist "aquarium_app.exe" del /f /q "aquarium_app.exe"
python -c "import os; os.path.exists('\u0410\u043a\u0432\u0430\u0423\u0447\u0451\u0442.exe') and os.remove('\u0410\u043a\u0432\u0430\u0423\u0447\u0451\u0442.exe')"
echo Done.
echo.

REM ---- 6. Clean previous build ----
echo [5/6] Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "aquarium_app.spec" del /q "aquarium_app.spec"
echo Done.
echo.

REM ---- 7. Build .exe ----
echo [6/6] Running PyInstaller (may take 1-3 minutes)...
echo.

python -c "import PyInstaller.__main__, os; args=['--noconfirm','--onefile','--windowed','--name','aquarium_app','--clean','--icon','aquarium_app.ico','--add-data','aquarium_app;aquarium_app']; os.path.exists('icon.png') and args.extend(['--add-data','icon.png;.']); os.path.exists('icon_sidebar.png') and args.extend(['--add-data','icon_sidebar.png;.']); os.path.exists('icon_sidebar_large.png') and args.extend(['--add-data','icon_sidebar_large.png;.']); args.extend(['--hidden-import','aquarium_app.db','--hidden-import','aquarium_app.gui','--hidden-import','aquarium_app.logic']); args.append('aquarium_app\\__main__.py'); PyInstaller.__main__.run(args)"

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    echo See output above for details.
    pause
    exit /b 1
)

echo.
echo Build completed.
echo.

REM ---- 8. Move and rename .exe ----
if not exist "dist\aquarium_app.exe" (
    echo [ERROR] dist\aquarium_app.exe not found after build.
    pause
    exit /b 1
)

move /y "dist\aquarium_app.exe" "." >nul
python -c "import os; os.replace('aquarium_app.exe', '\u0410\u043a\u0432\u0430\u0423\u0447\u0451\u0442.exe')"

REM ---- 9. Cleanup ----
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "aquarium_app.spec" del /q "aquarium_app.spec"

REM ---- 10. Refresh Windows icon cache ----
echo.
echo Refreshing Windows icon cache...
taskkill /f /im explorer.exe >nul 2>&1
timeout /t 1 >nul
start explorer.exe
echo Done.

echo.
echo ============================================================
echo   DONE!
echo.
echo   If icon still looks OLD in Explorer:
echo     1. Press F5 in Explorer to refresh
echo     2. Or: delete IconCache.db in %%LOCALAPPDATA%%
echo     3. Or: restart the computer
echo ============================================================
echo.
pause
exit /b 0