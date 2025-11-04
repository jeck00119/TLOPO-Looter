import cv2 as cv2
import ctypes
from ctypes import wintypes
import hashlib
import numpy as np
import os
import psutil
import pyttsx3
import sys
import threading
import time
import win32api as api
import win32con
import win32gui as gui
import winreg
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

# Data Storage Paths
SCREENSHOT_BASE_PATH = 'Data\\All Loot Screenshots'

# Resolution Modes (shared with GUI)
RESOLUTION_MODE_ADAPTIVE = 0
RESOLUTION_MODE_FORCED = 1
DEFAULT_RESOLUTION_MODE = RESOLUTION_MODE_ADAPTIVE
RESOLUTION_MODE_LABELS = {
    RESOLUTION_MODE_ADAPTIVE: "Scaled (auto-detect)",
    RESOLUTION_MODE_FORCED: "Force 1280x800",
}

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
    Returns: (success, error_message) - False if any directory creation failed
    """
    if session_folder:
        # Session-based structure
        targets = [
            get_data_path(f'{SCREENSHOT_BASE_PATH}\\{session_folder}\\Legendary Loot'),
            get_data_path(f'{SCREENSHOT_BASE_PATH}\\{session_folder}\\Regular Loot'),
        ]
    else:
        # Legacy flat structure (backward compatibility)
        targets = [
            get_data_path(f'{SCREENSHOT_BASE_PATH}\\Legendary Loot'),
            get_data_path(f'{SCREENSHOT_BASE_PATH}\\Regular Loot'),
        ]

    # Use centralized utility for consistency and error reporting
    for target in targets:
        success, error = ensure_directory_exists(target)
        if not success:
            return (False, f"Failed to create directory {target}: {error}")

    return (True, None)


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
    return get_data_path(f'{SCREENSHOT_BASE_PATH}\\{session_folder}\\{subfolder}\\{filename}')


def get_info_path(session_folder, filename):
    """Construct path for legendary info text file"""
    return get_data_path(f'{SCREENSHOT_BASE_PATH}\\{session_folder}\\Legendary Loot\\{filename}')


def save_debug_screenshot(frame, template, region_name, timestamp, threshold):
    """
    Save debug screenshot showing what's being matched.
    Stores captured region, template, and metadata for later review.
    """
    try:
        debug_folder = get_data_path('Data\\Debug')
        os.makedirs(debug_folder, exist_ok=True)

        region_path = os.path.join(debug_folder, f'{timestamp}_{region_name}_region.jpg')
        template_path = os.path.join(debug_folder, f'{timestamp}_{region_name}_template.jpg')
        info_path = os.path.join(debug_folder, f'{timestamp}_{region_name}_info.txt')

        cv2.imwrite(region_path, frame)
        cv2.imwrite(template_path, template)

        with open(info_path, 'w', encoding='utf-8') as info_file:
            info_file.write(f"Detection: {region_name}\n")
            info_file.write(f"Timestamp: {timestamp}\n")
            info_file.write(f"Threshold: {threshold:.2f}\n")
            info_file.write(f"Region size: {frame.shape[1]}x{frame.shape[0]}\n")
            info_file.write(f"Template size: {template.shape[1]}x{template.shape[0]}\n")
            info_file.write("\nFiles saved:\n")
            info_file.write(f"  Region: {region_path}\n")
            info_file.write(f"  Template: {template_path}\n")

        return True
    except Exception:
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

def check_window(force_base_resolution=False):
    """
    Checks if game window exists and optionally auto-corrects size.
    Returns window handle if found, 0 if not found.

    During startup validation: Called from subprocess (no PyQt5 interference).
    During bot operation: Called from bot process (no PyQt5 interference).
    Both contexts are safe for resize.
    """
    try:
        handle = gui.FindWindow(None, GAME_WINDOW_TITLE)
        if not handle:
            return 0

        # Restore if minimized
        left, top, right, bottom = gui.GetClientRect(handle)
        if right == 0 and bottom == 0:
            gui.ShowWindow(handle, win32con.SW_SHOWNORMAL)
            sleep(0.1)  # Give window time to restore

        if force_base_resolution:
            # Auto-correct window size if it's wrong (e.g., user resized it)
            # Only do quick correction (1 iteration) to not slow down bot
            client_rect = gui.GetClientRect(handle)
            current_w = client_rect[2]
            current_h = client_rect[3]

            # Check if size is significantly wrong (>10px off)
            error_w = abs(GAME_RESOLUTION[0] - current_w)
            error_h = abs(GAME_RESOLUTION[1] - current_h)

            if error_w > 10 or error_h > 10:
                # Size is wrong, do quick correction
                x0, y0, x1, y1 = gui.GetWindowRect(handle)
                window_w = x1 - x0
                window_h = y1 - y0

                # Calculate correction
                correction_w = GAME_RESOLUTION[0] - current_w
                correction_h = GAME_RESOLUTION[1] - current_h

                # Apply correction
                new_w = window_w + correction_w
                new_h = window_h + correction_h

                gui.MoveWindow(handle, x0, y0, new_w, new_h, True)
                sleep(0.1)

        return handle

    except Exception:
        return 0


def resize_window_iterative(handle, max_iterations=3):
    """
    Resize window using iterative error correction.
    Returns True if successful (within 10px tolerance), False otherwise.

    This is the method that worked in window_fix_tool.py testing.
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


def detect_resolution_and_scale(hwnd):
    """
    Detect current game resolution and calculate scale factors.
    Base resolution: 1280x800.
    Returns: (current_width, current_height, scale_x, scale_y)
    """
    try:
        rect = gui.GetClientRect(hwnd)
        current_w = rect[2]
        current_h = rect[3]

        if current_w == 0 or current_h == 0:
            return GAME_RESOLUTION[0], GAME_RESOLUTION[1], 1.0, 1.0

        scale_x = current_w / float(GAME_RESOLUTION[0])
        scale_y = current_h / float(GAME_RESOLUTION[1])
        return current_w, current_h, scale_x, scale_y
    except Exception:
        return GAME_RESOLUTION[0], GAME_RESOLUTION[1], 1.0, 1.0


