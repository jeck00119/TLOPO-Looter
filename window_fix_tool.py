#!/usr/bin/env python3
"""
Universal Window Fix Tool for TLOPO Looter
Diagnoses issues and tries all methods to fix window dimensions
"""

import ctypes
from ctypes import wintypes
import win32gui as gui
import win32api
import win32con
from time import sleep
import sys

GAME_WINDOW_TITLE = "The Legend of Pirates Online [BETA]"
TARGET_WIDTH = 1280
TARGET_HEIGHT = 800
TOLERANCE = 10


# ==============================================================================
# Helper Functions
# ==============================================================================

def print_box(text, char="="):
    """Print text in a box"""
    print("\n" + char * 70)
    print(text)
    print(char * 70 + "\n")


def get_client_size(hwnd):
    """Get current client area size"""
    try:
        rect = gui.GetClientRect(hwnd)
        return (rect[2], rect[3])
    except:
        return (0, 0)


def get_window_rect_tuple(hwnd):
    """Get current window rectangle"""
    try:
        return gui.GetWindowRect(hwnd)
    except:
        return (0, 0, 0, 0)


def show_current_state(hwnd, label="CURRENT STATE"):
    """Display current window state"""
    print(f"\n{label}:")
    print("-" * 70)

    try:
        # Client area
        client_w, client_h = get_client_size(hwnd)
        print(f"Client Area: {client_w}x{client_h}")

        # Window size
        x0, y0, x1, y1 = get_window_rect_tuple(hwnd)
        window_w = x1 - x0
        window_h = y1 - y0
        print(f"Window Size: {window_w}x{window_h}")
        print(f"Position: ({x0}, {y0})")

        # Calculate borders
        border_w = window_w - client_w
        border_h = window_h - client_h
        print(f"Borders: {border_w}x{border_h} (Width x Height)")

        # Check vs target
        diff_w = client_w - TARGET_WIDTH
        diff_h = client_h - TARGET_HEIGHT
        print(f"Difference from target ({TARGET_WIDTH}x{TARGET_HEIGHT}): {diff_w:+d}x{diff_h:+d} pixels")

        # Status
        if abs(diff_w) <= TOLERANCE and abs(diff_h) <= TOLERANCE:
            print(f"✅ WITHIN TOLERANCE (±{TOLERANCE}px)")
            return True
        else:
            print(f"❌ OUT OF TOLERANCE (>{TOLERANCE}px)")
            return False

    except Exception as e:
        print(f"Error: {e}")
        return False


def get_full_diagnostics(hwnd):
    """Show complete diagnostic information"""
    print_box("FULL SYSTEM & WINDOW DIAGNOSTICS")

    # System info
    print("SYSTEM:")
    desktop_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
    desktop_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
    print(f"  Desktop Resolution: {desktop_w}x{desktop_h}")

    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        hdc = user32.GetDC(0)
        dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        dpi_y = ctypes.windll.gdi32.GetDeviceCaps(hdc, 90)
        user32.ReleaseDC(0, hdc)
        scale = (dpi_x / 96.0) * 100
        print(f"  System DPI: {dpi_x} ({scale:.0f}% scaling)")
    except:
        dpi_x = 96
        scale = 100
        print(f"  System DPI: Unknown (assuming 96)")

    print()

    # Window info
    print("WINDOW:")
    print(f"  Title: {gui.GetWindowText(hwnd)}")
    print(f"  Handle: {hwnd}")

    # Get styles
    try:
        style = win32api.GetWindowLong(hwnd, win32con.GWL_STYLE)
        ex_style = win32api.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        print(f"  Style: 0x{style:08X}")

        # Check window state
        if style & win32con.WS_MAXIMIZE:
            print(f"  State: MAXIMIZED ⚠️")
        elif style & win32con.WS_MINIMIZE:
            print(f"  State: MINIMIZED ⚠️")
        else:
            print(f"  State: Normal")

        if style & win32con.WS_THICKFRAME:
            print(f"  Resizable: Yes")
        else:
            print(f"  Resizable: No ⚠️")

    except:
        style = 0
        ex_style = 0
        print(f"  Style: Unknown")

    # DPI awareness
    try:
        user32 = ctypes.windll.user32
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

        kernel32 = ctypes.windll.kernel32
        h_process = kernel32.OpenProcess(0x0400, False, process_id.value)

        if h_process:
            awareness = ctypes.c_int()
            shcore = ctypes.windll.shcore
            result = shcore.GetProcessDpiAwareness(h_process, ctypes.byref(awareness))

            if result == 0:
                awareness_names = {
                    0: "UNAWARE (Windows scales window)",
                    1: "SYSTEM_AWARE (DPI override = System)",
                    2: "PER_MONITOR_AWARE"
                }
                print(f"  DPI Awareness: {awareness_names.get(awareness.value, 'Unknown')}")
                if awareness.value == 0:
                    print(f"    ⚠️ Game is DPI-unaware - Windows will scale the window")

            kernel32.CloseHandle(h_process)
    except:
        print(f"  DPI Awareness: Unknown")

    print()
    show_current_state(hwnd, "CURRENT DIMENSIONS")

    return dpi_x, style, ex_style


