import ctypes
import cv2 as cv2
import multiprocessing
import numpy as np
import os
import pyttsx3
import sys
import win32api as api
import win32con
import win32gui as gui
from colorama import Fore, Back, init
from datetime import datetime
from multiprocessing import Process
from time import sleep
from win32api import GetAsyncKeyState as KeyState
from win32con import WM_KEYDOWN, WM_KEYUP, VK_CONTROL, WM_LBUTTONDOWN, WM_LBUTTONUP, MK_LBUTTON, VK_INSERT, VK_DELETE, \
    VK_SHIFT, VK_HOME

from hsvfilter import HsvFilter
from vision import Vision
from windowcapture import WindowCapture

init(autoreset=True)
engine = pyttsx3.init()
engine.setProperty('rate', 150)
engine.setProperty('volume', 1.0)
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[1].id)


# !!!!!!!!!!!!!!!!!!!!!!!!!
# 46 114
# 222 303
# 0:53:22

# Intervale posibile:
# X 250 - 280 si 404 - 437
# Y 250 si 368

# Cazuri Ideale:

# (0,0) 266 260  |  (0,1) 422 260
# (1,0) 266 310  |  (1,1) 422 310
# (2,0) 266 360  |  (2,1) 422 360


# sys.tracebacklimit = 0


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


img_dir = resource_path("img")
current_img = 0

try:

    if not os.path.exists('Data\\All Loot Screenshots\\Legendary Loot'):
        os.makedirs('Data\\All Loot Screenshots\\Legendary Loot')

    if not os.path.exists('Data\\All Loot Screenshots\\Regular Loot'):
        os.makedirs('Data\\All Loot Screenshots\\Regular Loot')

except OSError:
    print('Error: Creating directory Data')

if len(os.listdir('Data\\All Loot Screenshots\\Regular Loot')) == 0:
    current_img = 1
else:
    current_img = len(os.listdir('Data\\All Loot Screenshots\\Regular Loot')) + 1

def GUI(loot_opened, legendaries):
    os.system('cls')
    print(Fore.GREEN + '************************************************** ')
    print(Fore.GREEN + '* ' + Fore.MAGENTA + 'The Legend of Pirates Online - BOT by Andy8991 ' + Fore.GREEN + '*')
    print(Fore.GREEN + '************************************************** \n')

    print(
        ' ' + Fore.GREEN + '1' + Fore.RESET + '.Hold ' + Fore.RED + 'INSERT' + Fore.RESET + ' to ' + Fore.BLUE + 'START        ' + Fore.YELLOW + 'Loot opened: ' + Fore.RESET + str(
            loot_opened.value))
    print(
        ' ' + Fore.GREEN + '2' + Fore.RESET + '.Hold ' + Fore.RED + 'DELETE' + Fore.RESET + ' to ' + Fore.BLUE + 'STOP         ' + Fore.LIGHTRED_EX + 'Legendaries: ' + Fore.RESET + str(
            legendaries.value))

    print('\n')

    print(
        ' ' + Fore.GREEN + '3' + Fore.RESET + '.Hold ' + Fore.RED + 'HOME' + Fore.RESET + ' for ' + Fore.BLUE + 'OPTIONS \n')

    print(Fore.GREEN + '------------------------------------------------- \n')