def scale_coordinates(scale_x, scale_y):
    """
    Scale hardcoded button coordinates to current resolution.
    Returns: dictionary with scaled coordinate tuples.
    """
    return {
        'TAKE_SMALL_ITEMS_BUTTON': (int(TAKE_SMALL_ITEMS_BUTTON[0] * scale_x), int(TAKE_SMALL_ITEMS_BUTTON[1] * scale_y)),
        'TRASH_BUTTON': (int(TRASH_BUTTON[0] * scale_x), int(TRASH_BUTTON[1] * scale_y)),
    }


def scale_crop_regions(scale_x, scale_y, border_offset):
    """
    Scale WindowCapture crop regions to current resolution.
    Base coordinates include fixed borders, so subtract border, scale client coords, then add border back.
    """
    border_x, border_y = border_offset
    scaled_regions = {}

    for name, region in WindowCapture.DEFAULT_CROP_REGIONS.items():
        client_x = region['x'] - border_x
        client_y = region['y'] - border_y

        scaled_regions[name] = {
            'x': int(client_x * scale_x + border_x),
            'y': int(client_y * scale_y + border_y),
            'w': int(region['w'] * scale_x),
            'h': int(region['h'] * scale_y),
        }

    return scaled_regions


def scale_legendary_detection(scale_x, scale_y):
    """Scale legendary item detection parameters to current resolution."""
    return {
        'OFFSET_X': int(LEGENDARY_OFFSET_X * scale_x),
        'OFFSET_Y': int(LEGENDARY_OFFSET_Y * scale_y),
        'RANGE_1_START': int(min(LEGENDARY_RANGE_1) * scale_x),
        'RANGE_1_END': int(max(LEGENDARY_RANGE_1) * scale_x),
        'RANGE_2_START': int(min(LEGENDARY_RANGE_2) * scale_x),
        'RANGE_2_END': int(max(LEGENDARY_RANGE_2) * scale_x),
    }


def scale_template(template_img, scale_x, scale_y):
    """
    Scale a template image to match current resolution.
    Uses INTER_AREA for downscaling (better quality), INTER_CUBIC for upscaling.
    Returns: scaled template image.
    """
    if template_img is None:
        return None

    if scale_x == 1.0 and scale_y == 1.0:
        return template_img

    if scale_x < 1.0 or scale_y < 1.0:
        interpolation = cv2.INTER_AREA
    else:
        interpolation = cv2.INTER_CUBIC

    return cv2.resize(template_img, None, fx=scale_x, fy=scale_y, interpolation=interpolation)


def get_window_border_offset():
    """Return border offsets using WindowCapture helper."""
    try:
        wincap = WindowCapture()
        return wincap.get_client_offset(GAME_WINDOW_TITLE)
    except Exception:
        return WINDOW_BORDER_OFFSET


def check_dpi_settings(hwnd):
    """
    Check if window dimensions are correct (indicates proper DPI settings).
    Accepts dimensions within 10 pixels tolerance to account for window borders
    and minor DPI quirks. Requires DPI override set to "System" in game properties.
    Returns: (is_correct, error_message)
    """
    try:
        # Get actual client area dimensions
        client_rect = gui.GetClientRect(hwnd)
        actual_width = client_rect[2]
        actual_height = client_rect[3]
        expected_width, expected_height = GAME_RESOLUTION  # (1280, 800)

        # Calculate pixel difference
        width_diff = abs(actual_width - expected_width)
        height_diff = abs(actual_height - expected_height)

        # Allow 10 pixels tolerance for window borders and DPI quirks
        TOLERANCE = 10

        # If dimensions are exact or within tolerance
        if actual_width == expected_width and actual_height == expected_height:
            return (True, f"Resolution OK: Client area is {actual_width}x{actual_height}")
        elif width_diff <= TOLERANCE and height_diff <= TOLERANCE:
            # Close enough - show warning but don't block
            return (True,
                   f"Resolution OK (within tolerance): Client area is {actual_width}x{actual_height}, "
                   f"expected {expected_width}x{expected_height}. "
                   f"Difference: {width_diff}x{height_diff} pixels (tolerance: {TOLERANCE}px)")
        else:
            # Too far off - block startup
            return (False,
                   f"Window dimensions incorrect. Client area is {actual_width}x{actual_height}, "
                   f"expected {expected_width}x{expected_height} ({TOLERANCE}px tolerance).\n\n"
                   f"Troubleshooting:\n"
                   f"1. Set game to 1280x800 resolution in-game graphics settings\n"
                   f"2. Make sure game is in windowed mode (not fullscreen)\n"
                   f"3. Restart the bot to trigger auto-resize\n\n"
                   f"Note: Bot attempts automatic resize but Windows display scaling\n"
                   f"at {actual_width}x{actual_height} suggests game is DPI-unaware.\n"
                   f"Try setting game .exe compatibility: 'Override high DPI scaling' = 'System'")

    except Exception as e:
        # If check fails, don't block startup - log warning instead
        return (True, f"Resolution check skipped: {e}")


