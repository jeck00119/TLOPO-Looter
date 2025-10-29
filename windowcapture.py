import numpy as np
import win32con
import win32gui
import win32ui


class WindowCapture:
    # properties
    w = 0
    h = 0
    hwnd = None
    cropped_x = 0
    cropped_y = 0
    offset_x = 0
    offset_y = 0

    def get_screenshot(self, window_name=None, crop=None):

        # find the handle for the window we want to capture.
        # if no window name is given, capture the entire screen
        if window_name is None:
            self.hwnd = win32gui.GetDesktopWindow()
        else:
            self.hwnd = win32gui.FindWindow(None, window_name)
            if not self.hwnd:
                raise Exception('Window not found: {}'.format(window_name))

        # get the window size
        window_rect = win32gui.GetWindowRect(self.hwnd)

        if crop == "crop_boss_name":
            # x, y, w, h: (571, 93, 225, 18)

            self.w = 200
            self.h = 25

            self.cropped_x = 570
            self.cropped_y = 70

        elif crop == "crop_enemy_hp":
            # x, y, w, h: (571, 93, 225, 18)

            self.w = 225
            self.h = 18

            self.cropped_x = 571
            self.cropped_y = 93

        elif crop == "crop_hit_combo":
            self.w = 200
            self.h = 50

            self.cropped_x = 200
            self.cropped_y = 195

        elif crop == "crop_loot_window":
            # x, y, w, h: (207, 209, 397, 262)

            self.w = 397
            self.h = 262

            self.cropped_x = 207
            self.cropped_y = 209

        elif crop == "crop_open_loot":
            self.w = 155
            self.h = 34

            self.cropped_x = 570
            self.cropped_y = 684

        elif crop == 'crop_test':
            self.w = 148
            self.h = 26

            self.cropped_x = 925
            self.cropped_y = 68

        else:
            self.w = window_rect[2] - window_rect[0]
            self.h = window_rect[3] - window_rect[1]

            self.cropped_x = 0
            self.cropped_y = 0

        # get the window image data
        wDC = win32gui.GetWindowDC(self.hwnd)
        dcObj = win32ui.CreateDCFromHandle(wDC)
        cDC = dcObj.CreateCompatibleDC()
        dataBitMap = win32ui.CreateBitmap()
        dataBitMap.CreateCompatibleBitmap(dcObj, self.w, self.h)
        cDC.SelectObject(dataBitMap)
        cDC.BitBlt((0, 0), (self.w, self.h), dcObj, (self.cropped_x, self.cropped_y), win32con.SRCCOPY)

        # convert the raw data into a format opencv can read
        # dataBitMap.SaveBitmapFile(cDC, 'debug.bmp')
        signedIntsArray = dataBitMap.GetBitmapBits(True)
        img = np.fromstring(signedIntsArray, dtype='uint8')
        img.shape = (self.h, self.w, 4)

        # free resources
        dcObj.DeleteDC()
        cDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, wDC)
        win32gui.DeleteObject(dataBitMap.GetHandle())

        # drop the alpha channel, or cv.matchTemplate() will throw an error like:
        #   error: (-215:Assertion failed) (depth == CV_8U || depth == CV_32F) && type == _templ.type() 
        #   && _img.dims() <= 2 in function 'cv::matchTemplate'
        img = img[..., :3]

        # make image C_CONTIGUOUS to avoid errors that look like:
        #   File ... in draw_rectangles
        #   TypeError: an integer is required (got type tuple)
        # see the discussion here:
        # https://github.com/opencv/opencv/issues/14866#issuecomment-580207109
        img = np.ascontiguousarray(img)

        return img

    # find the name of the window you're interested in.
    # once you have it, update window_capture()
    # https://stackoverflow.com/questions/55547940/how-to-get-a-list-of-the-name-of-every-open-window
    @staticmethod
    def list_window_names():
        def winEnumHandler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                print(hex(hwnd), win32gui.GetWindowText(hwnd))

        win32gui.EnumWindows(winEnumHandler, None)

    # translate a pixel position on a screenshot image to a pixel position on the screen.
    # pos = (x, y)
    # WARNING: if you move the window being captured after execution is started, this will
    # return incorrect coordinates, because the window position is only calculated in
    # the __init__ constructor.
    def get_screen_position(self, pos):
        return (pos[0] + self.offset_x, pos[1] + self.offset_y)
