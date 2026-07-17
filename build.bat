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

echo [1/5] Python found:
python --version
echo.

REM ---- 2. Check PyInstaller ----
echo [2/5] Checking PyInstaller...
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
echo [3/5] Checking icon...
if not exist "aquarium_app.ico" (
    echo [WARNING] aquarium_app.ico not found - building without icon.
    pause
    exit /b 1
)
echo Icon found: aquarium_app.ico
echo.

REM ---- 5. Clean previous build ----
echo [4/5] Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "aquarium_app.spec" del /q "aquarium_app.spec"
echo Done.
echo.

REM ---- 6. Build .exe ----
echo [5/5] Running PyInstaller (may take 1-3 minutes)...
echo.

python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name aquarium_app ^
    --clean ^
    --icon aquarium_app.ico ^
    --add-data "aquarium_app;aquarium_app" ^
    --add-data "aquarium_app.ico;." ^
    --hidden-import aquarium_app.db ^
    --hidden-import aquarium_app.gui ^
    --hidden-import aquarium_app.logic ^
    aquarium_app\__main__.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo Build completed.
echo.

REM ---- 7. Move exe ----
if not exist "dist\aquarium_app.exe" (
    echo [ERROR] dist\aquarium_app.exe not found.
    pause
    exit /b 1
)

move /y "dist\aquarium_app.exe" "." >nul
python -c "import os; os.replace('aquarium_app.exe', '\u0410\u043a\u0432\u0430\u0423\u0447\u0451\u0442.exe')"

REM ---- 8. Cleanup ----
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "aquarium_app.spec" del /q "aquarium_app.spec"

echo.
echo ============================================================
echo   DONE! Output: %CD%\aquarium_app.exe
echo ============================================================
echo.
pause
exit /b 0