def GUI_settings():
    os.system('cls')
    print(Fore.GREEN + '************************************************** ')
    print(Fore.GREEN + '* ' + Fore.MAGENTA + 'The Legend of Pirates Online - BOT by Andy8991 ' + Fore.GREEN + '*')
    print(Fore.GREEN + '************************************************** \n')

    print(
        Fore.YELLOW + "----------------> " + Fore.BLUE + ' BOT OPTIONS ' + Fore.RESET + Fore.YELLOW + " <----------------\n")

    print(' ' + Fore.GREEN + '1' + Fore.RESET + '.Edit attack wait time after enemy spawn')
    print(' ' + Fore.GREEN + '2' + Fore.RESET + '.Edit time between attacks')
    print(' ' + Fore.GREEN + '3' + Fore.RESET + '.Reset attack to default values')
    print(' ' + Fore.GREEN + '4' + Fore.RESET + '.Reset statistics')
    print(' ' + Fore.GREEN + '5' + Fore.RESET + '.Back\n')

    print(Fore.GREEN + '------------------------------------------------- \n')

    try:
        Var = int(input('Choose an option(1, 2, 3, 4 or 5): '))

        if Var == 1:
            GUI(loot_opened, legendaries)
            wait_after_enemy_spawn.value = float(
                input('Enter Edit attack wait time after enemy spawn(Current value: ' + str(
                    wait_after_enemy_spawn.value) + ' sec): '))
            gui_settings_opened.value = False
            GUI(loot_opened, legendaries)
            print_bot_status(started)

        elif Var == 2:
            GUI(loot_opened, legendaries)
            attack_delay.value = float(
                input('Enter time between attacks(Current value: ' + str(attack_delay.value) + ' sec): '))
            gui_settings_opened.value = False
            GUI(loot_opened, legendaries)
            print_bot_status(started)

        elif Var == 3:
            GUI(loot_opened, legendaries)
            attack_delay.value = 0
            wait_after_enemy_spawn.value = 5
            gui_settings_opened.value = False
            GUI(loot_opened, legendaries)
            print_bot_status(started)

        elif Var == 4:
            GUI(loot_opened, legendaries)
            loot_opened.value = 0
            legendaries.value = 0
            gui_settings_opened.value = False
            GUI(loot_opened, legendaries)
            print_bot_status(started)

        elif Var == 5:
            gui_settings_opened.value = False
            GUI(loot_opened, legendaries)
            print_bot_status(started)

        else:
            GUI_settings()

    except ValueError:
        GUI_settings()


def print_bot_status(started):
    if started.value:
        print(
            Fore.YELLOW + "---------------> " + Back.GREEN + Fore.BLACK + "BOT STARTED !!!" + Back.RESET + Fore.RESET + Fore.YELLOW + " <---------------")
    else:
        print(
            Fore.YELLOW + "---------------> " + Back.RED + Fore.BLACK + "BOT STOPPED !!!" + Back.RESET + Fore.RESET + Fore.YELLOW + " <---------------")


def check_window():
    try:
        WHandle = gui.FindWindow(None, "The Legend of Pirates Online [BETA]")
        if gui.GetClientRect(WHandle)[2] == 1280 and gui.GetClientRect(WHandle)[3] == 800:
            return WHandle

        else:
            left, top, right, bottom = gui.GetClientRect(WHandle)
            if right == 0 and bottom == 0:
                gui.ShowWindow(WHandle, win32con.SW_SHOWNORMAL)
            x0, y0, x1, y1 = gui.GetWindowRect(WHandle)
            gui.MoveWindow(WHandle, x0, y0, 1280 + 16, 800 + 39, True)
            return WHandle

    except:
        return 0


def pressLCLick(x, y):
    lParam = api.MAKELONG(x, y)

    api.PostMessage(check_window(), WM_LBUTTONDOWN, MK_LBUTTON, lParam)
    api.PostMessage(check_window(), WM_LBUTTONUP, MK_LBUTTON, lParam)


def pressCTRL():
    api.PostMessage(check_window(), WM_KEYDOWN, VK_CONTROL, 0)
    sleep(0.3)
    api.PostMessage(check_window(), WM_KEYUP, VK_CONTROL, 0)


def pressSHIFT():
    api.PostMessage(check_window(), WM_KEYDOWN, VK_SHIFT, 0)
    sleep(0.8)
    api.PostMessage(check_window(), WM_KEYUP, VK_SHIFT, 0)


# def pressA():
#     api.PostMessage(check_window(), WM_KEYDOWN, 0x41, 0)
#     sleep(0.1)
#     api.PostMessage(check_window(), WM_KEYUP, 0x41, 0)
#
#
# def pressW():
#     api.PostMessage(check_window(), WM_KEYDOWN, 0x57, 0)
#     sleep(0.2)
#     api.PostMessage(check_window(), WM_KEYUP, 0x57, 0)