def check_dpi_registry_setting(hwnd):
    """
    Check if game executable has DPI override set in Windows registry.
    Returns: (status, exe_path, registry_value, message)
    Status: "correct", "incorrect", "not_set", "error"
    """
    try:
        # Get process ID from window handle
        process_id = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

        # Get executable path using psutil
        try:
            process = psutil.Process(process_id.value)
            exe_path = process.exe()
        except:
            return ("error", None, None, "Could not get process executable path")

        # Check registry for DPI override setting
        try:
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers",
                0,
                winreg.KEY_READ
            )

            try:
                value, reg_type = winreg.QueryValueEx(reg_key, exe_path)
                winreg.CloseKey(reg_key)

                # Check what type of DPI override is set
                # System = "~ DPIUNAWARE" (with space)
                # Application = "~ HIGHDPIAWARE"
                # System (Enhanced) = "~ GDIDPISCALING DPIUNAWARE"

                if "~ DPIUNAWARE" in value and "GDIDPISCALING" not in value:
                    return ("correct", exe_path, value, "DPI Override set to 'System' (correct)")
                elif "~ HIGHDPIAWARE" in value:
                    return ("incorrect", exe_path, value, "DPI Override set to 'Application' (should be 'System')")
                elif "~ GDIDPISCALING DPIUNAWARE" in value:
                    return ("incorrect", exe_path, value, "DPI Override set to 'System (Enhanced)' (should be 'System')")
                else:
                    return ("incorrect", exe_path, value, f"Unknown DPI Override: {value}")

            except FileNotFoundError:
                winreg.CloseKey(reg_key)
                return ("not_set", exe_path, None, "No DPI Override set in registry")

        except FileNotFoundError:
            return ("not_set", exe_path, None, "Registry key does not exist")

    except Exception as e:
        return ("error", None, None, f"Error checking registry: {e}")


def set_dpi_override_to_system(exe_path):
    """
    Automatically set DPI override to 'System' in Windows registry.

    Args:
        exe_path: Full path to executable

    Returns: (success, message)
    """
    try:
        # Registry key path
        key_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"

        # Try to open existing key or create if it doesn't exist
        try:
            reg_key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_WRITE
            )
        except FileNotFoundError:
            # Key doesn't exist, create it
            reg_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)

        # Set the DPI override value
        # "~ DPIUNAWARE" = System (note the space after ~)
        winreg.SetValueEx(reg_key, exe_path, 0, winreg.REG_SZ, "~ DPIUNAWARE")
        winreg.CloseKey(reg_key)

        return (True, "Successfully set DPI override to 'System'")

    except PermissionError:
        return (False, "Permission denied. Try running as administrator.")
    except Exception as e:
        return (False, f"Failed to set registry value: {e}")


def handle_dpi_configuration(hwnd):
    """
    Handle DPI configuration workflow: check status and apply fix if needed.

    This function centralizes the DPI configuration logic that was previously
    split between bot_logic.py and main_gui.py.

    Args:
        hwnd: Window handle

    Returns: dict with keys:
        - success: bool - Whether DPI is correctly configured (after fix if applied)
        - action: str - "already_correct", "fixed", "failed", "error"
        - exe_path: str - Executable path
        - message: str - User-friendly message
        - restart_required: bool - Whether game needs restart
    """
    result = {
        'success': False,
        'action': 'error',
        'exe_path': None,
        'message': '',
        'restart_required': False
    }

    try:
        # Check current DPI status
        status, exe_path, reg_value, status_message = check_dpi_registry_setting(hwnd)
        result['exe_path'] = exe_path

        if status == "error":
            result['message'] = status_message
            return result

        if status == "correct":
            result['success'] = True
            result['action'] = 'already_correct'
            result['message'] = "DPI override already correctly configured"
            return result

        # DPI needs fixing (status is "not_set" or "incorrect")
        if not exe_path:
            result['message'] = "Could not determine executable path"
            return result

        # Attempt to apply fix
        fix_success, fix_message = set_dpi_override_to_system(exe_path)

        if fix_success:
            result['success'] = True
            result['action'] = 'fixed'
            result['message'] = fix_message
            result['restart_required'] = True
        else:
            result['action'] = 'failed'
            result['message'] = fix_message

        return result

    except Exception as e:
        result['message'] = f"Error handling DPI configuration: {e}"
        return result


# ===========================
# END WINDOW UTILITIES
# ===========================


def validate_game_ready(resolution_mode=DEFAULT_RESOLUTION_MODE):
    """
    Validate all requirements before starting bot.
    Returns: (success, error_message, details)
    """
    details = {
        'resolution_mode': resolution_mode,
    }

    force_base_resolution = resolution_mode == RESOLUTION_MODE_FORCED

    # Check 1: Game window exists
    handle = check_window(force_base_resolution=force_base_resolution)
    if not handle:
        return (False, "Game window not detected. Please start the game.", details)
    details['window_handle'] = handle

    current_w, current_h, scale_x, scale_y = detect_resolution_and_scale(handle)
    details['detected_resolution'] = f"{current_w}x{current_h}"
    details['client_size'] = f"{current_w}x{current_h}"

    if force_base_resolution:
        details['initial_size'] = f"{current_w}x{current_h}"
        resize_success = resize_window_iterative(handle, max_iterations=5)
        details['resize_attempted'] = True
        details['resize_success'] = resize_success
        sleep(0.2)

        dpi_correct, dpi_msg = check_dpi_settings(handle)
        details['dpi_message'] = dpi_msg
        if not dpi_correct:
            final_rect = gui.GetClientRect(handle)
            final_w = final_rect[2]
            final_h = final_rect[3]
            details['final_size'] = f"{final_w}x{final_h}"

            enhanced_msg = f"{dpi_msg}\n\nDiagnostics:\n"
            enhanced_msg += f"  Initial size: {current_w}x{current_h}\n"
            enhanced_msg += f"  After resize: {final_w}x{final_h}\n"
            enhanced_msg += f"  Target: {GAME_RESOLUTION[0]}x{GAME_RESOLUTION[1]}"
            return (False, enhanced_msg, details)

        # Refresh resolution info after resize (should now match 1280x800)
        current_w, current_h, scale_x, scale_y = detect_resolution_and_scale(handle)
        details['post_resize_resolution'] = f"{current_w}x{current_h}"
        scale_x = 1.0
        scale_y = 1.0
    else:
        details['resize_attempted'] = False
        details['dpi_message'] = "Adaptive scaling enabled"

    details['scale_factors'] = f"{scale_x:.2f}x, {scale_y:.2f}x"
    details['scale_x'] = scale_x
    details['scale_y'] = scale_y
    details['resolution_ok'] = True
    details['border_offset'] = get_window_border_offset()

    # Check 4: Template images exist
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

    # Check 5: Data folder writable
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

    # Check 6: DPI override configured correctly
    dpi_status, exe_path, dpi_value, dpi_message = check_dpi_registry_setting(handle)
    details['dpi_status'] = dpi_status
    details['dpi_exe_path'] = exe_path
    details['dpi_registry_value'] = dpi_value

    if dpi_status == "error":
        # Error checking DPI - don't block, but warn
        details['dpi_warning'] = dpi_message
    elif dpi_status in ["not_set", "incorrect"]:
        # DPI override missing or wrong - offer to fix automatically
        error_msg = f"DPI Override Configuration Issue\n\n"
        error_msg += f"Game: {exe_path}\n"
        error_msg += f"Status: {dpi_message}\n\n"
        error_msg += f"The bot can automatically fix this for you.\n\n"
        error_msg += f"Would you like to apply the fix?\n"
        error_msg += f"(After fixing, you MUST restart the game for changes to take effect)"

        # Return special status for GUI to handle with Yes/No dialog
        return (False, error_msg, details)

    details['dpi_ok'] = True

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


