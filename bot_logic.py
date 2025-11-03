import cv2 as cv2
import hashlib
import numpy as np
import os
import pyttsx3
import sys
import time
import win32api as api
import win32con
import win32gui as gui
from datetime import datetime
from time import sleep
from win32con import WM_KEYDOWN, WM_KEYUP, VK_CONTROL, WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON, VK_SHIFT

from hsvfilter import HsvFilter
from vision import Vision
from windowcapture import WindowCapture


# ===========================
# CONFIGURATION CONSTANTS
# ===========================

# Game Window Settings
GAME_WINDOW_TITLE = "The Legend of Pirates Online [BETA]"
GAME_RESOLUTION = (1280, 800)
WINDOW_BORDER_OFFSET = (16, 39)  # (width, height) borders

# Timing Delays (seconds)
LOOP_DELAY = 0.3
LOOT_OPEN_PRE_DELAY = 2.0
LOOT_OPEN_POST_DELAY = 3.0
SHIFT_KEY_HOLD_TIME = 0.8
CTRL_KEY_HOLD_TIME = 0.3
TAKE_ITEMS_DELAY = 2.0
INITIAL_ATTACK_DELAY = 0.5

# Button Click Coordinates
TAKE_SMALL_ITEMS_BUTTON = (532, 399)
TRASH_BUTTON = (221, 205)

# Legendary Item Detection
LEGENDARY_OFFSET_X = 202 - 26  # 176
LEGENDARY_OFFSET_Y = 181 + 8   # 189
LEGENDARY_RANGE_1 = range(250, 280)
LEGENDARY_RANGE_2 = range(404, 437)
MIN_CONTOUR_AREA = 800

# Template Matching Thresholds
THRESHOLD_OPEN_LOOT = 0.40
THRESHOLD_LOOT_WINDOW = 0.35  # Lowered to detect through message overlays
THRESHOLD_HP_FULL = 0.85
THRESHOLD_HP_DAMAGED = 0.95
THRESHOLD_HP_EMPTY = 0.90

# HSV Filter for Legendary Items (Red/Gold)
HSV_LEGENDARY_RED = {
    'hMin': 0, 'sMin': 233, 'vMin': 3,
    'hMax': 0, 'sMax': 255, 'vMax': 255,
    'sAdd': 25, 'sSub': 22, 'vAdd': 0, 'vSub': 140
}

# Image Processing
DILATION_KERNEL_SIZE = (8, 8)

# ===========================
# END CONFIGURATION
# ===========================


engine = pyttsx3.init()
engine.setProperty('rate', 150)
engine.setProperty('volume', 1.0)
voices = engine.getProperty('voices')
if voices:
    engine.setProperty('voice', voices[min(1, len(voices) - 1)].id)