def InsertPressed():
    if KeyState(VK_INSERT) != 0 and KeyState(VK_DELETE) == 0 and KeyState(VK_HOME) == 0:
        return 1
    return 0


def DeletePressed():
    if KeyState(VK_DELETE) != 0 and KeyState(VK_INSERT) == 0 and KeyState(VK_HOME) == 0:
        return 1
    return 0


def HomePressed():
    if KeyState(VK_HOME) != 0 and KeyState(VK_INSERT) == 0 and KeyState(VK_DELETE) == 0:
        return 1
    return 0


def bot(started, attack_delay, wait_after_enemy_spawn, gui_settings_opened, loot_opened, legendaries):
    start_time = datetime.now()

    check_window()
    wincap = WindowCapture()

    # initialize the Vision class
    vision_open_loot = Vision(img_dir + '\\open_loot.jpg')
    vision_loot_window = Vision(img_dir + '\\loot_window.jpg')
    vision_enemy_hp_full = Vision(img_dir + '\\full_hp.jpg')
    vision_enemy_hp_damaged = Vision(img_dir + '\\damaged_hp.jpg')
    vision_enemy_hp_empty = Vision(img_dir + '\\empty_hp.jpg')
    vision_hit_combo = Vision(img_dir + '\\hit_combo.jpg')
    vision_loot = Vision(None)

    # initialize the trackbar window
    # vision_limestone.init_control_GUI(loot_opened, legendaries)

    hsv_filter_red = HsvFilter(0, 233, 3, 0, 255, 255, 25, 22, 0, 140)

    hsv_filter_green = HsvFilter(50, 160, 124, 67, 255, 255, 0, 0, 0, 0)

    # hsv_filter_combo = HsvFilter(0, 83, 53, 179, 114, 205, 0, 0, 0, 0)

    def game_closed():
        started.value = False
        GUI(loot_opened, legendaries)
        print_bot_status(started)
        print(Fore.RED + '\nERROR: The game is closed! Open the game!\n\n' +
              Fore.BLUE + 'Press INSERT to restart the bot!')
        engine.say("Error")
        engine.say("Bot Stopped")
        engine.runAndWait()
        sys.exit(1)

    def check_legendary(frame, hsv_filter):

        global current_img
        regularFrame = frame

        try:

            if not os.path.exists('Data\\All Loot Screenshots\\Legendary Loot'):
                os.makedirs('Data\\All Loot Screenshots\\Legendary Loot')

            if not os.path.exists('Data\\All Loot Screenshots\\Regular Loot'):
                os.makedirs('Data\\All Loot Screenshots\\Regular Loot')

        except OSError:
            print('Error: Creating directory Data')

        mask = vision_loot.apply_hsv_filter(frame, hsv_filter)
        kernal = np.ones((8, 8), "uint8")

        mask = cv2.dilate(mask, kernal)
        # res_red = cv2.bitwise_and(frame, frame,
        #                           mask=mask)
        contours, hierarchy = cv2.findContours(mask,
                                               cv2.RETR_TREE,
                                               cv2.CHAIN_APPROX_SIMPLE)
        if contours != ():
            for _, contour in enumerate(contours):
                area = cv2.contourArea(contour)
                if area > 800:
                    x, y, w, h = cv2.boundingRect(contour)
                    # rectangleFrame = cv2.rectangle(frame, (x, y),(x + w, y + h),(255, 0, 0), 2)

                    if x + 202 - 26 in range(250, 280) or x + 202 - 26 in range(404, 437):
                        name_legendary = '.\\Data\\All Loot Screenshots\\Legendary Loot\\Legendary_' + str(
                            current_img) + '.jpg'
                        cv2.imwrite(name_legendary, regularFrame)
                        time_elapsed = datetime.now().replace(microsecond=0) - start_time.replace(microsecond=0)

                        engine.say("Legendary Found")
                        engine.runAndWait()

                        pressLCLick(x + 202 - 26, y + 181 + 8)
                        pressLCLick(x + 202 - 26, y + 181 + 8)

                        legendaries.value += 1
                        if not gui_settings_opened.value:
                            GUI(loot_opened, legendaries)
                            print_bot_status(started)

                        with open('.\\Data\\All Loot Screenshots\\Legendary Loot\\Legendary_Info_' + str(
                                current_img) + '.txt',
                                  'a') as f:
                            f.write('################################################\n' +
                                    'Legendary_' + str(current_img) + '\n' +
                                    f'originals coordinates: {x, y}\n'
                                    f'Calculated coordinates: {x + 202 - 26, y + 181 + 8}\n'
                                    f'Time elapsed to find the legendary: {time_elapsed}\n' +
                                    '################################################\n\n'
                                    )
                    else:
                        name_legendary = '.\\Data\\All Loot Screenshots\\Regular Loot\\' + str(current_img) + '.jpg'
                        cv2.imwrite(name_legendary, regularFrame)
                else:
                    name_legendary = '.\\Data\\All Loot Screenshots\\Regular Loot\\' + str(current_img) + '.jpg'
                    cv2.imwrite(name_legendary, regularFrame)


        else:
            name_legendary = '.\\Data\\All Loot Screenshots\\Regular Loot\\' + str(current_img) + '.jpg'
            cv2.imwrite(name_legendary, regularFrame)

        current_img += 1

    activated = True
    start_time_kill = None
    while True:
        sleep(0.3)

        if check_window() != 0:

            # enemy_hp_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_enemy_hp')
            # hit_combo_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_hit_combo')
            # test_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]')

            # do object detection

            # rectangles_hit_combo = vision_hit_combo.find(hit_combo_frame, 0.45)

            # draw the detection results onto the original image
            # output_image_loot_window = vision_loot_window.draw_rectangles(loot_frame, rectangles_loot_window)
            # output_image_enemy_full = vision_enemy_hp_full.draw_rectangles(enemy_hp_frame, rectangles_enemy_hp_full)
            # output_image_enemy_hp_damaged = vision_enemy_hp_damaged.draw_rectangles(enemy_hp_frame, rectangles_enemy_hp_damaged)
            # output_image_enemy_hp_empty = vision_enemy_hp_empty.draw_rectangles(enemy_hp_frame, rectangles_enemy_hp_empty)
            # output_image_open_loot = vision_open_loot.draw_rectangles(open_loot_frame, rectangles_open_loot)
            # output_hit_combo = vision_hit_combo.draw_rectangles(hit_combo_frame, rectangles_hit_combo)

            # cv2.imshow('test', test_frame)
            # cv2.imshow('Loot Window', loot_frame)
            # cv2.imshow('Enemy HP', output_image_enemy_hp_empty)
            # cv2.imshow('Open Loot Text', open_loot_frame)
            # cv2.imshow('Hit Combo', output_hit_combo)

            if activated:

                open_loot_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_open_loot')
                rectangles_open_loot = vision_open_loot.find(open_loot_frame, 0.40)

                if rectangles_open_loot.any():
                    # open_loot_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_open_loot')
                    # rectangles_open_loot = vision_open_loot.find(open_loot_frame, 0.40)
                    # output_image_open_loot = vision_open_loot.draw_rectangles(open_loot_frame, rectangles_open_loot)
                    # cv2.imshow('isLoot', output_image_open_loot)
                    sleep(2)
                    pressSHIFT()
                    sleep(3)

                loot_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_loot_window')
                rectangles_loot_window = vision_loot_window.find(loot_frame, 0.40)

                if rectangles_loot_window.any():
                    # loot_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_loot_window')
                    # rectangles_loot_window = vision_loot_window.find(loot_frame, 0.45)
                    # output_image_loot_window = vision_loot_window.draw_rectangles(loot_frame, rectangles_loot_window)
                    # cv2.imshow('Loot Window', output_image_loot_window)
                    loot_opened.value += 1
                    if not gui_settings_opened.value:
                        GUI(loot_opened, legendaries)
                        print_bot_status(started)
                    check_legendary(loot_frame, hsv_filter_red)
                    pressLCLick(532, 399)  # take small items
                    sleep(2)

                    loot_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_loot_window')
                    rectangles_loot_window = vision_loot_window.find(loot_frame, 0.40)

                    if rectangles_loot_window.any():
                        pressLCLick(221, 205)  # trash
                        sleep(2)


                enemy_hp_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_enemy_hp')
                rectangles_enemy_hp_full = vision_enemy_hp_full.find(enemy_hp_frame, 0.85)
                rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, 0.95)
                rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, 0.90)

                if rectangles_enemy_hp_full.any() or rectangles_enemy_hp_damaged.any() or rectangles_enemy_hp_empty.any():
                    # output_image_enemy_hp_full = vision_enemy_hp_full.draw_rectangles(enemy_hp_frame, rectangles_enemy_hp_full)
                    # output_image_enemy_hp_damaged = vision_enemy_hp_damaged.draw_rectangles(enemy_hp_frame, rectangles_enemy_hp_damaged)
                    # cv2.imshow('Enemy HP', enemy_hp_frame)

                    if not rectangles_enemy_hp_damaged.any() and not rectangles_enemy_hp_empty.any():
                        start_time_kill = datetime.now()
                        sleep(wait_after_enemy_spawn.value)
                        pressCTRL()
                        pressCTRL()
                        pressCTRL()
                        sleep(0.5)

                    enemy_hp_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_enemy_hp')
                    rectangles_enemy_hp_damaged = vision_enemy_hp_damaged.find(enemy_hp_frame, 0.95)
                    rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, 0.90)

                    if rectangles_enemy_hp_damaged.any():
                        pressCTRL()
                        pressCTRL()
                        # hit_combo_frame = wincap.get_screenshot('The Legend of Pirates Online [BETA]', 'crop_hit_combo')
                        # rectangles_hit_combo = vision_hit_combo.find(hit_combo_frame, 0.45)
                        # rectangles_enemy_hp_empty = vision_enemy_hp_empty.find(enemy_hp_frame, 0.90)
                        # output_hit_combo = vision_hit_combo.draw_rectangles(hit_combo_frame, rectangles_hit_combo)
                        # cv2.imshow('Hit Combo', output_hit_combo)
                        sleep(attack_delay.value)


        else:
            game_closed()

        if cv2.waitKey(1) == ord('q'):
            cv2.destroyAllWindows()
            break