def overlay_update_thread(overlay_enabled, overlay_stop_event, status_queue, scaled_regions,
                          threshold_open_loot, threshold_loot_window, threshold_hp_full,
                          threshold_hp_damaged, scale_x, scale_y,
                          template_open_loot, template_loot_window, template_hp_full,
                          template_hp_damaged, border_offset, client_width, client_height):
    """
    Dedicated thread for overlay updates (aim for ~30 FPS).
    Provides smooth real-time visualization without blocking main bot loop.
    """
    wincap_overlay = WindowCapture()

    border_x, border_y = border_offset
    client_area_region = {
        'crop_client_area': {
            'x': border_x,
            'y': border_y,
            'w': client_width,
            'h': client_height
        }
    }

    all_regions = {**scaled_regions, **client_area_region}
    wincap_overlay.set_crop_regions(all_regions)

    # Vision objects with pre-scaled templates
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

    template_requirements = {
        'crop_open_loot': (template_open_loot.shape[1], template_open_loot.shape[0]),
        'crop_loot_window': (template_loot_window.shape[1], template_loot_window.shape[0]),
        'crop_enemy_hp': (template_hp_full.shape[1], template_hp_full.shape[0]),
    }

    threshold_adjustment = 1.0
    if scale_x < 1.0 or scale_y < 1.0:
        min_scale = min(scale_x, scale_y)
        threshold_adjustment = 0.85 + (min_scale * 0.15)

    target_frame_time = 1.0 / 30.0
    invalid_zone_reported = set()

    while not overlay_stop_event.is_set():
        frame_start = time.time()

        try:
            if not overlay_enabled or not bool(overlay_enabled.value):
                time.sleep(0.1)
                continue

            client_area = wincap_overlay.get_screenshot(GAME_WINDOW_TITLE, crop='crop_client_area')
            if client_area is None:
                time.sleep(0.1)
                continue

            base_open_loot = float(threshold_open_loot.value) if threshold_open_loot else THRESHOLD_OPEN_LOOT
            base_loot_window = float(threshold_loot_window.value) if threshold_loot_window else THRESHOLD_LOOT_WINDOW
            base_hp_full = float(threshold_hp_full.value) if threshold_hp_full else THRESHOLD_HP_FULL
            base_hp_damaged = float(threshold_hp_damaged.value) if threshold_hp_damaged else THRESHOLD_HP_DAMAGED

            current_thresholds = {
                'OPEN_LOOT': base_open_loot * threshold_adjustment,
                'LOOT_WINDOW': base_loot_window * threshold_adjustment,
                'HP_FULL': base_hp_full * threshold_adjustment,
                'HP_DAMAGED': base_hp_damaged * threshold_adjustment,
            }

            zones = []

            def evaluate_zone(region_key, vision_obj, threshold_key):
                region = scaled_regions.get(region_key)
                if not region:
                    return
                template_w, template_h = template_requirements.get(region_key, (1, 1))
                valid_size = region['w'] >= template_w and region['h'] >= template_h
                rectangles = None

                if valid_size:
                    crop = client_area[
                        (region['y'] - border_y):(region['y'] - border_y) + region['h'],
                        (region['x'] - border_x):(region['x'] - border_x) + region['w']
                    ]
                    try:
                        rectangles = vision_obj.find(crop, current_thresholds[threshold_key])
                        invalid_zone_reported.discard(region_key)
                    except cv2.error as cv_err:
                        rectangles = None
                        valid_size = False
                        if status_queue and region_key not in invalid_zone_reported:
                            status_queue.put({
                                "type": "overlay_error",
                                "message": (
                                    f"Overlay zone '{region_key}' caused OpenCV error: {cv_err}. "
                                    f"Reset or enlarge the zone in the overlay window."
                                ),
                            })
                        invalid_zone_reported.add(region_key)
                else:
                    crop = None
                    if status_queue and region_key not in invalid_zone_reported:
                        status_queue.put({
                            "type": "overlay_error",
                            "message": (
                                f"Overlay zone '{region_key}' is smaller than its template size "
                                f"({region['w']}x{region['h']} vs >= {template_w}x{template_h}); "
                                "increase the zone in the overlay window."
                            ),
                        })
                    invalid_zone_reported.add(region_key)

                rel_x = region['x'] - border_x
                rel_y = region['y'] - border_y
                detected = bool(rectangles.any()) if rectangles is not None else False
                zones.append({
                    'name': region_key,
                    'x': rel_x,
                    'y': rel_y,
                    'w': region['w'],
                    'h': region['h'],
                    'detected': detected,
                    'min_w': template_w,
                    'min_h': template_h,
                    'valid': valid_size,
                })

            evaluate_zone('crop_open_loot', vision_open_loot, 'OPEN_LOOT')
            evaluate_zone('crop_loot_window', vision_loot_window, 'LOOT_WINDOW')
            evaluate_zone('crop_enemy_hp', vision_enemy_hp_full, 'HP_FULL')

            image_bytes = client_area.tobytes()
            if status_queue:
                status_queue.put({
                    "type": "detection_overlay",
                    "image": image_bytes,
                    "width": client_area.shape[1],
                    "height": client_area.shape[0],
                    "zones": zones,
                    "resolution": f"{client_width}x{client_height}",
                    "scale_x": scale_x,
                    "scale_y": scale_y,
                    "border_offset": border_offset,
                })

        except Exception as overlay_error:
            if status_queue:
                status_queue.put({
                    "type": "overlay_error",
                    "message": f"Overlay thread error: {overlay_error}",
                })
            time.sleep(0.2)

        frame_duration = time.time() - frame_start
        sleep_time = target_frame_time - frame_duration
        if sleep_time > 0:
            time.sleep(sleep_time)

