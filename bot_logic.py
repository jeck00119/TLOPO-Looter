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


engine = pyttsx3.init()
engine.setProperty('rate', 150)
engine.setProperty('volume', 1.0)
voices = engine.getProperty('voices')
if voices:
    engine.setProperty('voice', voices[min(1, len(voices) - 1)].id)


def resource_path(relative_path):
    """Return absolute path to resource, compatible with PyInstaller bundles."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def ensure_data_directories():
    targets = [
        'Data\\All Loot Screenshots\\Legendary Loot',
        'Data\\All Loot Screenshots\\Regular Loot',
    ]
    for target in targets:
        os.makedirs(target, exist_ok=True)


def _initial_image_index():
    regular_loot_dir = 'Data\\All Loot Screenshots\\Regular Loot'
    files = []
    try:
        files = os.listdir(regular_loot_dir)
    except FileNotFoundError:
        return 1

    if not files:
        return 1
    return len(files) + 1


ensure_data_directories()
img_dir = resource_path("img")
current_img = _initial_image_index()


def check_window():
    try:
        handle = gui.FindWindow(None, "The Legend of Pirates Online [BETA]")
        if not handle:
            return 0

        client_rect = gui.GetClientRect(handle)
        if client_rect[2] == 1280 and client_rect[3] == 800:
            return handle

        left, top, right, bottom = gui.GetClientRect(handle)
        if right == 0 and bottom == 0:
            gui.ShowWindow(handle, win32con.SW_SHOWNORMAL)
        x0, y0, x1, y1 = gui.GetWindowRect(handle)
        gui.MoveWindow(handle, x0, y0, 1280 + 16, 800 + 39, True)
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
    sleep(0.3)
    api.PostMessage(handle, WM_KEYUP, VK_CONTROL, 0)


def press_shift():
    handle = check_window()
    if not handle:
        return
    api.PostMessage(handle, WM_KEYDOWN, VK_SHIFT, 0)
    sleep(0.8)
    api.PostMessage(handle, WM_KEYUP, VK_SHIFT, 0)


def run_bot(started, attack_delay, wait_after_enemy_spawn, gui_settings_opened, loot_opened, legendaries, status_queue=None):
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

    def check_legendary(frame, hsv_filter):
        global current_img
        regular_frame = frame

        ensure_data_directories()

        mask = vision_loot.apply_hsv_filter(frame, hsv_filter)
        kernel = np.ones((8, 8), "uint8")

        mask = cv2.dilate(mask, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 800:
                    x, y, w, h = cv2.boundingRect(contour)

                    if x + 202 - 26 in range(250, 280) or x + 202 - 26 in range(404, 437):
                        legendary_path = '.\\Data\\All Loot Screenshots\\Legendary Loot\\Legendary_' + str(current_img) + '.jpg'
                        cv2.imwrite(legendary_path, regular_frame)
                        time_elapsed = datetime.now().replace(microsecond=0) - start_time.replace(microsecond=0)

                        engine.say("Legendary Found")
                        engine.runAndWait()

                        press_left_click(x + 202 - 26, y + 181 + 8)
                        press_left_click(x + 202 - 26, y + 181 + 8)

                        legendaries.value += 1
                        info_path = '.\\Data\\All Loot Screenshots\\Legendary Loot\\Legendary_Info_' + str(current_img) + '.txt'
                        notify(
                            "legendary",
                            "Legendary loot detected.",
                            loot_count=int(loot_opened.value),
                            legendary_count=int(legendaries.value),
                            screenshot=legendary_path,
                            info_file=info_path,
                        )

                        with open(info_path, 'a') as f_handle:
                            f_handle.write('################################################\n' +
                                           'Legendary_' + str(current_img) + '\n' +
                                           f'originals coordinates: {x, y}\n'
                                           f'Calculated coordinates: {x + 202 - 26, y + 181 + 8}\n'
                                           f'Time elapsed to find the legendary: {time_elapsed}\n' +
                                           '################################################\n\n'
                                           )
                    else:
                        regular_path = '.\\Data\\All Loot Screenshots\\Regular Loot\\' + str(current_img) + '.jpg'
                        cv2.imwrite(regular_path, regular_frame)
                else:
                    regular_path = '.\\Data\\All Loot Screenshots\\Regular Loot\\' + str(current_img) + '.jpg'
                    cv2.imwrite(regular_path, regular_frame)

        else:
            regular_path = '.\\Data\\All Loot Screenshots\\Regular Loot\\' + str(current_img) + '.jpg'
            cv2.imwrite(regular_path, regular_frame)

        current_img += 1

    start_time = datetime.now()
    notify("status", "Bot loop started.")

    handle = check_window()
    if not handle:
        game_closed()
        return

    wincap = WindowCapture()

    vision_open_loot = Vision(img_dir + '\\open_loot.jpg')
    vision_loot_window = Vision(img_dir + '\\loot_window.jpg')
    vision_enemy_hp_full = Vision(img_dir + '\\full_hp.jpg')
    vision_enemy_hp_damaged = Vision(img_dir + '\\damaged_hp.jpg')
    vision_enemy_hp_empty = Vision(img_dir + '\\empty_hp.jpg')
    vision_hit_combo = Vision(img_dir + '\\hit_combo.jpg')
    vision_loot = Vision(None)

    hsv_filter_red = HsvFilter(0, 233, 3, 0, 255, 255, 25, 22, 0, 140)
    hsv_filter_green = HsvFilter(50, 160, 124, 67, 255, 255, 0, 0, 0, 0)

    activated = True
    start_time_kill = None
    while True:
        sleep(0.3)

        if check_window() != 0:
            if activated:

                open_loot_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_open_loot')
                rectangles_open_loot = vision_open_loot.find(open_loot_frame, 0.40)

                if rectangles_open_loot.any():
                    notify("status", "Open loot prompt detected, pressing shift.")
                    sleep(2)
                    press_shift()
                    sleep(3)

                loot_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_loot_window')
                rectangles_loot_window = vision_loot_window.find(loot_frame, 0.40)

                if rectangles_loot_window.any():
                    loot_opened.value += 1
                    check_legendary(loot_frame, hsv_filter_red)
                    notify(
                        "loot",
                        "Loot window processed.",
                        loot_count=int(loot_opened.value),
                        legendary_count=int(legendaries.value),
                    )
                    press_left_click(532, 399)
                    sleep(2)

                    loot_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_loot_window')
                    rectangles_loot_window = vision_loot_window.find(loot_frame, 0.40)

                    if rectangles_loot_window.any():
                        press_left_click(221, 205)
                        sleep(2)

                enemy_hp_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_enemy_hp')
                rectangles_enemy_hp_full = vision_enemy_hp_full.find(enemy_hp_frame, 0.85)
                rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, 0.95)
                rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, 0.90)

                if rectangles_enemy_hp_full.any() or rectangles_enemy_hp_damaged.any() or rectangles_enemy_hp_empty.any():

                    if not rectangles_enemy_hp_damaged.any() and not rectangles_enemy_hp_empty.any():
                        start_time_kill = datetime.now()
                        sleep(wait_after_enemy_spawn.value)
                        press_ctrl()
                        press_ctrl()
                        press_ctrl()
                        sleep(0.5)

                    enemy_hp_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_enemy_hp')
                    rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, 0.95)
                    rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, 0.90)

                    if rectangles_enemy_hp_damaged.any():
                        press_ctrl()
                        press_ctrl()
                        sleep(attack_delay.value)

        else:
            game_closed()

        if cv2.waitKey(1) == ord('q'):
            cv2.destroyAllWindows()
            break