# ==============================================================================
# Resize Methods
# ==============================================================================

def try_method_iterative(hwnd, label, max_iter=5):
    """Iterative resize with error correction"""
    print(f"\n{label}")
    print("Strategy: Measure error, adjust window by error amount, repeat")
    print("-" * 70)

    for i in range(max_iter):
        client_w, client_h = get_client_size(hwnd)
        error_w = TARGET_WIDTH - client_w
        error_h = TARGET_HEIGHT - client_h

        print(f"Iteration {i+1}: Client={client_w}x{client_h}, Error={error_w:+d}x{error_h:+d}")

        if abs(error_w) <= TOLERANCE and abs(error_h) <= TOLERANCE:
            print("✅ Within tolerance!")
            return show_current_state(hwnd, "RESULT")

        if error_w == 0 and error_h == 0:
            print("✅ Exact match!")
            return show_current_state(hwnd, "RESULT")

        # Adjust window
        x0, y0, x1, y1 = get_window_rect_tuple(hwnd)
        window_w = x1 - x0
        window_h = y1 - y0

        new_w = window_w + error_w
        new_h = window_h + error_h

        gui.MoveWindow(hwnd, x0, y0, new_w, new_h, True)
        sleep(0.15)

    print("❌ Max iterations reached")
    return show_current_state(hwnd, "RESULT")


def try_method_direct_borders(hwnd, label):
    """Calculate from current borders"""
    print(f"\n{label}")
    print("Strategy: Measure current borders, apply to target size")
    print("-" * 70)

    client_w, client_h = get_client_size(hwnd)
    x0, y0, x1, y1 = get_window_rect_tuple(hwnd)
    window_w = x1 - x0
    window_h = y1 - y0

    border_w = window_w - client_w
    border_h = window_h - client_h

    print(f"Current borders: {border_w}x{border_h}")

    new_window_w = TARGET_WIDTH + border_w
    new_window_h = TARGET_HEIGHT + border_h

    print(f"Setting window to: {new_window_w}x{new_window_h}")

    gui.MoveWindow(hwnd, x0, y0, new_window_w, new_window_h, True)
    sleep(0.15)

    return show_current_state(hwnd, "RESULT")


def try_method_adjust_window_rect(hwnd, label, style, ex_style):
    """Use AdjustWindowRectEx API"""
    print(f"\n{label}")
    print("Strategy: Use Windows API to calculate proper window size")
    print("-" * 70)

    rect = wintypes.RECT()
    rect.left = 0
    rect.top = 0
    rect.right = TARGET_WIDTH
    rect.bottom = TARGET_HEIGHT

    ctypes.windll.user32.AdjustWindowRectEx(
        ctypes.byref(rect),
        style,
        False,
        ex_style
    )

    window_w = rect.right - rect.left
    window_h = rect.bottom - rect.top

    print(f"API calculates window size: {window_w}x{window_h}")

    x0, y0, x1, y1 = get_window_rect_tuple(hwnd)
    gui.MoveWindow(hwnd, x0, y0, window_w, window_h, True)
    sleep(0.15)

    return show_current_state(hwnd, "RESULT")


