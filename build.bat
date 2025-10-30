@echo off
REM ============================================
REM TLOPO Looter - Build Script
REM Creates a single executable with all assets
REM ============================================

echo.
echo ========================================
echo    TLOPO Looter - Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [ERROR] PyInstaller is not installed!
    echo.
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller
        echo Please run: pip install pyinstaller
        pause
        exit /b 1
    )
)

echo [1/4] Cleaning old build files...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo      Done!
echo.

echo [2/4] Building executable with PyInstaller...
echo      This may take a few minutes...
echo.
pyinstaller main_gui.spec --clean
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)
echo.

echo [3/4] Verifying build...
if not exist "dist\TLOPO_Looter.exe" (
    echo [ERROR] Executable not found in dist folder!
    pause
    exit /b 1
)
echo      Build successful!
echo.

echo [4/4] Build complete!
echo.
echo ========================================
echo    Build Summary
echo ========================================
echo  Output: dist\TLOPO_Looter.exe
echo  Size:   %~z1
echo.
echo  The executable includes:
echo    - All Python code
echo    - img folder (templates + GIFs)
echo    - icon.ico
echo    - All dependencies
echo.
echo  You can now distribute TLOPO_Looter.exe
echo  as a standalone application!
echo ========================================
echo.

pause
