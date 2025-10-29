import cv2 as cv2
import numpy as np
import os
import pyttsx3
import sys
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
THRESHOLD_LOOT_WINDOW = 0.40
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


def _initial_image_index():
    """
    Returns initial image index for a new session.
    Always returns 1 for session-based folders (fresh counter each session).
    """
    return 1


img_dir = resource_path("img")
# current_img moved inside run_bot() to prevent race conditions


def check_window():
    try:
        handle = gui.FindWindow(None, GAME_WINDOW_TITLE)
        if not handle:
            return 0

        client_rect = gui.GetClientRect(handle)
        if client_rect[2] == GAME_RESOLUTION[0] and client_rect[3] == GAME_RESOLUTION[1]:
            return handle

        left, top, right, bottom = gui.GetClientRect(handle)
        if right == 0 and bottom == 0:
            gui.ShowWindow(handle, win32con.SW_SHOWNORMAL)
        x0, y0, x1, y1 = gui.GetWindowRect(handle)
        gui.MoveWindow(handle, x0, y0,
                      GAME_RESOLUTION[0] + WINDOW_BORDER_OFFSET[0],
                      GAME_RESOLUTION[1] + WINDOW_BORDER_OFFSET[1], True)
        return handle

    except Exception:
        return 0


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


def run_bot(started, attack_delay, wait_after_enemy_spawn, gui_settings_opened, loot_opened, legendaries, status_queue=None, screenshot_enabled=None):
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

    def game_closed():
        started.value = False
        notify("error", "ERROR: The game window is closed. Bot stopping.")
        engine.say("Error")
        engine.say("Bot Stopped")
        engine.runAndWait()
        sys.exit(1)

    def check_legendary(frame, hsv_filter, current_img, save_screenshots, session_folder):
        """
        Checks if the loot window contains legendary items.
        Saves screenshot ONCE per loot window (if enabled).
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
                        calculated_x = x + LEGENDARY_OFFSET_X

                        # Check if item is in legendary position
                        if calculated_x in LEGENDARY_RANGE_1 or calculated_x in LEGENDARY_RANGE_2:
                            is_legendary = True
                            legendary_x = calculated_x
                            legendary_y = y + LEGENDARY_OFFSET_Y
                            legendary_coords = (x, y)
                            break  # Found legendary, stop searching

            # Save screenshot ONCE based on result (if enabled)
            if is_legendary:
                legendary_path = None
                if save_screenshots:
                    legendary_path = get_data_path(f'Data\\All Loot Screenshots\\{session_folder}\\Legendary Loot\\Legendary_{current_img}.jpg')
                    cv2.imwrite(legendary_path, frame)

                time_elapsed = datetime.now().replace(microsecond=0) - start_time.replace(microsecond=0)

                engine.say("Legendary Found")
                engine.runAndWait()

                # Double-click legendary item (intentional)
                press_left_click(legendary_x, legendary_y)
                press_left_click(legendary_x, legendary_y)

                legendaries.value += 1

                info_path = None
                if save_screenshots:
                    info_path = get_data_path(f'Data\\All Loot Screenshots\\{session_folder}\\Legendary Loot\\Legendary_Info_{current_img}.txt')
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
                if save_screenshots:
                    regular_path = get_data_path(f'Data\\All Loot Screenshots\\{session_folder}\\Regular Loot\\{current_img}.jpg')
                    cv2.imwrite(regular_path, frame)

            return current_img + 1

        except Exception as e:
            notify("error", f"Error in check_legendary: {e}")
            # Still increment counter even on error to avoid overwrites
            return current_img + 1

    # Initialize screenshot counter (always starts at 1 for each session)
    current_img = _initial_image_index()

    # Create session folder name with timestamp
    start_time = datetime.now()
    session_folder = start_time.strftime("Session_%d-%m-%Y_%H.%M.%S")
    notify("status", f"Bot loop started. Session: {session_folder}")

    handle = check_window()
    if not handle:
        game_closed()
        return

    wincap = WindowCapture()

    try:
        vision_open_loot = Vision(img_dir + '\\open_loot.jpg')
        vision_loot_window = Vision(img_dir + '\\loot_window.jpg')
        vision_enemy_hp_full = Vision(img_dir + '\\full_hp.jpg')
        vision_enemy_hp_damaged = Vision(img_dir + '\\damaged_hp.jpg')
        vision_enemy_hp_empty = Vision(img_dir + '\\empty_hp.jpg')
        vision_loot = Vision(None)
    except Exception as e:
        notify("error", f"Failed to load template images: {e}")
        started.value = False
        return

    # Create HSV filter from constants
    hsv_filter_red = HsvFilter(**HSV_LEGENDARY_RED)

    while True:
        sleep(LOOP_DELAY)

        if check_window() != 0:
            try:
                open_loot_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_open_loot')
                rectangles_open_loot = vision_open_loot.find(open_loot_frame, THRESHOLD_OPEN_LOOT)

                if rectangles_open_loot.any():
                    notify("status", "Open loot prompt detected, pressing shift.")
                    sleep(LOOT_OPEN_PRE_DELAY)
                    press_shift()
                    sleep(LOOT_OPEN_POST_DELAY)

                loot_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_loot_window')
                rectangles_loot_window = vision_loot_window.find(loot_frame, THRESHOLD_LOOT_WINDOW)

                if rectangles_loot_window.any():
                    loot_opened.value += 1
                    # Read screenshot enabled state from shared memory (allows real-time toggle)
                    save_screenshots = bool(screenshot_enabled.value) if screenshot_enabled is not None else True
                    current_img = check_legendary(loot_frame, hsv_filter_red, current_img, save_screenshots, session_folder)
                    notify(
                        "loot",
                        "Loot window processed.",
                        loot_count=int(loot_opened.value),
                        legendary_count=int(legendaries.value),
                    )
                    press_left_click(*TAKE_SMALL_ITEMS_BUTTON)
                    sleep(TAKE_ITEMS_DELAY)

                    loot_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_loot_window')
                    rectangles_loot_window = vision_loot_window.find(loot_frame, THRESHOLD_LOOT_WINDOW)

                    if rectangles_loot_window.any():
                        press_left_click(*TRASH_BUTTON)
                        sleep(TAKE_ITEMS_DELAY)

                enemy_hp_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_enemy_hp')
                rectangles_enemy_hp_full = vision_enemy_hp_full.find(enemy_hp_frame, THRESHOLD_HP_FULL)
                rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, THRESHOLD_HP_DAMAGED)
                rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, THRESHOLD_HP_EMPTY)

                if rectangles_enemy_hp_full.any() or rectangles_enemy_hp_damaged.any() or rectangles_enemy_hp_empty.any():

                    if not rectangles_enemy_hp_damaged.any() and not rectangles_enemy_hp_empty.any():
                        sleep(wait_after_enemy_spawn.value)
                        press_ctrl()
                        press_ctrl()
                        press_ctrl()
                        sleep(INITIAL_ATTACK_DELAY)

                    enemy_hp_frame = wincap.get_screenshot(GAME_WINDOW_TITLE, 'crop_enemy_hp')
                    rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, THRESHOLD_HP_DAMAGED)
                    rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, THRESHOLD_HP_EMPTY)

                    if rectangles_enemy_hp_damaged.any():
                        press_ctrl()
                        press_ctrl()
                        sleep(attack_delay.value)

            except Exception as e:
                notify("error", f"Bot loop error: {e}")
                continue

        else:
            game_closed()

        if cv2.waitKey(1) == ord('q'):
            cv2.destroyAllWindows()
            break
