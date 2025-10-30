# Building TLOPO Looter Executable

This guide explains how to build a standalone `.exe` file for TLOPO Looter.

## Prerequisites

- Python 3.7+ installed
- All dependencies from `requirements.txt` installed

## Build Methods

### Method 1: Using the Batch Script (Recommended for Windows)

Simply double-click `build.bat` or run from command prompt:

```bash
build.bat
```

The script will:
1. Check if PyInstaller is installed (installs if missing)
2. Clean old build files
3. Build the executable
4. Show build summary

### Method 2: Using the Python Script

Run the Python build script:

```bash
python build.py
```

This method provides:
- Cross-platform compatibility
- Better error handling
- Interactive PyInstaller installation prompt

### Method 3: Manual Build

If you prefer to run PyInstaller manually:

```bash
# Install PyInstaller if not already installed
pip install pyinstaller

# Clean previous builds
rmdir /s /q build dist

# Build executable
pyinstaller main_gui.spec --clean
```

## Output

After successful build, you'll find:

```
dist/
└── TLOPO_Looter.exe    (Standalone executable)
```

The executable includes:
- All Python code (main_gui.py, bot_logic.py, vision.py, etc.)
- img/ folder with all templates and GIF animations
- icon.ico application icon
- All dependencies (PyQt5, OpenCV, NumPy, etc.)

## File Size

Expected file size: **~150-200 MB** (includes entire Python runtime + libraries)

## Distribution

The `TLOPO_Looter.exe` file is completely portable and can be:
- Copied to any Windows PC
- Run without Python installed
- Distributed as a single file

**Note:** The Data folder for screenshots will be created next to the .exe when the bot runs.

## Troubleshooting

### "PyInstaller not found"
Install it manually:
```bash
pip install pyinstaller
```

### Build fails with import errors
Make sure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Executable won't run
- Make sure Windows Defender isn't blocking it
- Check that icon.ico exists in the project folder
- Verify all files in img/ folder are present

### Large file size
This is normal! PyInstaller bundles:
- Python interpreter
- PyQt5 (large GUI framework)
- OpenCV (computer vision library)
- All other dependencies

To reduce size, you can:
- Use UPX compression (already enabled in spec file)
- Remove unused template images from img/ folder