if __name__ == '__main__':

    multiprocessing.freeze_support()
    started = multiprocessing.Value("i", False)
    gui_settings_opened = multiprocessing.Value("i", False)
    attack_delay = multiprocessing.Value("d", 0)
    wait_after_enemy_spawn = multiprocessing.Value("d", 5.5)
    loot_opened = multiprocessing.Value("i", 0)
    legendaries = multiprocessing.Value("i", 0)

    cmd = 'mode 51,18'
    os.system(cmd)

    GUI(loot_opened, legendaries)
    print_bot_status(started)

    while True:
        if InsertPressed() and not started.value and not gui_settings_opened.value:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000002)
            p = Process(target=bot, args=(
                started, attack_delay, wait_after_enemy_spawn, gui_settings_opened, loot_opened, legendaries))
            p.start()
            started.value = True
            GUI(loot_opened, legendaries)
            print_bot_status(started)
            engine.say("Bot Started")
            engine.runAndWait()

        elif DeletePressed() and started.value and not gui_settings_opened.value:
            p.terminate()
            p.join()
            started.value = False
            GUI(loot_opened, legendaries)
            print_bot_status(started)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            engine.say("Bot Stopped")
            engine.runAndWait()
        elif HomePressed():
            gui_settings_opened.value = True
            GUI_settings()
        # time_elapsed = datetime.now().replace(microsecond=0) - start_time.replace(microsecond=0)
        # term = Terminal()
        # with term.location(34, 3):
        #     print(time_elapsed)

        sleep(1)
