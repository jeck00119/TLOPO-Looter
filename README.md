# TLOPO Looter

An automated bot for "The Legend of Pirates Online [BETA]" that uses computer vision to detect and collect loot, engage enemies, and track legendary items.

## Features

- **Automated Loot Collection**: Detects loot prompts and automatically collects items
- **Smart Duplicate Prevention**: Three-layer protection system prevents processing same loot window multiple times
  - Message overlay detection (waits for clean view)
  - Hash-based frame comparison (skips identical windows)
  - Automatic cleanup of old hashes
- **Enemy Detection & Combat**: Identifies enemy health bars and engages in combat with clean event logging
- **Legendary Item Tracking**: Detects legendary loot using HSV color filtering and saves screenshots
  - **Legendary Verification System**: Double-checks if legendary was taken, with automatic fallback if collection fails
  - Saves fallback screenshots when retry is needed
- **Modern PyQt5 GUI**: Real-time statistics with emoji indicators, event logging, and easy-to-use controls
- **Session-Based Organization**: Screenshots organized by timestamp folders for easy tracking
- **Statistics Tracking**: Tracks loot opened, legendaries found, and total running time
- **Emoji-Enhanced Logging**: Visual event logs with pirate-themed and functional emojis (🏴‍☠️ 💰 💎 ⚔️ 🗝️)
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
- **Attack delay**: Time between consecutive attacks (default: 0.1s)

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
├── test_message_detection.py          # Test script for message overlay detection
├── icon.ico                            # Application icon
├── requirements.txt                    # Python dependencies
└── README.md                           # This file
```

## How It Works

1. **Window Detection**: Locates the game window and ensures 1280x800 resolution
2. **Window Validation**: Continuously verifies window state (every 0.3s) to prevent misclicks
3. **Template Matching**: Uses OpenCV to detect UI elements (loot prompts, health bars)
4. **Message Overlay Detection**: Analyzes pixel darkness in bottom-left region to detect game messages
5. **Duplicate Prevention**: MD5 hash comparison prevents processing same window multiple times
6. **HSV Color Filtering**: Identifies legendary items by red/gold color signature
7. **Legendary Verification**: Re-scans after collection to ensure legendary was taken, with fallback retry
8. **Input Simulation**: Sends keyboard/mouse events via Windows API
9. **Screenshot Capture**: Saves all loot screenshots to session-based folders
10. **Error Handling**: Comprehensive error management for reliability

## Data Output

The bot automatically creates a `Data/` directory next to the executable with session-based organization:

```
Data/
└── All Loot Screenshots/
    └── Session_DD-MM-YYYY_HH.MM.SS/
        ├── Regular Loot/          # Regular loot screenshots (1.jpg, 2.jpg, ...)
        └── Legendary Loot/        # Legendary screenshots + fallback attempts
            ├── Legendary_X.jpg
            └── Legendary_X_FALLBACK.jpg  # If verification retry was needed
```

Each bot session creates a new timestamped folder for organized tracking.

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