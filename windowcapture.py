import numpy as np
import win32con
import win32gui
import win32ui


class WindowCapture:
    # Crop region definitions (x, y, width, height)
    # IMPORTANT: Coordinates are for 1280x800 game window only
    # (0,0) = top-left corner of game client area (inside window borders)
    CROP_REGIONS = {
        "crop_boss_name": {"x": 570, "y": 70, "w": 200, "h": 25},
        "crop_enemy_hp": {"x": 571, "y": 93, "w": 225, "h": 18},
        "crop_hit_combo": {"x": 200, "y": 195, "w": 200, "h": 50},
        "crop_loot_window": {"x": 207, "y": 209, "w": 397, "h": 262},
        "crop_open_loot": {"x": 570, "y": 684, "w": 155, "h": 34},
        "crop_test": {"x": 925, "y": 68, "w": 148, "h": 26},
    }

    # properties
    w = 0
    h = 0
    hwnd = None
    cropped_x = 0
    cropped_y = 0
    offset_x = 0
    offset_y = 0

    def __enter__(self):
        """Context manager entry - allows 'with' statement usage"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup resources if needed"""
        # Resources are cleaned up in get_screenshot, but this ensures proper context manager support
        return False  # Don't suppress exceptions

    def get_screenshot(self, window_name=None, crop=None):
        """
        Captures window screenshot using Win32 API (works even when game is minimized/background).
        Uses BitBlt to copy pixel data from window DC to bitmap, then converts to OpenCV format.
        Returns: numpy array (BGR format, no alpha channel)
        """
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

        # Use dictionary lookup for crop regions
        if crop and crop in self.CROP_REGIONS:
            region = self.CROP_REGIONS[crop]
            self.w = region["w"]
            self.h = region["h"]
            self.cropped_x = region["x"]
            self.cropped_y = region["y"]
        else:
            # Full window capture
            self.w = window_rect[2] - window_rect[0]
            self.h = window_rect[3] - window_rect[1]
            self.cropped_x = 0
            self.cropped_y = 0

        # get the window image data
        wDC = None
        dcObj = None
        cDC = None
        dataBitMap = None

        try:
            wDC = win32gui.GetWindowDC(self.hwnd)
            dcObj = win32ui.CreateDCFromHandle(wDC)
            cDC = dcObj.CreateCompatibleDC()
            dataBitMap = win32ui.CreateBitmap()
            dataBitMap.CreateCompatibleBitmap(dcObj, self.w, self.h)
            cDC.SelectObject(dataBitMap)
            cDC.BitBlt((0, 0), (self.w, self.h), dcObj, (self.cropped_x, self.cropped_y), win32con.SRCCOPY)

            # convert the raw data into a format opencv can read
            signedIntsArray = dataBitMap.GetBitmapBits(True)
            img = np.frombuffer(signedIntsArray, dtype='uint8')
            img.shape = (self.h, self.w, 4)

            # drop the alpha channel, or cv.matchTemplate() will throw an error
            img = img[..., :3]

            # make image C_CONTIGUOUS to avoid errors
            img = np.ascontiguousarray(img)

            return img

        finally:
            # Always free resources, even if an exception occurs
            if dcObj is not None:
                dcObj.DeleteDC()
            if cDC is not None:
                cDC.DeleteDC()
            if wDC is not None and self.hwnd is not None:
                win32gui.ReleaseDC(self.hwnd, wDC)
            if dataBitMap is not None:
                win32gui.DeleteObject(dataBitMap.GetHandle())

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