def run_bot(
    started,
    attack_delay,
    wait_after_enemy_spawn,
    gui_settings_opened,
    loot_opened,
    legendaries,
    status_queue=None,
    screenshot_enabled=None,
    resolution_mode=None,
    threshold_open_loot=None,
    threshold_loot_window=None,
    threshold_hp_full=None,
    threshold_hp_damaged=None,
    threshold_hp_empty=None,
    debug_mode=None,
    show_coords=None,
    show_confidence=None,
    debug_capture_open_loot=None,
    debug_capture_loot_window=None,
    debug_capture_hp_full=None,
    debug_capture_hp_damaged=None,
    debug_capture_hp_empty=None,
    manual_capture_trigger=None,
    overlay_enabled=None,
    disable_bot_actions=None,
    use_overlay_zones_flag=None,
    overlay_zones_dict=None,
    session_folder=None,
):
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

    def get_bool(value):
        try:
            return bool(value.value)
        except Exception:
            return False

    def get_float(value, default):
        try:
            return float(value.value)
        except Exception:
            return default

    def actions_enabled():
        """Check if bot actions are enabled (returns True if actions should execute)"""
        if disable_bot_actions is None:
            return True
        try:
            return not bool(disable_bot_actions.value)
        except Exception:
            return True

    def click_with_logging(x, y, label=""):
        if actions_enabled():
            press_left_click(x, y)
        else:
            notify("status", f"[DRY RUN] Would click at ({x}, {y}) ({label})")
        if get_bool(show_coords):
            msg = f"Click at ({x}, {y})"
            if label:
                msg += f" - {label}"
            notify("click", msg, x=x, y=y)
        if overlay_enabled:
            color = (255, 255, 0)
            if label:
                lowered = label.lower()
                if "take" in lowered:
                    color = (0, 255, 0)
                elif "trash" in lowered:
                    color = (255, 165, 0)
                elif "legendary" in lowered:
                    color = (255, 0, 255)
            notify("overlay_click", x=x, y=y, label=label or "Click", color=color)

    def capture_debug(region_name, frame, template, threshold):
        if not get_bool(debug_mode):
            return
        flag_map = {
            "open_loot": debug_capture_open_loot,
            "loot_window": debug_capture_loot_window,
            "hp_full": debug_capture_hp_full,
            "hp_damaged": debug_capture_hp_damaged,
            "hp_empty": debug_capture_hp_empty,
        }
        flag = flag_map.get(region_name)
        if flag is not None and not get_bool(flag):
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_debug_screenshot(frame, template, region_name, timestamp, threshold)

    start_time = datetime.now()
    if session_folder is None:
        session_folder = start_time.strftime("Session_%d-%m-%Y_%H.%M.%S")
    notify("status", f"Bot loop started. Session: {session_folder}")

    screenshot_active = True if screenshot_enabled is None else get_bool(screenshot_enabled)
    if screenshot_active:
        success, error = ensure_data_directories(session_folder)
        if not success:
            notify("error", f"Unable to create screenshot directories: {error}")
            screenshot_active = False

    resolution_mode_value = DEFAULT_RESOLUTION_MODE
    if resolution_mode is not None:
        try:
            resolution_mode_value = int(resolution_mode.value)
        except Exception:
            resolution_mode_value = DEFAULT_RESOLUTION_MODE

    force_base_resolution = resolution_mode_value == RESOLUTION_MODE_FORCED

    handle = check_window(force_base_resolution=force_base_resolution)
    if not handle:
        notify("error", "Game window not found when starting loop.")
        started.value = False
        return

    current_w, current_h, scale_x, scale_y = detect_resolution_and_scale(handle)
    if force_base_resolution:
        scale_x = 1.0
        scale_y = 1.0
        current_w = GAME_RESOLUTION[0]
        current_h = GAME_RESOLUTION[1]

    notify("status", f"Detected resolution {current_w}x{current_h} (scale {scale_x:.2f}x, {scale_y:.2f}x)")

    border_offset = get_window_border_offset()
    scaled_regions = scale_crop_regions(scale_x, scale_y, border_offset)
    coords = scale_coordinates(scale_x, scale_y)
    legendary_params = scale_legendary_detection(scale_x, scale_y)

    wincap = WindowCapture()
    wincap.set_crop_regions(scaled_regions)

    base_scaled_regions = dict(scaled_regions)
    overlay_snapshot = None
    overlay_active = False
    min_template_sizes = {}

    def read_overlay_regions():
        if overlay_zones_dict is None:
            return None
        try:
            shared_items = dict(overlay_zones_dict)
        except Exception:
            return None
        cleaned = {}
        for name, region in shared_items.items():
            if not isinstance(region, dict):
                continue
            try:
                cleaned[name] = {
                    "x": int(region.get("x", 0)),
                    "y": int(region.get("y", 0)),
                    "w": int(region.get("w", 0)),
                    "h": int(region.get("h", 0)),
                }
            except Exception:
                continue
        return cleaned or None

    def convert_overlay_regions_to_window(regions):
        if not regions:
            return None
        border_x, border_y = border_offset
        converted = {}
        for name, region in regions.items():
            try:
                size_floor = min_template_sizes.get(name, {})
                min_w = max(1, int(size_floor.get("w", 1)))
                min_h = max(1, int(size_floor.get("h", 1)))
                width = max(min_w, max(1, int(region["w"])))
                height = max(min_h, max(1, int(region["h"])))
                converted[name] = {
                    "x": int(region["x"] + border_x),
                    "y": int(region["y"] + border_y),
                    "w": width,
                    "h": height,
                }
            except Exception:
                continue
        return converted or None

    def refresh_overlay_regions(force=False):
        nonlocal overlay_snapshot, overlay_active

        flag_active = False
        if use_overlay_zones_flag is not None:
            try:
                flag_active = bool(use_overlay_zones_flag.value)
            except Exception:
                flag_active = False

        if flag_active:
            shared = read_overlay_regions()
            converted = convert_overlay_regions_to_window(shared)
            if converted:
                if force or not overlay_active or converted != overlay_snapshot:
                    overlay_snapshot = converted
                    overlay_active = True
                    combined = dict(base_scaled_regions)
                    combined.update(converted)
                    scaled_regions.clear()
                    scaled_regions.update(combined)
                    wincap.set_crop_regions(scaled_regions)
                    notify("status", f"Overlay detection zones applied ({len(converted)} regions).")
            else:
                if overlay_active or force:
                    overlay_active = False
                    overlay_snapshot = None
                    scaled_regions.clear()
                    scaled_regions.update(base_scaled_regions)
                    wincap.set_crop_regions(scaled_regions)
                    if not force:
                        notify("status", "Overlay detection zones disabled (no custom regions).")
        else:
            if overlay_active or (force and overlay_snapshot is not None):
                overlay_active = False
                overlay_snapshot = None
                scaled_regions.clear()
                scaled_regions.update(base_scaled_regions)
                wincap.set_crop_regions(scaled_regions)
                if not force:
                    notify("status", "Overlay detection zones disabled.")

    refresh_overlay_regions(force=True)

    img_dir = resource_path("img")

    def load_template(name):
        path = os.path.join(img_dir, name)
        template = cv2.imread(path)
        if template is None:
            raise FileNotFoundError(f"Template missing: {name}")
        return scale_template(template, scale_x, scale_y)

    try:
        template_open_loot = load_template('open_loot.jpg')
        template_loot_window = load_template('loot_window.jpg')
        template_hp_full = load_template('full_hp.jpg')
        template_hp_damaged = load_template('damaged_hp.jpg')
        template_hp_empty = load_template('empty_hp.jpg')
    except Exception as exc:
        notify("error", f"Failed to load templates: {exc}")
        started.value = False
        return

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

    template_requirements = {
        'crop_open_loot': (vision_open_loot.needle_w, vision_open_loot.needle_h),
        'crop_loot_window': (vision_loot_window.needle_w, vision_loot_window.needle_h),
        'crop_enemy_hp': (
            max(vision_enemy_hp_full.needle_w, vision_enemy_hp_damaged.needle_w, vision_enemy_hp_empty.needle_w),
            max(vision_enemy_hp_full.needle_h, vision_enemy_hp_damaged.needle_h, vision_enemy_hp_empty.needle_h),
        ),
    }

    for name, (tpl_w, tpl_h) in template_requirements.items():
        min_template_sizes[name] = {
            "w": max(1, int(tpl_w)),
            "h": max(1, int(tpl_h)),
        }

    overlay_invalid_zones = set()

    def zone_detection_allowed(zone_name):
        region = scaled_regions.get(zone_name)
        if region is None:
            return False
        min_w, min_h = template_requirements.get(zone_name, (1, 1))
        if region['w'] < min_w or region['h'] < min_h:
            if zone_name not in overlay_invalid_zones:
                notify(
                    "status",
                    (
                        f"Overlay zone '{zone_name}' is smaller than required template size "
                        f"({region['w']}x{region['h']} vs >= {min_w}x{min_h}); enlarge it in the overlay."
                    ),
                )
                overlay_invalid_zones.add(zone_name)
            return False
        overlay_invalid_zones.discard(zone_name)
        return True

    vision_loot = Vision(None)

    hsv_filter_red = HsvFilter(**HSV_LEGENDARY_RED)

    threshold_adjustment = 1.0
    if scale_x < 1.0 or scale_y < 1.0:
        min_scale = min(scale_x, scale_y)
        threshold_adjustment = 0.85 + (min_scale * 0.15)
        notify("status", f"Resolution below 1280x800 detected; adjusting thresholds by {threshold_adjustment:.2f}")

    overlay_stop_event = threading.Event()
    overlay_thread = None
    if overlay_enabled is not None:
        overlay_thread = threading.Thread(
            target=overlay_update_thread,
            args=(
                overlay_enabled,
                overlay_stop_event,
                status_queue,
                scaled_regions,
                threshold_open_loot,
                threshold_loot_window,
                threshold_hp_full,
                threshold_hp_damaged,
                scale_x,
                scale_y,
                template_open_loot,
                template_loot_window,
                template_hp_full,
                template_hp_damaged,
                border_offset,
                current_w,
                current_h,
            ),
            daemon=True,
        )
        overlay_thread.start()

    processed_loot = {}
    attacking_logged = False
    current_img = _initial_image_index()
    last_manual_capture = manual_capture_trigger.value if manual_capture_trigger else 0

    def check_legendary(frame, save_screenshots):
        nonlocal current_img
        try:
            if save_screenshots:
                success, error = ensure_data_directories(session_folder)
                if not success:
                    notify("error", f"Screenshot directory error: {error}")
                    save_screenshots = False

            mask = vision_loot.apply_hsv_filter(frame, hsv_filter_red)
            kernel = np.ones(DILATION_KERNEL_SIZE, "uint8")
            mask = cv2.dilate(mask, kernel)
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            range_1_start = legendary_params['RANGE_1_START']
            range_1_end = legendary_params['RANGE_1_END']
            range_2_start = legendary_params['RANGE_2_START']
            range_2_end = legendary_params['RANGE_2_END']

            is_legendary = False
            legendary_x = None
            legendary_y = None

            for contour in contours:
                area = cv2.contourArea(contour)
                if area <= MIN_CONTOUR_AREA:
                    continue
                x, y, w, h = cv2.boundingRect(contour)
                calculated_x = x + legendary_params['OFFSET_X']
                if (range_1_start <= calculated_x <= range_1_end) or (range_2_start <= calculated_x <= range_2_end):
                    is_legendary = True
                    legendary_x = calculated_x
                    legendary_y = y + legendary_params['OFFSET_Y']
                    break

            if is_legendary and legendary_x is not None and legendary_y is not None:
                notify("status", f"Legendary item detected at ({legendary_x}, {legendary_y}).")
                if save_screenshots:
                    path = get_screenshot_path(session_folder, f'Legendary_{current_img}.jpg', legendary=True)
                    cv2.imwrite(path, frame)
                    notify("status", f"Screenshot saved: {os.path.basename(path)}")

                engine.say("Legendary Found")
                engine.runAndWait()

                notify("status", "Double-clicking legendary item (attempt 1).")
                click_with_logging(legendary_x, legendary_y, "Legendary click 1")
                click_with_logging(legendary_x, legendary_y, "Legendary click 2")

                notify("status", "Waiting 1s before verification.")
                sleep(1.0)

                verification_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_loot_window')
                verification_mask = vision_loot.apply_hsv_filter(verification_frame, hsv_filter_red)
                verification_mask = cv2.dilate(verification_mask, kernel)
                verification_contours, _ = cv2.findContours(verification_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

                legendary_still_visible = False
                for contour in verification_contours:
                    area = cv2.contourArea(contour)
                    if area <= MIN_CONTOUR_AREA:
                        continue
                    vx, vy, vw, vh = cv2.boundingRect(contour)
                    calc_x = vx + legendary_params['OFFSET_X']
                    if (range_1_start <= calc_x <= range_1_end) or (range_2_start <= calc_x <= range_2_end):
                        legendary_still_visible = True
                        break

                if legendary_still_visible:
                    notify("status", "Legendary still visible; retrying double-click and fallback.")
                    if actions_enabled():
                        click_with_logging(legendary_x, legendary_y, "Legendary retry 1")
                        click_with_logging(legendary_x, legendary_y, "Legendary retry 2")
                        sleep(1.0)
                        click_with_logging(*coords['TAKE_SMALL_ITEMS_BUTTON'], label="Take Small Items fallback")
                    else:
                        notify("status", "[DRY RUN] Would retry legendary clicks and fallback")
                        sleep(1.0)
                    if save_screenshots:
                        fallback_path = get_screenshot_path(
                            session_folder,
                            f'Legendary_{current_img}.jpg',
                            legendary=True,
                            fallback=True,
                        )
                        cv2.imwrite(fallback_path, verification_frame)
                        notify("status", f"Fallback screenshot saved: {os.path.basename(fallback_path)}")
                    notify("legendary_fallback", "Legendary required fallback", loot_count=int(loot_opened.value))
                else:
                    notify("status", "Legendary confirmed collected.")
                    notify("legendary_success", "Legendary collected successfully", loot_count=int(loot_opened.value))

                current_img += 1
                with legendaries.get_lock():
                    legendaries.value += 1
                notify("legendary", "Legendary loot recorded.", legendary=True, legendary_count=int(legendaries.value))
            else:
                notify("status", "No legendary items detected in loot window.")
                if save_screenshots:
                    path = get_screenshot_path(session_folder, f'{current_img}.jpg', legendary=False)
                    cv2.imwrite(path, frame)
                    notify("status", f"Regular loot screenshot saved: {os.path.basename(path)}")
                current_img += 1

        except Exception as exc:
            notify("error", f"Legendary detection error: {exc}")
            current_img += 1

    try:
        while True:
            sleep(LOOP_DELAY)

            refresh_overlay_regions()

            if check_window(force_base_resolution=force_base_resolution) == 0:
                notify("status", "Game window closed; stopping bot.")
                break

            save_screenshots = screenshot_active and (get_bool(screenshot_enabled) if screenshot_enabled else True)

            current_threshold_open = get_float(threshold_open_loot, THRESHOLD_OPEN_LOOT) * threshold_adjustment
            current_threshold_loot = get_float(threshold_loot_window, THRESHOLD_LOOT_WINDOW) * threshold_adjustment
            current_threshold_hp_full = get_float(threshold_hp_full, THRESHOLD_HP_FULL) * threshold_adjustment
            current_threshold_hp_damaged = get_float(threshold_hp_damaged, THRESHOLD_HP_DAMAGED) * threshold_adjustment
            current_threshold_hp_empty = get_float(threshold_hp_empty, THRESHOLD_HP_EMPTY)

            open_loot_frame = None
            rectangles_open_loot = np.empty((0,), dtype=np.float32)
            if zone_detection_allowed('crop_open_loot'):
                open_loot_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_open_loot')
                rectangles_open_loot = vision_open_loot.find(open_loot_frame, current_threshold_open)
            if rectangles_open_loot.any():
                if open_loot_frame is not None:
                    capture_debug('open_loot', open_loot_frame, template_open_loot, current_threshold_open)
                if actions_enabled():
                    notify("status", "Open loot prompt detected; pressing Shift.")
                    sleep(LOOT_OPEN_PRE_DELAY)
                    press_shift()
                    notify("status", "Shift pressed; waiting for loot window.")
                    sleep(LOOT_OPEN_POST_DELAY)
                else:
                    notify("status", "[DRY RUN] Would press Shift to open loot")
                    sleep(LOOT_OPEN_PRE_DELAY + LOOT_OPEN_POST_DELAY)

            loot_frame = None
            rectangles_loot_window = np.empty((0,), dtype=np.float32)
            if zone_detection_allowed('crop_loot_window'):
                loot_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_loot_window')
                rectangles_loot_window = vision_loot_window.find(loot_frame, current_threshold_loot)
            if rectangles_loot_window.any():
                if loot_frame is not None:
                    capture_debug('loot_window', loot_frame, template_loot_window, current_threshold_loot)

                if has_message_overlay(loot_frame):
                    notify("status", "Loot window has overlay text; waiting for clear view.")
                    continue

                loot_hash = hashlib.md5(loot_frame.tobytes()).hexdigest()
                now_ts = time.time()
                processed_loot = {h: t for h, t in processed_loot.items() if now_ts - t < 300}
                if loot_hash in processed_loot:
                    notify("status", "Duplicate loot window detected; skipping.")
                    continue
                processed_loot[loot_hash] = now_ts

                loot_opened.value += 1
                notify("status", "Processing loot window.")
                check_legendary(loot_frame, save_screenshots)
                notify("loot", "Loot window processed.", loot_count=int(loot_opened.value), legendary_count=int(legendaries.value))

                if actions_enabled():
                    click_with_logging(*coords['TAKE_SMALL_ITEMS_BUTTON'], label="Take Small Items")
                    sleep(TAKE_ITEMS_DELAY)
                else:
                    notify("status", "[DRY RUN] Would click Take Small Items button")
                    sleep(TAKE_ITEMS_DELAY)

                loot_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_loot_window')
                rectangles_loot_window = vision_loot_window.find(loot_frame, current_threshold_loot)
                if rectangles_loot_window.any():
                    if actions_enabled():
                        notify("status", "Items remain; clicking Trash.")
                        click_with_logging(*coords['TRASH_BUTTON'], label="Trash Button")
                    else:
                        notify("status", "[DRY RUN] Would click Trash button")
                    sleep(TAKE_ITEMS_DELAY)
                else:
                    notify("status", "Loot window cleared.")

            enemy_hp_frame = None
            rectangles_enemy_hp_full = np.empty((0,), dtype=np.float32)
            rectangles_enemy_hp_damaged = np.empty((0,), dtype=np.float32)
            rectangles_enemy_hp_empty = np.empty((0,), dtype=np.float32)
            if zone_detection_allowed('crop_enemy_hp'):
                enemy_hp_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_enemy_hp')
                rectangles_enemy_hp_full = vision_enemy_hp_full.find(enemy_hp_frame, current_threshold_hp_full)
                rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, current_threshold_hp_damaged)
                rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, current_threshold_hp_empty)

            if rectangles_enemy_hp_full.any() or rectangles_enemy_hp_damaged.any() or rectangles_enemy_hp_empty.any():
                if rectangles_enemy_hp_full.any() and not rectangles_enemy_hp_damaged.any() and not rectangles_enemy_hp_empty.any():
                    attacking_logged = False
                    notify("status", f"Enemy detected; waiting {wait_after_enemy_spawn.value}s before engaging.")
                    sleep(wait_after_enemy_spawn.value)
                    if actions_enabled():
                        notify("status", "Starting combat sequence (3x Ctrl).")
                        press_ctrl()
                        press_ctrl()
                        press_ctrl()
                        sleep(INITIAL_ATTACK_DELAY)
                    else:
                        notify("status", "[DRY RUN] Would start combat with 3x Ctrl")
                        sleep(INITIAL_ATTACK_DELAY)

                if zone_detection_allowed('crop_enemy_hp'):
                    enemy_hp_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_enemy_hp')
                    rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, current_threshold_hp_damaged)
                    rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, current_threshold_hp_empty)
                else:
                    rectangles_enemy_hp_damaged = np.empty((0,), dtype=np.float32)
                    rectangles_enemy_hp_empty = np.empty((0,), dtype=np.float32)

                if rectangles_enemy_hp_damaged.any():
                    if not attacking_logged:
                        if actions_enabled():
                            notify("status", "Enemy damaged; continuing attacks (2x Ctrl).")
                        else:
                            notify("status", "[DRY RUN] Would continue attacking with 2x Ctrl")
                        attacking_logged = True
                    if actions_enabled():
                        press_ctrl()
                        press_ctrl()
                    else:
                        pass  # Already logged above on first iteration
                    sleep(attack_delay.value)

            if manual_capture_trigger is not None:
                try:
                    manual_value = manual_capture_trigger.value
                except Exception:
                    manual_value = last_manual_capture
                if manual_value != last_manual_capture:
                    last_manual_capture = manual_value
                    notify("status", "Manual debug capture requested.")
                    if open_loot_frame is not None:
                        capture_debug('open_loot', open_loot_frame, template_open_loot, current_threshold_open)
                    if loot_frame is not None:
                        capture_debug('loot_window', loot_frame, template_loot_window, current_threshold_loot)
                    if enemy_hp_frame is not None:
                        capture_debug('hp_full', enemy_hp_frame, template_hp_full, current_threshold_hp_full)

    except Exception as exc:
        notify("error", f"Bot loop terminated due to error: {exc}")
    finally:
        if overlay_enabled is not None and overlay_thread is not None:
            overlay_stop_event.set()
            overlay_thread.join(timeout=1.0)

        with started.get_lock():
            started.value = False