def resource_path(relative_path):
    """
    Return absolute path to READ-ONLY bundled resources (like img folder).
    When frozen with PyInstaller, uses temporary _MEIPASS directory.
    """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def get_data_path(relative_path=''):
    """
    Return absolute path to WRITABLE data folder (like Data folder).
    Always returns path relative to .exe or script location, NOT _MEIPASS.
    This ensures Data folder is created next to the executable, not in temp folder.
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled .exe - use exe directory
        base_path = os.path.dirname(sys.executable)
    else:
        # Running as .py script - use script directory
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path) if relative_path else base_path


def ensure_data_directories(session_folder=None):
    """
    Create data directories. If session_folder is provided, creates session-based structure.
    Otherwise creates legacy flat structure.
    """
    if session_folder:
        # Session-based structure
        targets = [
            get_data_path(f'Data\\All Loot Screenshots\\{session_folder}\\Legendary Loot'),
            get_data_path(f'Data\\All Loot Screenshots\\{session_folder}\\Regular Loot'),
        ]
    else:
        # Legacy flat structure (backward compatibility)
        targets = [
            get_data_path('Data\\All Loot Screenshots\\Legendary Loot'),
            get_data_path('Data\\All Loot Screenshots\\Regular Loot'),
        ]
    for target in targets:
        os.makedirs(target, exist_ok=True)


def ensure_directory_exists(path):
    """
    Create directory if it doesn't exist.
    Returns: (success, error_message)
    """
    if os.path.exists(path):
        return (True, None)
    try:
        os.makedirs(path)
        return (True, None)
    except Exception as e:
        return (False, str(e))


def get_screenshot_path(session_folder, filename, legendary=False, fallback=False):
    """
    Construct screenshot path for given session and filename.
    Args:
        session_folder: Session folder name (e.g., 'Session_30-10-2025_14.30.45')
        filename: Base filename (e.g., 'Legendary_1.jpg' or '1.jpg')
        legendary: If True, saves to Legendary Loot folder
        fallback: If True, appends '_FALLBACK' to filename
    Returns: Absolute path to screenshot file
    """
    if fallback:
        base, ext = os.path.splitext(filename)
        filename = f"{base}_FALLBACK{ext}"

    subfolder = 'Legendary Loot' if legendary else 'Regular Loot'
    return get_data_path(f'Data\\All Loot Screenshots\\{session_folder}\\{subfolder}\\{filename}')


def get_info_path(session_folder, filename):
    """Construct path for legendary info text file"""
    return get_data_path(f'Data\\All Loot Screenshots\\{session_folder}\\Legendary Loot\\{filename}')


def save_debug_screenshot(frame, template, region_name, timestamp, threshold):
    """
    Save debug screenshot showing what's being matched.
    Saves both the captured region and the scaled template for comparison.
    Args:
        frame: The screenshot region being searched
        template: The scaled template being matched
        region_name: Name of the detection (e.g., 'open_loot', 'loot_window')
        timestamp: Timestamp string for filename
        threshold: Threshold value used for detection
    """
    try:
        debug_folder = get_data_path('Data\\Debug')
        os.makedirs(debug_folder, exist_ok=True)

        # Save the captured region
        region_path = os.path.join(debug_folder, f'{timestamp}_{region_name}_region.jpg')
        cv2.imwrite(region_path, frame)

        # Save the template being matched
        template_path = os.path.join(debug_folder, f'{timestamp}_{region_name}_template.jpg')
        cv2.imwrite(template_path, template)

        # Save a text file with info
        info_path = os.path.join(debug_folder, f'{timestamp}_{region_name}_info.txt')
        with open(info_path, 'w') as f:
            f.write(f"Detection: {region_name}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Threshold: {threshold:.2f}\n")
            f.write(f"Region size: {frame.shape[1]}x{frame.shape[0]}\n")
            f.write(f"Template size: {template.shape[1]}x{template.shape[0]}\n")
            f.write(f"\nFiles saved:\n")
            f.write(f"  Region: {region_path}\n")
            f.write(f"  Template: {template_path}\n")

        return True
    except Exception as e:
        return False


def _initial_image_index():
    """
    Returns initial image index for a new session.
    Always returns 1 for session-based folders (fresh counter each session).
    """
    return 1


img_dir = resource_path("img")
# current_img moved inside run_bot() to prevent race conditions


# ===========================
# WINDOW UTILITY FUNCTIONS
# ===========================

def check_window():
    """
    Checks if game window exists and restores if minimized.
    Returns window handle if found, 0 if not found.

    Note: Bot now adapts to any resolution, so no auto-resize is performed.
    """
    try:
        handle = gui.FindWindow(None, GAME_WINDOW_TITLE)
        if not handle:
            return 0

        # Restore if minimized (CRITICAL: Bot can't capture minimized windows)
        left, top, right, bottom = gui.GetClientRect(handle)
        if right == 0 and bottom == 0:
            gui.ShowWindow(handle, win32con.SW_SHOWNORMAL)
            sleep(0.1)  # Give window time to restore

        return handle

    except Exception:
        return 0


def resize_window_iterative(handle, max_iterations=3):
    """
    DEPRECATED: This function is kept for backward compatibility with window_fix_tool.py only.

    Bot no longer forces window resizing - it adapts to any resolution.
    This function tries to resize window to 1280x800 for diagnostic purposes only.

    Returns True if successful (within ±10px tolerance), False otherwise.
    """
    try:
        TOLERANCE = 10

        for i in range(max_iterations):
            # Get current client size
            client_rect = gui.GetClientRect(handle)
            client_w = client_rect[2]
            client_h = client_rect[3]

            # Calculate error
            error_w = GAME_RESOLUTION[0] - client_w
            error_h = GAME_RESOLUTION[1] - client_h

            # Check if within tolerance
            if abs(error_w) <= TOLERANCE and abs(error_h) <= TOLERANCE:
                return True

            # Check if exact
            if error_w == 0 and error_h == 0:
                return True

            # Get current window size and adjust by error
            x0, y0, x1, y1 = gui.GetWindowRect(handle)
            window_w = x1 - x0
            window_h = y1 - y0

            new_window_w = window_w + error_w
            new_window_h = window_h + error_h

            # Resize window
            gui.MoveWindow(handle, x0, y0, new_window_w, new_window_h, True)
            sleep(0.15)  # Match test script timing exactly

        # Check final size
        client_rect = gui.GetClientRect(handle)
        client_w = client_rect[2]
        client_h = client_rect[3]
        error_w = abs(GAME_RESOLUTION[0] - client_w)
        error_h = abs(GAME_RESOLUTION[1] - client_h)

        return error_w <= TOLERANCE and error_h <= TOLERANCE

    except Exception as e:
        return False


def check_dpi_settings(hwnd):
    """
    DEPRECATED: This function is kept for backward compatibility with window_fix_tool.py.

    Returns informational message about current resolution.
    Bot now adapts to any resolution, so this never blocks startup.

    Returns: (always_true, info_message)
    """
    try:
        # Get actual client area dimensions
        client_rect = gui.GetClientRect(hwnd)
        actual_width = client_rect[2]
        actual_height = client_rect[3]

        # Just return informational message (never blocks)
        return (True, f"Detected resolution: {actual_width}x{actual_height} (bot will auto-scale)")

    except Exception as e:
        return (True, f"Resolution detection skipped: {e}")


# ===========================
# END WINDOW UTILITIES
# ===========================


# ===========================
# RESOLUTION SCALING SYSTEM
# ===========================

def detect_resolution_and_scale(hwnd):
    """
    Detect current game resolution and calculate scale factors.
    Base resolution: 1280x800
    Returns: (current_width, current_height, scale_x, scale_y)
    """
    try:
        rect = gui.GetClientRect(hwnd)
        current_w = rect[2]
        current_h = rect[3]

        # Calculate scale factors relative to base resolution
        scale_x = current_w / 1280.0
        scale_y = current_h / 800.0

        return current_w, current_h, scale_x, scale_y
    except Exception as e:
        # Fallback to base resolution if detection fails
        return 1280, 800, 1.0, 1.0


def scale_coordinates(scale_x, scale_y):
    """
    Scale all hardcoded button coordinates to current resolution.
    Returns: Dictionary of scaled coordinate tuples
    """
    return {
        'TAKE_SMALL_ITEMS_BUTTON': (int(532 * scale_x), int(399 * scale_y)),
        'TRASH_BUTTON': (int(221 * scale_x), int(205 * scale_y)),
    }


def scale_crop_regions(scale_x, scale_y):
    """
    Scale WindowCapture crop regions to current resolution.
    Returns: Dictionary of scaled region definitions
    """
    base_regions = {
        "crop_boss_name": {"x": 570, "y": 70, "w": 200, "h": 25},
        "crop_enemy_hp": {"x": 571, "y": 93, "w": 225, "h": 18},
        "crop_hit_combo": {"x": 200, "y": 195, "w": 200, "h": 50},
        "crop_loot_window": {"x": 207, "y": 209, "w": 397, "h": 262},
        "crop_open_loot": {"x": 570, "y": 684, "w": 155, "h": 34},
        "crop_test": {"x": 925, "y": 68, "w": 148, "h": 26},
    }

    scaled_regions = {}
    for name, region in base_regions.items():
        scaled_regions[name] = {
            'x': int(region['x'] * scale_x),
            'y': int(region['y'] * scale_y),
            'w': int(region['w'] * scale_x),
            'h': int(region['h'] * scale_y)
        }

    return scaled_regions


def scale_legendary_detection(scale_x, scale_y):
    """
    Scale legendary item detection parameters to current resolution.
    Returns: Dictionary of scaled detection parameters
    """
    return {
        'OFFSET_X': int(176 * scale_x),  # LEGENDARY_OFFSET_X
        'OFFSET_Y': int(189 * scale_y),  # LEGENDARY_OFFSET_Y
        'RANGE_1_START': int(250 * scale_x),
        'RANGE_1_END': int(280 * scale_x),
        'RANGE_2_START': int(404 * scale_x),
        'RANGE_2_END': int(437 * scale_x),
    }


def scale_template(template_img, scale_x, scale_y):
    """
    Scale a template image to match current resolution.
    Uses INTER_AREA for downscaling (better quality), INTER_CUBIC for upscaling.
    Returns: Scaled template image
    """
    if scale_x == 1.0 and scale_y == 1.0:
        return template_img  # No scaling needed

    # Choose interpolation based on scaling direction
    # INTER_AREA is best for downscaling (reduces aliasing/blur)
    # INTER_CUBIC is best for upscaling (smoother)
    if scale_x < 1.0 or scale_y < 1.0:
        interpolation = cv2.INTER_AREA  # Downscaling
    else:
        interpolation = cv2.INTER_CUBIC  # Upscaling

    return cv2.resize(template_img, None, fx=scale_x, fy=scale_y,
                     interpolation=interpolation)


# ===========================
# END RESOLUTION SCALING
# ===========================


def validate_game_ready():
    """
    Validate all requirements before starting bot.
    Now resolution-independent - accepts any game resolution.
    Returns: (success, error_message, details)
    """
    details = {}

    # Check 1: Game window exists and is not minimized
    handle = check_window()
    if not handle:
        return (False, "Game window not detected. Please start the game.", details)
    details['window_handle'] = handle

    # Check 2: Detect current resolution (no enforcement, just log)
    try:
        current_w, current_h, scale_x, scale_y = detect_resolution_and_scale(handle)
        details['detected_resolution'] = f"{current_w}x{current_h}"
        details['scale_factors'] = f"{scale_x:.2f}x, {scale_y:.2f}x"
        details['resolution_ok'] = True

        # Informational message (not blocking)
        if current_w == 1280 and current_h == 800:
            details['resolution_note'] = "Using base resolution (no scaling needed)"
        else:
            details['resolution_note'] = f"Bot will scale for {current_w}x{current_h} resolution"
    except Exception as e:
        return (False, f"Failed to detect game resolution: {e}", details)

    # Check 3: Template images exist
    img_dir = resource_path("img")
    required_templates = [
        'open_loot.jpg',
        'loot_window.jpg',
        'full_hp.jpg',
        'damaged_hp.jpg',
        'empty_hp.jpg'
    ]

    missing_templates = []
    for template in required_templates:
        template_path = os.path.join(img_dir, template)
        if not os.path.exists(template_path):
            missing_templates.append(template)

    if missing_templates:
        details['missing_templates'] = missing_templates
        return (False, f"Required template images missing from img/ folder: {', '.join(missing_templates)}", details)

    details['templates_ok'] = True

    # Check 4: Data folder writable
    try:
        test_dir = get_data_path('Data')
        os.makedirs(test_dir, exist_ok=True)

        # Try creating a test file
        test_file = os.path.join(test_dir, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        details['data_folder_writable'] = True
    except Exception as e:
        return (False, f"Cannot write to Data/ folder. Check permissions. Error: {e}", details)

    # All checks passed
    return (True, "All validation checks passed", details)


def press_left_click(x, y):
    handle = check_window()
    if not handle:
        return
    l_param = api.MAKELONG(x, y)
    api.PostMessage(handle, WM_LBUTTONDOWN, MK_LBUTTON, l_param)
    api.PostMessage(handle, WM_LBUTTONUP, MK_LBUTTON, l_param)


def press_ctrl():
    handle = check_window()
    if not handle:
        return
    api.PostMessage(handle, WM_KEYDOWN, VK_CONTROL, 0)
    sleep(CTRL_KEY_HOLD_TIME)
    api.PostMessage(handle, WM_KEYUP, VK_CONTROL, 0)


def press_shift():
    handle = check_window()
    if not handle:
        return
    api.PostMessage(handle, WM_KEYDOWN, VK_SHIFT, 0)
    sleep(SHIFT_KEY_HOLD_TIME)
    api.PostMessage(handle, WM_KEYUP, VK_SHIFT, 0)


def has_message_overlay(frame):
    """
    Detect if message overlays are present in loot window.
    Messages appear as dark semi-transparent boxes in the bottom-left area.
    Returns True if message detected, False if clean view.
    """
    try:
        # Check bottom-left region where messages typically appear
        # Based on loot window crop: (207, 209, 397x262)
        # Bottom-left corner of that region
        message_region = frame[150:220, 0:150]

        # Convert to grayscale
        gray = cv2.cvtColor(message_region, cv2.COLOR_BGR2GRAY)

        # Messages have dark backgrounds (pixel values < 40)
        # Count dark pixels
        dark_pixels = np.sum(gray < 40)
        total_pixels = gray.size
        dark_ratio = dark_pixels / total_pixels

        # If > 20% of region is very dark, message is present
        return dark_ratio > 0.20

    except Exception:
        # If detection fails, assume no message (safe default)
        return False


def run_bot(started, attack_delay, wait_after_enemy_spawn, gui_settings_opened, loot_opened, legendaries, status_queue=None, screenshot_enabled=None,
            threshold_open_loot=None, threshold_loot_window=None, threshold_hp_full=None, threshold_hp_damaged=None, threshold_hp_empty=None,
            debug_mode=None, show_coords=None, show_confidence=None,
            debug_capture_open_loot=None, debug_capture_loot_window=None, debug_capture_hp_full=None, debug_capture_hp_damaged=None, debug_capture_hp_empty=None,
            manual_capture_trigger=None, overlay_enabled=None):
    """Main bot loop extracted from the CLI script."""

    def notify(event_type, message=None, **payload):
        if status_queue is None:
            return
        event = {"type": event_type}
        if message is not None:
            event["message"] = message
        if payload:
            event.update(payload)
        try:
            status_queue.put(event)
        except Exception:
            pass

    def click_with_logging(x, y, label=""):
        """Wrapper for press_left_click that logs coordinates if enabled"""
        press_left_click(x, y)
        if show_coords and bool(show_coords.value):
            msg = f"🖱️ Clicked at ({x}, {y})"
            if label:
                msg += f" - {label}"
            notify("click", msg, x=x, y=y)

    def game_closed():
        started.value = False
        notify("error", "❌ ERROR: The game window is closed. Bot stopping.")
        engine.say("Error")
        engine.say("Bot Stopped")
        engine.runAndWait()
        sys.exit(1)

    def check_legendary(frame, hsv_filter, current_img, save_screenshots, session_folder, wincap, legendary_params, coords):
        """
        Checks if the loot window contains legendary items.
        Saves screenshot ONCE per loot window (if enabled).
        Verifies legendary was taken and uses fallback if needed.
        Args:
            legendary_params: Dictionary with scaled legendary detection parameters
            coords: Dictionary with scaled button coordinates
        Returns: incremented current_img counter
        """
        try:
            if save_screenshots:
                ensure_data_directories(session_folder)

            mask = vision_loot.apply_hsv_filter(frame, hsv_filter)
            kernel = np.ones(DILATION_KERNEL_SIZE, "uint8")
            mask = cv2.dilate(mask, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            is_legendary = False
            legendary_x, legendary_y = None, None
            legendary_coords = None

            # Check all contours for legendary items
            if contours:
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area > MIN_CONTOUR_AREA:
                        x, y, w, h = cv2.boundingRect(contour)
                        calculated_x = x + legendary_params['OFFSET_X']

                        # Check if item is in legendary position (using scaled ranges)
                        range_1 = range(legendary_params['RANGE_1_START'], legendary_params['RANGE_1_END'])
                        range_2 = range(legendary_params['RANGE_2_START'], legendary_params['RANGE_2_END'])
                        if calculated_x in range_1 or calculated_x in range_2:
                            is_legendary = True
                            legendary_x = calculated_x
                            legendary_y = y + legendary_params['OFFSET_Y']
                            legendary_coords = (x, y)
                            break  # Found legendary, stop searching

            # Save screenshot ONCE based on result (if enabled)
            if is_legendary:
                notify("status", f"💎 Legendary item detected at position ({legendary_x}, {legendary_y}).")
                legendary_path = None
                if save_screenshots:
                    legendary_path = get_screenshot_path(session_folder, f'Legendary_{current_img}.jpg', legendary=True)
                    cv2.imwrite(legendary_path, frame)
                    notify("status", f"📸 Screenshot saved: Legendary_{current_img}.jpg")

                time_elapsed = datetime.now().replace(microsecond=0) - start_time.replace(microsecond=0)

                engine.say("Legendary Found")
                engine.runAndWait()

                # LEGENDARY VERIFICATION FLOW
                # Double-click puts legendary in backpack, but may fail due to network lag
                # Verification: Screenshot → Re-detect → If still visible: Try fallback method
                notify("status", "🖱️ Double-clicking legendary item (1st attempt).")
                click_with_logging(legendary_x, legendary_y, "Legendary 1st click")
                click_with_logging(legendary_x, legendary_y, "Legendary 2nd click")

                # Verification: Check if legendary was taken
                notify("status", "🔎 Waiting 1s, then verifying legendary was taken.")
                sleep(1.0)  # Wait for double-click to process

                # Capture verification screenshot
                verification_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_loot_window')

                # Re-run legendary detection on verification frame
                verification_mask = vision_loot.apply_hsv_filter(verification_frame, hsv_filter)
                kernel = np.ones(DILATION_KERNEL_SIZE, "uint8")
                verification_mask = cv2.dilate(verification_mask, kernel)
                verification_contours, _ = cv2.findContours(verification_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                legendary_still_there = False
                for contour in verification_contours:
                    area = cv2.contourArea(contour)
                    if area > MIN_CONTOUR_AREA:
                        vx, vy, vw, vh = cv2.boundingRect(contour)
                        calc_x = vx + legendary_params['OFFSET_X']
                        range_1 = range(legendary_params['RANGE_1_START'], legendary_params['RANGE_1_END'])
                        range_2 = range(legendary_params['RANGE_2_START'], legendary_params['RANGE_2_END'])
                        if calc_x in range_1 or calc_x in range_2:
                            legendary_still_there = True
                            break

                # Fallback if legendary still visible
                if legendary_still_there:
                    notify("status", "⚠️ Verification: Legendary STILL VISIBLE after 1st attempt!")
                    # Double-click again (second attempt)
                    notify("status", "🔁 Double-clicking legendary item (2nd attempt).")
                    click_with_logging(legendary_x, legendary_y, "Legendary retry 1st click")
                    click_with_logging(legendary_x, legendary_y, "Legendary retry 2nd click")
                    sleep(1.0)

                    # Click "Take Small Items" once (fallback)
                    notify("status", "🆘 Clicking 'Take Small Items' button (fallback method).")
                    click_with_logging(*coords['TAKE_SMALL_ITEMS_BUTTON'], label="Take Small Items (fallback)")

                    # Save fallback screenshot
                    if save_screenshots:
                        fallback_path = get_screenshot_path(session_folder, f'Legendary_{current_img}.jpg', legendary=True, fallback=True)
                        cv2.imwrite(fallback_path, verification_frame)
                        notify("status", f"📷 Fallback screenshot saved: Legendary_{current_img}_FALLBACK.jpg")

                    notify("legendary_fallback", "🆘 Legendary required Take All fallback",
                           loot_count=int(loot_opened.value))
                else:
                    notify("status", "🏆 Verification: Legendary successfully taken!")
                    notify("legendary_success", "🏆 Legendary taken successfully by double-click",
                           loot_count=int(loot_opened.value))

                legendaries.value += 1

                info_path = None
                if save_screenshots:
                    info_path = get_info_path(session_folder, f'Legendary_Info_{current_img}.txt')
                    with open(info_path, 'a') as f_handle:
                        f_handle.write(f'################################################\n'
                                       f'Legendary_{current_img}\n'
                                       f'Original coordinates: {legendary_coords}\n'
                                       f'Calculated coordinates: {legendary_x, legendary_y}\n'
                                       f'Time elapsed to find the legendary: {time_elapsed}\n'
                                       f'################################################\n\n')

                notify(
                    "legendary",
                    "Legendary loot detected.",
                    loot_count=int(loot_opened.value),
                    legendary_count=int(legendaries.value),
                    screenshot=legendary_path,
                    info_file=info_path,
                )
            else:
                notify("status", "📦 No legendary items detected, regular loot only.")
                if save_screenshots:
                    regular_path = get_screenshot_path(session_folder, f'{current_img}.jpg', legendary=False)
                    cv2.imwrite(regular_path, frame)
                    notify("status", f"📄 Regular loot screenshot saved: {current_img}.jpg")

            return current_img + 1

        except Exception as e:
            notify("error", f"❌ Error in check_legendary: {e}")
            # Still increment counter even on error to avoid overwrites
            return current_img + 1

    # Initialize screenshot counter (always starts at 1 for each session)
    current_img = _initial_image_index()

    # Create session folder name with timestamp
    start_time = datetime.now()
    session_folder = start_time.strftime("Session_%d-%m-%Y_%H.%M.%S")
    notify("status", f"🏴‍☠️ Bot loop started. Session: {session_folder}")

    handle = check_window()
    if not handle:
        game_closed()
        return

    wincap = WindowCapture()

    # ═══════════════════════════════════════
    # RESOLUTION DETECTION & SCALING
    # ═══════════════════════════════════════
    notify("status", "🔍 Detecting game resolution...")
    current_w, current_h, scale_x, scale_y = detect_resolution_and_scale(handle)
    notify("status", f"📐 Resolution: {current_w}x{current_h} | Scale: {scale_x:.2f}x, {scale_y:.2f}x")
    # Send resolution info to GUI for debug display
    notify("resolution_detected", resolution=f"{current_w}x{current_h}", scale_x=scale_x, scale_y=scale_y)

    # Scale crop regions and set them on WindowCapture
    scaled_regions = scale_crop_regions(scale_x, scale_y)
    wincap.set_crop_regions(scaled_regions)
    notify("status", "✅ Crop regions scaled to current resolution")

    # Scale button coordinates
    coords = scale_coordinates(scale_x, scale_y)
    notify("status", f"✅ Button coordinates scaled")

    # Scale legendary detection parameters
    legendary_params = scale_legendary_detection(scale_x, scale_y)
    notify("status", "✅ Legendary detection parameters scaled")

    # Get base thresholds from shared memory (if provided) or use constants
    base_threshold_open_loot = float(threshold_open_loot.value) if threshold_open_loot else THRESHOLD_OPEN_LOOT
    base_threshold_loot_window = float(threshold_loot_window.value) if threshold_loot_window else THRESHOLD_LOOT_WINDOW
    base_threshold_hp_full = float(threshold_hp_full.value) if threshold_hp_full else THRESHOLD_HP_FULL
    base_threshold_hp_damaged = float(threshold_hp_damaged.value) if threshold_hp_damaged else THRESHOLD_HP_DAMAGED
    base_threshold_hp_empty = float(threshold_hp_empty.value) if threshold_hp_empty else THRESHOLD_HP_EMPTY

    notify("status", f"📊 Using thresholds: Open={base_threshold_open_loot:.2f}, Loot={base_threshold_loot_window:.2f}, "
                     f"HP Full={base_threshold_hp_full:.2f}, HP Dmg={base_threshold_hp_damaged:.2f}, HP Empty={base_threshold_hp_empty:.2f}")

    # Adjust thresholds for low resolutions (downscaling loses quality)
    # At 1024x768 (0.80x), templates lose detail, so lower thresholds
    threshold_adjustment = 1.0
    if scale_x < 1.0 or scale_y < 1.0:
        # For downscaling, reduce thresholds by up to 15%
        min_scale = min(scale_x, scale_y)
        threshold_adjustment = 0.85 + (min_scale * 0.15)  # Range: 0.85 to 1.0
        notify("status", f"⚠️ Low resolution detected - adjusting thresholds ({threshold_adjustment:.2f}x)")

    # Calculate adjusted thresholds (user-set values * resolution adjustment)
    adjusted_thresholds = {
        'OPEN_LOOT': base_threshold_open_loot * threshold_adjustment,
        'LOOT_WINDOW': base_threshold_loot_window * threshold_adjustment,
        'HP_FULL': base_threshold_hp_full * threshold_adjustment,
        'HP_DAMAGED': base_threshold_hp_damaged * threshold_adjustment,
        'HP_EMPTY': base_threshold_hp_empty * threshold_adjustment,
    }

    # Load and scale templates
    try:
        notify("status", "📸 Loading template images...")
        # Load original templates
        template_open_loot = cv2.imread(img_dir + '\\open_loot.jpg')
        template_loot_window = cv2.imread(img_dir + '\\loot_window.jpg')
        template_hp_full = cv2.imread(img_dir + '\\full_hp.jpg')
        template_hp_damaged = cv2.imread(img_dir + '\\damaged_hp.jpg')
        template_hp_empty = cv2.imread(img_dir + '\\empty_hp.jpg')

        # Scale templates to current resolution
        if scale_x != 1.0 or scale_y != 1.0:
            notify("status", f"🔧 Scaling templates by {scale_x:.2f}x, {scale_y:.2f}x...")
            template_open_loot = scale_template(template_open_loot, scale_x, scale_y)
            template_loot_window = scale_template(template_loot_window, scale_x, scale_y)
            template_hp_full = scale_template(template_hp_full, scale_x, scale_y)
            template_hp_damaged = scale_template(template_hp_damaged, scale_x, scale_y)
            template_hp_empty = scale_template(template_hp_empty, scale_x, scale_y)
            notify("status", "✅ Templates scaled successfully")
        else:
            notify("status", "✅ Using original templates (no scaling needed)")

        # Create Vision objects with scaled templates
        vision_open_loot = Vision(None)
        vision_open_loot.needle_img = template_open_loot
        vision_open_loot.needle_w = template_open_loot.shape[1]
        vision_open_loot.needle_h = template_open_loot.shape[0]

        vision_loot_window = Vision(None)
        vision_loot_window.needle_img = template_loot_window
        vision_loot_window.needle_w = template_loot_window.shape[1]
        vision_loot_window.needle_h = template_loot_window.shape[0]

        vision_enemy_hp_full = Vision(None)
        vision_enemy_hp_full.needle_img = template_hp_full
        vision_enemy_hp_full.needle_w = template_hp_full.shape[1]
        vision_enemy_hp_full.needle_h = template_hp_full.shape[0]

        vision_enemy_hp_damaged = Vision(None)
        vision_enemy_hp_damaged.needle_img = template_hp_damaged
        vision_enemy_hp_damaged.needle_w = template_hp_damaged.shape[1]
        vision_enemy_hp_damaged.needle_h = template_hp_damaged.shape[0]

        vision_enemy_hp_empty = Vision(None)
        vision_enemy_hp_empty.needle_img = template_hp_empty
        vision_enemy_hp_empty.needle_w = template_hp_empty.shape[1]
        vision_enemy_hp_empty.needle_h = template_hp_empty.shape[0]

        vision_loot = Vision(None)

        notify("status", "✅ All templates loaded and ready")
    except Exception as e:
        notify("error", f"❌ Failed to load template images: {e}")
        started.value = False
        return

    # Create HSV filter from constants
    hsv_filter_red = HsvFilter(**HSV_LEGENDARY_RED)

    # DUPLICATE DETECTION SYSTEM
    # Problem: Game messages overlay loot window, causing same window to be detected multiple times
    # Solution: Three-layer protection:
    #   1. Message detection - Skip processing if message overlay present (wait for clean view)
    #   2. Hash comparison - Skip if identical frame already processed (prevents double-clicking same window)
    #   3. Timestamp cleanup - Remove old hashes after 5min to prevent memory leak
    processed_loot = {}  # {hash: timestamp}

    # Track if we've logged the attack message for current enemy
    attacking_logged = False

    # Debug screenshot counters (limit to first 5 examples of each type)
    debug_counters = {
        'open_loot': 0,
        'loot_window': 0,
        'hp_full': 0,
        'hp_damaged': 0,
        'hp_empty': 0
    }
    MAX_DEBUG_SCREENSHOTS = 5

    def get_current_thresholds():
        """
        Read current thresholds from shared memory and apply resolution adjustment.
        This allows thresholds to be changed live without restarting the bot.
        Returns: Dictionary of adjusted thresholds
        """
        # Read current base thresholds from shared memory
        base_open_loot = float(threshold_open_loot.value) if threshold_open_loot else THRESHOLD_OPEN_LOOT
        base_loot_window = float(threshold_loot_window.value) if threshold_loot_window else THRESHOLD_LOOT_WINDOW
        base_hp_full = float(threshold_hp_full.value) if threshold_hp_full else THRESHOLD_HP_FULL
        base_hp_damaged = float(threshold_hp_damaged.value) if threshold_hp_damaged else THRESHOLD_HP_DAMAGED
        base_hp_empty = float(threshold_hp_empty.value) if threshold_hp_empty else THRESHOLD_HP_EMPTY

        # Apply resolution adjustment (calculated at startup)
        return {
            'OPEN_LOOT': base_open_loot * threshold_adjustment,
            'LOOT_WINDOW': base_loot_window * threshold_adjustment,
            'HP_FULL': base_hp_full * threshold_adjustment,
            'HP_DAMAGED': base_hp_damaged * threshold_adjustment,
            'HP_EMPTY': base_hp_empty * threshold_adjustment,
        }

    # Track last manual capture trigger value to detect changes
    last_manual_trigger = 0

    while True:
        sleep(LOOP_DELAY)

        if check_window() != 0:
            try:
                # Get current thresholds (allows live updates)
                current_thresholds = get_current_thresholds()

                # Check for manual capture trigger (button press)
                manual_capture_now = False
                if manual_capture_trigger:
                    current_trigger = int(manual_capture_trigger.value)
                    if current_trigger != last_manual_trigger:
                        last_manual_trigger = current_trigger
                        manual_capture_now = True
                        notify("status", "📸 Manual capture triggered! Saving screenshots of all detection zones...")

                open_loot_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_open_loot')
                rectangles_open_loot = vision_open_loot.find(open_loot_frame, current_thresholds['OPEN_LOOT'])

                # Save debug screenshot (auto or manual trigger)
                should_save_open_loot = False
                if manual_capture_now:
                    should_save_open_loot = True  # Manual capture ignores flags and counters
                elif debug_mode and bool(debug_mode.value) and debug_capture_open_loot and bool(debug_capture_open_loot.value) and debug_counters['open_loot'] < MAX_DEBUG_SCREENSHOTS:
                    should_save_open_loot = True

                if should_save_open_loot:
                    timestamp = datetime.now().strftime("%H%M%S_%f")
                    if manual_capture_now:
                        timestamp = f"MANUAL_{timestamp}"
                    save_debug_screenshot(open_loot_frame, template_open_loot, 'open_loot', timestamp, current_thresholds['OPEN_LOOT'])
                    if not manual_capture_now:
                        debug_counters['open_loot'] += 1

                if rectangles_open_loot.any():
                    if show_confidence and bool(show_confidence.value):
                        notify("detection", f"Detected: Open Loot Prompt", template="Open Loot", confidence=current_thresholds['OPEN_LOOT'])
                    notify("status", "🗝️ Open loot prompt detected, pressing Shift.")
                    sleep(LOOT_OPEN_PRE_DELAY)
                    press_shift()
                    notify("status", "🔓 Shift pressed, waiting for loot window to open.")
                    sleep(LOOT_OPEN_POST_DELAY)

                loot_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_loot_window')
                rectangles_loot_window = vision_loot_window.find(loot_frame, current_thresholds['LOOT_WINDOW'])

                # Save debug screenshot (auto or manual trigger)
                should_save_loot_window = False
                if manual_capture_now:
                    should_save_loot_window = True
                elif debug_mode and bool(debug_mode.value) and debug_capture_loot_window and bool(debug_capture_loot_window.value) and debug_counters['loot_window'] < MAX_DEBUG_SCREENSHOTS:
                    should_save_loot_window = True

                if should_save_loot_window:
                    timestamp = datetime.now().strftime("%H%M%S_%f")
                    if manual_capture_now:
                        timestamp = f"MANUAL_{timestamp}"
                    save_debug_screenshot(loot_frame, template_loot_window, 'loot_window', timestamp, current_thresholds['LOOT_WINDOW'])
                    if not manual_capture_now:
                        debug_counters['loot_window'] += 1

                if rectangles_loot_window.any():
                    if show_confidence and bool(show_confidence.value):
                        notify("detection", f"Detected: Loot Window", template="Loot Window", confidence=current_thresholds['LOOT_WINDOW'])
                    # Check for message overlays first
                    if has_message_overlay(loot_frame):
                        notify("status", "💬 Loot window detected with message overlay, waiting for clear view.")
                        continue  # Skip processing until message disappears

                    # Calculate hash to detect duplicate windows
                    current_hash = hashlib.md5(loot_frame.tobytes()).hexdigest()
                    current_time = time.time()

                    # Clean up old hashes (> 5 minutes old)
                    processed_loot = {h: t for h, t in processed_loot.items()
                                      if current_time - t < 300}

                    # Check if we already processed this window
                    if current_hash in processed_loot:
                        time_since = current_time - processed_loot[current_hash]
                        notify("status", f"🔁 Duplicate loot window detected ({time_since:.1f}s ago), skipping.")
                        continue  # Skip to next loop iteration

                    # Store hash with timestamp
                    processed_loot[current_hash] = current_time

                    notify("status", "✨ Clean loot window detected, processing.")
                    loot_opened.value += 1
                    # Read screenshot enabled state from shared memory (allows real-time toggle)
                    save_screenshots = bool(screenshot_enabled.value) if screenshot_enabled is not None else True
                    current_img = check_legendary(loot_frame, hsv_filter_red, current_img, save_screenshots, session_folder, wincap, legendary_params, coords)
                    notify(
                        "loot",
                        "Loot window processed.",
                        loot_count=int(loot_opened.value),
                        legendary_count=int(legendaries.value),
                    )
                    notify("status", "👆 Clicking 'Take Small Items' button.")
                    click_with_logging(*coords['TAKE_SMALL_ITEMS_BUTTON'], label="Take Small Items")
                    sleep(TAKE_ITEMS_DELAY)

                    notify("status", "👀 Checking if items remain in loot window.")
                    loot_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_loot_window')
                    rectangles_loot_window = vision_loot_window.find(loot_frame, current_thresholds['LOOT_WINDOW'])

                    if rectangles_loot_window.any():
                        notify("status", "🗑️ Items still remain, clicking 'Trash' button.")
                        click_with_logging(*coords['TRASH_BUTTON'], label="Trash")
                        sleep(TAKE_ITEMS_DELAY)
                    else:
                        notify("status", "✅ All items collected, loot window closed.")

                enemy_hp_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_enemy_hp')
                rectangles_enemy_hp_full = vision_enemy_hp_full.find(enemy_hp_frame, current_thresholds['HP_FULL'])
                rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, current_thresholds['HP_DAMAGED'])
                rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, current_thresholds['HP_EMPTY'])

                # Save debug screenshots (auto or manual trigger)
                timestamp = datetime.now().strftime("%H%M%S_%f")
                if manual_capture_now:
                    timestamp = f"MANUAL_{timestamp}"
                    # Manual capture: save all 3 HP templates
                    save_debug_screenshot(enemy_hp_frame, template_hp_full, 'hp_full', timestamp, current_thresholds['HP_FULL'])
                    save_debug_screenshot(enemy_hp_frame, template_hp_damaged, 'hp_damaged', timestamp, current_thresholds['HP_DAMAGED'])
                    save_debug_screenshot(enemy_hp_frame, template_hp_empty, 'hp_empty', timestamp, current_thresholds['HP_EMPTY'])
                elif debug_mode and bool(debug_mode.value):
                    # Auto capture: respect flags and counters
                    if debug_capture_hp_full and bool(debug_capture_hp_full.value) and debug_counters['hp_full'] < MAX_DEBUG_SCREENSHOTS:
                        save_debug_screenshot(enemy_hp_frame, template_hp_full, 'hp_full', timestamp, current_thresholds['HP_FULL'])
                        debug_counters['hp_full'] += 1
                    if debug_capture_hp_damaged and bool(debug_capture_hp_damaged.value) and debug_counters['hp_damaged'] < MAX_DEBUG_SCREENSHOTS:
                        save_debug_screenshot(enemy_hp_frame, template_hp_damaged, 'hp_damaged', timestamp, current_thresholds['HP_DAMAGED'])
                        debug_counters['hp_damaged'] += 1
                    if debug_capture_hp_empty and bool(debug_capture_hp_empty.value) and debug_counters['hp_empty'] < MAX_DEBUG_SCREENSHOTS:
                        save_debug_screenshot(enemy_hp_frame, template_hp_empty, 'hp_empty', timestamp, current_thresholds['HP_EMPTY'])
                        debug_counters['hp_empty'] += 1

                if rectangles_enemy_hp_full.any() or rectangles_enemy_hp_damaged.any() or rectangles_enemy_hp_empty.any():
                    if show_confidence and bool(show_confidence.value):
                        if rectangles_enemy_hp_full.any():
                            notify("detection", f"Detected: Enemy HP Full", template="HP Full", confidence=current_thresholds['HP_FULL'])
                        elif rectangles_enemy_hp_damaged.any():
                            notify("detection", f"Detected: Enemy HP Damaged", template="HP Damaged", confidence=current_thresholds['HP_DAMAGED'])
                        elif rectangles_enemy_hp_empty.any():
                            notify("detection", f"Detected: Enemy HP Empty", template="HP Empty", confidence=current_thresholds['HP_EMPTY'])

                    if not rectangles_enemy_hp_damaged.any() and not rectangles_enemy_hp_empty.any():
                        # New enemy detected - reset attack logging flag
                        attacking_logged = False
                        notify("status", f"☠️ Enemy detected (full HP), waiting {wait_after_enemy_spawn.value}s before engaging.")
                        sleep(wait_after_enemy_spawn.value)
                        notify("status", "⚔️ Starting combat sequence (3x Ctrl).")
                        press_ctrl()
                        press_ctrl()
                        press_ctrl()
                        sleep(INITIAL_ATTACK_DELAY)

                    enemy_hp_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_enemy_hp')
                    rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, current_thresholds['HP_DAMAGED'])
                    rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, current_thresholds['HP_EMPTY'])

                    if rectangles_enemy_hp_damaged.any():
                        # Only log attack message once per enemy
                        if not attacking_logged:
                            notify("status", "🗡️ Enemy damaged, attacking (2x Ctrl).")
                            attacking_logged = True
                        press_ctrl()
                        press_ctrl()
                        sleep(attack_delay.value)

                # Send detection overlay data to GUI (if enabled)
                if overlay_enabled and bool(overlay_enabled.value):
                    try:
                        # Capture full game window
                        full_window = wincap.get_screenshot(GAME_WINDOW_TITLE)

                        if full_window is not None:
                            # Build zones dictionary with detection results
                            zones = {
                                'Open Loot': {
                                    'x': scaled_regions['crop_open_loot']['x'],
                                    'y': scaled_regions['crop_open_loot']['y'],
                                    'w': scaled_regions['crop_open_loot']['w'],
                                    'h': scaled_regions['crop_open_loot']['h'],
                                    'detected': rectangles_open_loot.any()
                                },
                                'Loot Window': {
                                    'x': scaled_regions['crop_loot_window']['x'],
                                    'y': scaled_regions['crop_loot_window']['y'],
                                    'w': scaled_regions['crop_loot_window']['w'],
                                    'h': scaled_regions['crop_loot_window']['h'],
                                    'detected': rectangles_loot_window.any()
                                },
                                'Enemy HP (Full)': {
                                    'x': scaled_regions['crop_enemy_hp']['x'],
                                    'y': scaled_regions['crop_enemy_hp']['y'],
                                    'w': scaled_regions['crop_enemy_hp']['w'],
                                    'h': scaled_regions['crop_enemy_hp']['h'],
                                    'detected': rectangles_enemy_hp_full.any()
                                },
                                'Enemy HP (Damaged)': {
                                    'x': scaled_regions['crop_enemy_hp']['x'],
                                    'y': scaled_regions['crop_enemy_hp']['y'],
                                    'w': scaled_regions['crop_enemy_hp']['w'],
                                    'h': scaled_regions['crop_enemy_hp']['h'],
                                    'detected': rectangles_enemy_hp_damaged.any()
                                },
                                'Enemy HP (Empty)': {
                                    'x': scaled_regions['crop_enemy_hp']['x'],
                                    'y': scaled_regions['crop_enemy_hp']['y'],
                                    'w': scaled_regions['crop_enemy_hp']['w'],
                                    'h': scaled_regions['crop_enemy_hp']['h'],
                                    'detected': rectangles_enemy_hp_empty.any()
                                }
                            }

                            # Serialize image and send to GUI
                            image_bytes = full_window.tobytes()
                            notify("detection_overlay",
                                   image=image_bytes,
                                   width=full_window.shape[1],
                                   height=full_window.shape[0],
                                   zones=zones)
                    except Exception as overlay_error:
                        # Don't crash bot if overlay fails
                        notify("error", f"⚠️ Overlay update failed: {overlay_error}")

            except Exception as e:
                notify("error", f"❌ Bot loop error: {e}")
                continue

        else:
            game_closed()

        if cv2.waitKey(1) == ord('q'):
            cv2.destroyAllWindows()
            break
