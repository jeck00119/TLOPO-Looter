# Building TLOPO Looter as Single Executable

This guide explains how to build TLOPO Looter as a single `.exe` file with all assets bundled.

## Prerequisites

1. **Python 3.8 or higher** installed
2. **All dependencies installed** from requirements.txt

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- PyQt5 (GUI framework)
- opencv-python (Computer vision)
- numpy (Image processing)
- pywin32 (Windows API)
- psutil (Process utilities)
- pyttsx3 (Text-to-speech)
- pyinstaller (Build tool)

## Step 2: Build the Executable

Simply run the build script:

```bash
python build.py
```

The script will:
1. Check if PyInstaller is installed (offer to install if missing)
2. Clean old build files
3. Build the executable using the spec file
4. Verify the build was successful
5. Show a summary with file size

## Step 3: Find Your Executable

After a successful build, you'll find:

```
dist/TLOPO_Looter.exe
```

This is a **single executable file** that includes:
- All Python code (bot_logic.py, main_gui.py, etc.)
- All template images (img folder)
- GIF animations (pirate_chest.gif, pirates_skull.gif)
- Application icon
- All dependencies (PyQt5, OpenCV, etc.)

## Distribution

You can distribute the single `TLOPO_Looter.exe` file to other computers without requiring:
- Python installation
- pip packages
- img folder (it's bundled inside)
- Any other files

**Note:** The exe will create a `Data/` folder next to itself for storing screenshots.

## Troubleshooting

### Build Failed
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Try deleting `build/` and `dist/` folders manually and rebuild
- Check that `img/` folder and `icon.ico` exist

### Exe Won't Run
- The exe is only compatible with Windows
- Antivirus might flag it (false positive, add to exclusions)
- Run from a location with write permissions (for Data folder)

### Large File Size
- Single-file executables are larger (50-150 MB is normal)
- PyQt5 and OpenCV add significant size
- This is expected for bundled applications

## Technical Details

### Spec File Configuration
The build uses `main_gui.spec` which configures:
- **onefile=True**: Single executable (not a folder)
- **console=False**: No console window (GUI only)
- **icon**: Application icon from icon.ico
- **datas**: Bundles img/ folder and icon.ico
- **hiddenimports**: Includes pyttsx3 drivers
- **upx=True**: Compresses executable (smaller size)

### What Happens When Exe Runs
1. PyInstaller extracts bundled files to a temporary folder (`_MEIPASS`)
2. Bot reads templates from the temporary img folder
3. Bot creates Data folder next to the exe for screenshots
4. When exe closes, temporary files are cleaned up

### Resource Path Function
The bot uses `resource_path()` in bot_logic.py to locate bundled files:
- In development: Reads from local img folder
- In exe: Reads from temporary _MEIPASS folder
- This is handled automatically by PyInstaller