def try_method_dpi_scaled(hwnd, label, dpi):
    """Try inverse DPI scaling for unaware apps"""
    print(f"\n{label}")
    print("Strategy: Account for DPI virtualization scaling")
    print("-" * 70)

    scale = dpi / 96.0
    print(f"Scale factor: {scale}x")

    # For DPI-unaware app at 150% scaling:
    # To get 1280x800 after Windows scales by 1.5x,
    # need to set to 1280/1.5 = 853x533

    inverse_w = int(TARGET_WIDTH / scale)
    inverse_h = int(TARGET_HEIGHT / scale)

    print(f"Setting to: {inverse_w}x{inverse_h} (expecting Windows to scale to {TARGET_WIDTH}x{TARGET_HEIGHT})")

    style = win32api.GetWindowLong(hwnd, win32con.GWL_STYLE)
    ex_style = win32api.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

    rect = wintypes.RECT()
    rect.left = 0
    rect.top = 0
    rect.right = inverse_w
    rect.bottom = inverse_h

    ctypes.windll.user32.AdjustWindowRectEx(
        ctypes.byref(rect),
        style,
        False,
        ex_style
    )

    window_w = rect.right - rect.left
    window_h = rect.bottom - rect.top

    print(f"Window size: {window_w}x{window_h}")

    x0, y0, x1, y1 = get_window_rect_tuple(hwnd)
    gui.MoveWindow(hwnd, x0, y0, window_w, window_h, True)
    sleep(0.15)

    return show_current_state(hwnd, "RESULT")


def try_method_hardcoded(hwnd, label):
    """Try common border sizes"""
    print(f"\n{label}")
    print("Strategy: Try common border size presets")
    print("-" * 70)

    configs = [
        (24, 59, "24x59"),
        (22, 56, "22x56"),
        (16, 39, "16x39"),
        (32, 72, "32x72"),
    ]

    x0, y0, x1, y1 = get_window_rect_tuple(hwnd)

    for border_w, border_h, desc in configs:
        window_w = TARGET_WIDTH + border_w
        window_h = TARGET_HEIGHT + border_h

        print(f"Trying borders {desc}: window={window_w}x{window_h}", end=" → ")
        gui.MoveWindow(hwnd, x0, y0, window_w, window_h, True)
        sleep(0.15)

        client_w, client_h = get_client_size(hwnd)
        diff_w = abs(client_w - TARGET_WIDTH)
        diff_h = abs(client_h - TARGET_HEIGHT)

        print(f"client={client_w}x{client_h}")

        if diff_w <= TOLERANCE and diff_h <= TOLERANCE:
            print(f"✅ Success with {desc}!")
            return show_current_state(hwnd, "RESULT")

    print("❌ No preset worked")
    return show_current_state(hwnd, "RESULT")


# ==============================================================================
# Main Program
# ==============================================================================

