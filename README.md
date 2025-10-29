# TLOPO Looter

An automated bot for "The Legend of Pirates Online [BETA]" that uses computer vision to detect and collect loot, engage enemies, and track legendary items.

## Features

- **Automated Loot Collection**: Detects loot prompts and automatically collects items
- **Enemy Detection & Combat**: Identifies enemy health bars and engages in combat
- **Legendary Item Tracking**: Detects legendary loot using HSV color filtering and saves screenshots
- **Dual Interface**:
  - Modern PyQt5 GUI with real-time statistics and event logging
  - CLI interface with colorized console output
- **Statistics Tracking**: Tracks loot opened, legendaries found, and total running time
- **Configurable Settings**: Adjustable attack delays and spawn wait times
- **Text-to-Speech Feedback**: Audio notifications for bot events

## Requirements

- Windows OS (uses Win32 API for window capture and input simulation)
- Python 3.7+
- The Legend of Pirates Online [BETA] game client

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/tlopo-looter.git
cd tlopo-looter
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### GUI Version (Recommended)

Run the PyQt5 graphical interface:
```bash
python main_gui.py
```

**Features:**
- Overview tab with real-time status display
- Advanced Settings tab for timing configuration
- Event log with timestamps
- Start/Stop controls
- Statistics reset options

### CLI Version

Run the command-line interface:
```bash
python main.py
```

**Hotkeys:**
- `INSERT` - Start bot
- `DELETE` - Stop bot
- `HOME` - Open settings menu

## Configuration

### Timing Settings

- **Wait after enemy spawn**: Delay before engaging enemies (default: 5.5s)
- **Attack delay**: Time between consecutive attacks (default: 0.0s)

Settings can be adjusted in the GUI or through the CLI settings menu.

## Project Structure

```
tlopo-looter/
├── main_gui.py           # PyQt5 GUI interface
├── main.py               # CLI interface
├── bot_logic.py          # Core bot automation logic
├── hsvfilter.py          # HSV color filter configuration
├── vision.py             # Computer vision & template matching
├── windowcapture.py      # Windows screen capture utility
├── requirements.txt      # Python dependencies
├── icon.ico              # Application icon
└── img/                  # Template images for detection
    ├── full_hp.jpg
    ├── damaged_hp.jpg
    ├── empty_hp.jpg
    ├── open_loot.jpg
    ├── loot_window.jpg
    ├── hit_combo.jpg
    └── out_of_range.jpg
```

## How It Works

1. **Window Detection**: Locates the game window and ensures 1280x800 resolution
2. **Template Matching**: Uses OpenCV to detect UI elements (loot prompts, health bars)
3. **HSV Color Filtering**: Identifies legendary items by color signature
4. **Input Simulation**: Sends keyboard/mouse events via Windows API
5. **Screenshot Capture**: Saves all loot screenshots with metadata

## Data Output

The bot creates a `Data/` directory with two subdirectories:
- `All Loot Screenshots/Regular Loot/` - Regular loot screenshots
- `All Loot Screenshots/Legendary Loot/` - Legendary loot with metadata files

## Disclaimer

This bot is for educational purposes only. Use at your own risk. Automated gameplay may violate the game's Terms of Service and could result in account penalties.

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## Troubleshooting

**Game window not detected:**
- Ensure the game window title is "The Legend of Pirates Online [BETA]"
- Make sure the game is running before starting the bot

**Bot not clicking correctly:**
- Verify game resolution is 1280x800
- Template images may need updating if game UI changed

**PyQt5 import error:**
- Install PyQt5: `pip install PyQt5`
