# TLOPO Looter

An automated bot for "The Legend of Pirates Online [BETA]" that uses computer vision to detect and collect loot, engage enemies, and track legendary items.

## Features

- **Automated Loot Collection**: Detects loot prompts and automatically collects items
- **Enemy Detection & Combat**: Identifies enemy health bars and engages in combat
- **Legendary Item Tracking**: Detects legendary loot using HSV color filtering and saves screenshots
- **Modern PyQt5 GUI**: Real-time statistics, event logging, and easy-to-use controls
- **Statistics Tracking**: Tracks loot opened, legendaries found, and total running time
- **Configurable Settings**: Adjustable attack delays and spawn wait times
- **Text-to-Speech Feedback**: Audio notifications for bot events
- **Portable Executable**: Build as a single .exe file for easy distribution
- **Optimized Performance**: Enhanced bot loop with improved memory management and error handling

## Requirements

- **Windows OS** (uses Win32 API for window capture and input simulation)
- **Python 3.7+** (for development)
- **The Legend of Pirates Online [BETA]** game client
- **Game DPI settings configured to "System"** (see setup instructions below - CRITICAL!)

## Installation

### Option 1: Run from Source

1. Clone this repository:
```bash
git clone https://github.com/yourusername/tlopo-looter.git
cd tlopo-looter
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main_gui.py
```

### Option 2: Build Executable

1. Install dependencies (including PyInstaller):
```bash
pip install -r requirements.txt
```

2. Build the .exe:
```bash
pyinstaller main_gui.spec
```

3. Find the executable:
```
dist\TLOPO_Looter.exe
```

The .exe is completely portable and can be run on any Windows PC without Python installed.

## ⚠️ Important: Game DPI Configuration

**CRITICAL SETUP STEP** - The bot requires the game to use System DPI scaling for proper window detection and click accuracy.

### Configure Game DPI Settings:

1. **Locate the game executable** (e.g., `Pirates Online Launcher.exe` or game shortcut)
2. **Right-click** on the game icon/executable
3. **Select "Properties"**
4. **Go to the "Compatibility" tab**
5. **Click "Change high DPI settings"** button
6. **Check** "Override high DPI scaling behavior"
7. **Select "System"** from the dropdown (NOT "Application" or "System (Enhanced)")
8. **Click "OK"** on both dialogs
9. **Restart the game** if it's already running

### Why This Matters:

- **Window coordinates**: DPI scaling affects click positions
- **Screenshot capture**: Ensures correct image dimensions (1280x800)
- **Template matching**: Prevents scaling artifacts that break detection

**Without correct DPI settings, the bot will not click correctly and template matching will fail!**

## Usage

### GUI Interface

Run the application:
```bash
python main_gui.py
```

Or run the built executable:
```bash
TLOPO_Looter.exe
```

**GUI Features:**
- **Overview Tab**: Real-time status display with statistics
- **Advanced Settings Tab**: Configure timing and delays
- **Event Log**: Timestamped event history
- **Start/Stop Controls**: Easy bot control
- **Statistics Reset**: Clear tracked statistics

### Configuration

**Timing Settings (Advanced Settings Tab):**
- **Wait after enemy spawn**: Delay before engaging enemies (default: 5.5s)
- **Attack delay**: Time between consecutive attacks (default: 0.0s)

Settings are saved and can be adjusted in real-time through the GUI.

## Project Structure

```
TLOPO-Looter/
├── img/                                # Template images for detection
│   ├── full_hp.jpg
│   ├── damaged_hp.jpg
│   ├── empty_hp.jpg
│   ├── open_loot.jpg
│   └── loot_window.jpg
├── main_gui.py                         # PyQt5 GUI interface (main entry point)
├── main_gui.spec                       # PyInstaller build configuration
├── bot_logic.py                        # Core bot automation logic
├── vision.py                           # Computer vision & template matching
├── windowcapture.py                    # Windows screen capture utility
├── hsvfilter.py                        # HSV color filter configuration
├── icon.ico                            # Application icon
├── requirements.txt                    # Python dependencies
└── README.md                           # This file
```

## How It Works

1. **Window Detection**: Locates the game window and ensures 1280x800 resolution
2. **Window Validation**: Continuously verifies window state (every 0.3s) to prevent misclicks
3. **Template Matching**: Uses OpenCV to detect UI elements (loot prompts, health bars)
4. **HSV Color Filtering**: Identifies legendary items by red/gold color signature
5. **Input Simulation**: Sends keyboard/mouse events via Windows API
6. **Screenshot Capture**: Saves all loot screenshots automatically
7. **Error Handling**: Comprehensive error management for reliability

## Data Output

The bot automatically creates a `Data/` directory next to the executable with:
- `Data/All Loot Screenshots/Regular Loot/` - Regular loot screenshots
- `Data/All Loot Screenshots/Legendary Loot/` - Legendary loot screenshots with metadata

## Technical Details

### Safety Systems
- Window existence check (every loop iteration)
- Window resolution validation (1280x800 required)
- Minimized window auto-restore
- Automatic window resizing
- Input validation before all clicks/key presses
- Clean exit on game close

## Troubleshooting

**Game window not detected:**
- Ensure the game window title is exactly "The Legend of Pirates Online [BETA]"
- Make sure the game is running before starting the bot
- Check if window is minimized (bot will auto-restore)
- Verify DPI settings are set to "System" (see Game DPI Configuration section)

**Bot not clicking correctly:**
- **FIRST: Check DPI settings!** Make sure game is set to "System" DPI scaling (see Game DPI Configuration section above)
- Verify game resolution is exactly 1280x800 (bot auto-resizes)
- Restart the game after changing DPI settings
- Template images may need updating if game UI changed

**Screenshots not saving:**
- Check if Data folder has write permissions
- Ensure sufficient disk space
- Run as administrator if needed