def main():
    print_box("TLOPO WINDOW FIX TOOL", "=")
    print("This tool will:")
    print("  1. Show full diagnostics")
    print("  2. Try multiple methods to fix window to 1280x800")
    print("  3. Report which method works")
    print()

    # Find window
    hwnd = gui.FindWindow(None, GAME_WINDOW_TITLE)

    if not hwnd:
        print(f"❌ ERROR: Game window not found!")
        print(f"   Looking for: '{GAME_WINDOW_TITLE}'")
        print()
        print("Make sure:")
        print("  - Game is running")
        print("  - Window title matches exactly")
        print()
        input("Press Enter to exit...")
        return

    print(f"✅ Found game window (handle: {hwnd})")
    print()

    # Get full diagnostics
    dpi, style, ex_style = get_full_diagnostics(hwnd)

    # Check if already good
    client_w, client_h = get_client_size(hwnd)
    diff_w = abs(client_w - TARGET_WIDTH)
    diff_h = abs(client_h - TARGET_HEIGHT)

    if diff_w <= TOLERANCE and diff_h <= TOLERANCE:
        print_box("✅ WINDOW IS ALREADY CORRECT!", "=")
        print(f"Current: {client_w}x{client_h}")
        print(f"Target: {TARGET_WIDTH}x{TARGET_HEIGHT}")
        print(f"Difference: {diff_w}x{diff_h} pixels (within ±{TOLERANCE}px tolerance)")
        print()
        input("Press Enter to exit...")
        return

    # Ask to proceed
    print()
    print(f"Window needs fixing: {client_w}x{client_h} → {TARGET_WIDTH}x{TARGET_HEIGHT}")
    response = input("\nProceed with resize attempts? (y/n): ")

    if response.lower() != 'y':
        print("Cancelled.")
        input("\nPress Enter to exit...")
        return

    print_box("TRYING RESIZE METHODS", "=")

    # Store initial state
    initial_w, initial_h = client_w, client_h

    # Try methods in order of likelihood
    methods = [
        ("METHOD 1: Iterative Resize (3 iterations)",
         lambda: try_method_iterative(hwnd, "METHOD 1: Iterative Resize", 3)),

        ("METHOD 2: Direct Border Calculation",
         lambda: try_method_direct_borders(hwnd, "METHOD 2: Direct Border Calculation")),

        ("METHOD 3: Iterative Resize (5 iterations)",
         lambda: try_method_iterative(hwnd, "METHOD 3: Iterative Resize (Extended)", 5)),

        ("METHOD 4: AdjustWindowRectEx API",
         lambda: try_method_adjust_window_rect(hwnd, "METHOD 4: AdjustWindowRectEx API", style, ex_style)),

        ("METHOD 5: Hardcoded Border Presets",
         lambda: try_method_hardcoded(hwnd, "METHOD 5: Hardcoded Border Presets")),

        ("METHOD 6: DPI-Scaled (Inverse Virtualization)",
         lambda: try_method_dpi_scaled(hwnd, "METHOD 6: DPI-Scaled Dimensions", dpi)),
    ]

    success = False
    working_method = None

    for method_name, method_func in methods:
        result = method_func()

        if result:
            success = True
            working_method = method_name
            break

        print()

    # Final report
    print_box("FINAL REPORT", "=")

    final_w, final_h = get_client_size(hwnd)

    print(f"Initial size: {initial_w}x{initial_h}")
    print(f"Final size: {final_w}x{final_h}")
    print(f"Target: {TARGET_WIDTH}x{TARGET_HEIGHT} (±{TOLERANCE}px tolerance)")
    print()

    if success:
        print(f"✅ SUCCESS!")
        print(f"Working method: {working_method}")
        print()
        print("Next steps:")
        print("  1. Note which method worked above")
        print("  2. This method will be used in bot_logic.py")
        print("  3. Bot should now work correctly")
    else:
        print(f"❌ ALL METHODS FAILED")
        print()
        print(f"Current size: {final_w}x{final_h}")
        print(f"Difference: {final_w - TARGET_WIDTH:+d}x{final_h - TARGET_HEIGHT:+d}")
        print()
        print("Possible issues:")
        print("  1. Game not set to 1280x800 in graphics settings")
        print("  2. Game in fullscreen mode (need windowed mode)")
        print("  3. Game has internal resolution limits")
        print("  4. Game window is maximized or locked")
        print()
        print("Recommendations:")
        print("  - Check in-game graphics settings")
        print("  - Look for 'Window Mode' or 'Display Mode' settings")
        print("  - Try setting to 'Windowed' or 'Windowed Borderless'")
        print("  - Make sure 1280x800 is selected")
        print("  - Restart game after changing settings")

    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\n[ERROR] Script failed: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
