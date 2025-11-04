import ctypes
import multiprocessing
import queue
import sys
import threading
from datetime import datetime

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtGui import QMovie, QIcon
    from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QMessageBox
except ImportError as exc:  # pragma: no cover - informative import guard
    raise ImportError("PyQt5 is required to run the GUI version of the bot.") from exc

import bot_logic


def speak_async(text):
    """Run text-to-speech in background thread to avoid blocking GUI"""
    def _speak():
        try:
            bot_logic.engine.say(text)
            bot_logic.engine.runAndWait()
        except Exception:
            pass  # Silently fail if TTS fails
    thread = threading.Thread(target=_speak, daemon=True)
    thread.start()

STYLE_SHEET = """
QWidget {
    background-color: #070d15;
    color: #d1f7ff;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 11pt;
}
QGroupBox {
    border: 1px solid #1f8b4c;
    border-radius: 8px;
    margin-top: 12px;
    padding: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #46ff9a;
    font-weight: bold;
    font-size: 10pt;
}
QGroupBox#statusGroup QLabel {
    font-weight: bold;
    font-size: 13pt;
}
QLabel#titleLabel {
    color: #46ff9a;
    font-size: 20pt;
    font-weight: bold;
}
QFrame#separatorLine {
    border: 1px solid #113c3d;
}
QLabel#statusValueLabel,
QLabel#lootValueLabel,
QLabel#legendaryValueLabel,
QLabel#runningTimeLabel {
    font-size: 18pt;
    font-weight: bold;
}
QLabel#statusValueLabel {
    color: #46ff9a;
}
QLabel#statusValueLabel[running="true"] {
    color: #1ed760;
}
QLabel#statusValueLabel[running="false"] {
    color: #ff5f6d;
}
QLabel#lootLabel {
    color: #FFD700;
}
QLabel#lootValueLabel {
    color: #FFD700;
}
QLabel#legendaryLabel {
    color: #FF6B6B;
}
QLabel#legendaryValueLabel {
    color: #FF6B6B;
}
QPushButton {
    background-color: #0f1f2e;
    border: 1px solid #46ff9a;
    border-radius: 6px;
    padding: 8px 16px;
    color: #46ff9a;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #152c40;
}
QPushButton:pressed {
    background-color: #091220;
}
QPushButton#startButton,
QPushButton#stopButton {
    padding: 16px 24px;
    min-height: 40px;
    font-size: 11pt;
}
QPushButton#startButton {
    border-color: #1ed760;
    color: #1ed760;
}
QPushButton#startButton:disabled {
    border-color: #0f3f26;
    color: #0f3f26;
}
QPushButton#stopButton {
    border-color: #ff5f6d;
    color: #ff5f6d;
}
QPushButton#stopButton:disabled {
    border-color: #4b1e24;
    color: #4b1e24;
}
QPushButton#resetTimingButton,
QPushButton#resetStatsButton {
    border-color: #66d9ff;
    color: #66d9ff;
}
QDoubleSpinBox {
    background-color: #03101d;
    border: 1px solid #1f8b4c;
    border-radius: 4px;
    padding: 4px 6px;
    color: #46ff9a;
    font-weight: bold;
}
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button {
    background: #0f1f2e;
    border: none;
    width: 18px;
}
QDoubleSpinBox::up-arrow,
QDoubleSpinBox::down-arrow {
    width: 10px;
    height: 10px;
}
QPlainTextEdit#logView {
    background-color: #010b10;
    border: 1px solid rgba(30, 215, 96, 0.4);
    border-radius: 10px;
    padding: 10px;
    color: #39ff14;
    font-family: "Fira Code", "Consolas", monospace;
    font-size: 11pt;
}
QPlainTextEdit#logView:focus {
    border-color: rgba(70, 255, 154, 0.6);
}
QPlainTextEdit#logView::selection {
    background-color: rgba(57, 255, 20, 0.3);
    color: #e8ffe8;
}
QTabWidget::pane {
    border: 1px solid #1f8b4c;
    border-radius: 8px;
    margin-top: 12px;
}
QTabWidget::tab-bar {
    alignment: left;
}
QTabBar::tab {
    background-color: #0b1724;
    border: 1px solid #1f8b4c;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 14px;
    margin-right: 6px;
    color: #66d9ff;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #152c40;
    color: #46ff9a;
}
QTabBar::tab:hover {
    background-color: #113c3d;
}
QScrollBar:vertical {
    background-color: #0b1724;
    border: 1px solid #1f8b4c;
    width: 12px;
    margin: 16px 0 16px 0;
}
QScrollBar::handle:vertical {
    background-color: #1f8b4c;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QTextBrowser {
    background-color: #010b10;
    border: 1px solid rgba(30, 215, 96, 0.4);
    border-radius: 10px;
    padding: 15px;
    color: #d1f7ff;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 10pt;
}
QTextBrowser:focus {
    border-color: rgba(70, 255, 154, 0.6);
}
"""


class DetectionOverlayWindow(QtWidgets.QWidget):
    """
    Window that displays the game window with detection zones overlaid.
    Green rectangles = detection found
    Red rectangles = no detection
    """
    def __init__(self, parent=None, log_callback=None):
        super().__init__(parent)
        self.setWindowTitle("TLOPO Looter - Detection Overlay [Position: 0, 0]")
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)

        # Store latest detection data
        self.game_image = None
        self.detection_zones = {}  # {zone_name: {'x': x, 'y': y, 'w': w, 'h': h, 'detected': bool}}
        self.zone_offsets = {}  # {zone_name: {'dx': 0, 'dy': 0}} - manual adjustments

        # Click visualization
        self.click_positions = []  # List of {'x': x, 'y': y, 'label': label, 'color': (r,g,b)}

        # Position tracking
        self.offset_x = 0
        self.offset_y = 0
        self.log_callback = log_callback

        # Dragging state
        self.dragging_zone = None
        self.drag_start_pos = None
        self.drag_start_zone_pos = None

        # Resolution info (set externally)
        self.resolution = "Unknown"
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.border_offset = (0, 0)

        # Create display label
        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #000000;")
        self.image_label.setMouseTracking(True)

        # Info label at top for instructions
        self.info_label = QtWidgets.QLabel("Drag zones | P: save | R: reset | C: clear clicks")
        self.info_label.setStyleSheet("background-color: #222222; color: #00FF00; padding: 5px; font-weight: bold;")
        self.info_label.setAlignment(QtCore.Qt.AlignCenter)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.info_label)
        layout.addWidget(self.image_label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Initial size
        self.resize(800, 600)

    def set_resolution_info(self, resolution, scale_x, scale_y, border_offset):
        """Set resolution info for debugging"""
        self.resolution = resolution
        self.scale_x = scale_x
        self.scale_y = scale_y
        self.border_offset = border_offset

    def reset_offsets(self):
        """Reset all manual zone offsets to default"""
        self.zone_offsets = {}
        if self.log_callback:
            self.log_callback("🔄 Overlay zones reset to default positions")
        # Redraw with reset positions
        if self.game_image is not None and self.detection_zones:
            self.update_detection_data(self.game_image, self.detection_zones)

    def add_click(self, x, y, label="Click", color=(255, 255, 0)):
        """Add a click position to visualize"""
        self.click_positions.append({'x': x, 'y': y, 'label': label, 'color': color})

    def clear_clicks(self):
        """Clear all click visualizations"""
        self.click_positions = []
        if self.log_callback:
            self.log_callback("🧹 Cleared click visualizations")

    def mousePressEvent(self, event):
        """Start dragging a zone"""
        if event.button() == QtCore.Qt.LeftButton:
            # Check if click is inside any zone
            click_pos = event.pos()
            # Account for info label height
            click_y = click_pos.y() - self.info_label.height()

            for zone_name, zone_data in self.detection_zones.items():
                offset = self.zone_offsets.get(zone_name, {'dx': 0, 'dy': 0})
                x = zone_data.get('x', 0) + offset['dx']
                y = zone_data.get('y', 0) + offset['dy']
                w = zone_data.get('w', 0)
                h = zone_data.get('h', 0)

                if x <= click_pos.x() <= x + w and y <= click_y <= y + h:
                    self.dragging_zone = zone_name
                    self.drag_start_pos = click_pos
                    self.drag_start_zone_pos = (x, y)
                    self.setCursor(QtCore.Qt.ClosedHandCursor)
                    break
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Update zone position while dragging"""
        if self.dragging_zone and self.drag_start_pos:
            delta_x = event.pos().x() - self.drag_start_pos.x()
            delta_y = event.pos().y() - self.drag_start_pos.y()

            # Update zone offset
            if self.dragging_zone not in self.zone_offsets:
                self.zone_offsets[self.dragging_zone] = {'dx': 0, 'dy': 0}

            original_x = self.detection_zones[self.dragging_zone].get('x', 0)
            original_y = self.detection_zones[self.dragging_zone].get('y', 0)
            new_x = self.drag_start_zone_pos[0] + delta_x
            new_y = self.drag_start_zone_pos[1] + delta_y

            self.zone_offsets[self.dragging_zone]['dx'] = new_x - original_x
            self.zone_offsets[self.dragging_zone]['dy'] = new_y - original_y

            # Redraw
            self.update_detection_data(self.game_image, self.detection_zones)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Stop dragging"""
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging_zone = None
            self.drag_start_pos = None
            self.drag_start_zone_pos = None
            self.setCursor(QtCore.Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == QtCore.Qt.Key_P:
            # Save all debug info to file
            self._save_debug_file()
        elif event.key() == QtCore.Qt.Key_R:
            # Reset all zone offsets to default
            self.reset_offsets()
        elif event.key() == QtCore.Qt.Key_C:
            # Clear click visualizations
            self.clear_clicks()
        super().keyPressEvent(event)

    def _save_debug_file(self):
        """Save zone positions and debug info to file"""
        from datetime import datetime
        import os

        if not self.detection_zones:
            if self.log_callback:
                self.log_callback("❌ No detection zones data available yet")
            return

        # Create filename with resolution
        resolution_safe = self.resolution.replace('x', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"overlay_debug_{resolution_safe}_{timestamp}.txt"

        # Build debug content
        lines = []
        lines.append("=" * 70)
        lines.append(f"TLOPO Looter - Detection Overlay Debug Report")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 70)
        lines.append("")
        lines.append("RESOLUTION INFO:")
        lines.append(f"  Game Resolution: {self.resolution}")
        lines.append(f"  Scale Factors: X={self.scale_x:.4f}, Y={self.scale_y:.4f}")
        lines.append(f"  Border Offset: X={self.border_offset[0]}px, Y={self.border_offset[1]}px")
        lines.append(f"  Overlay Window Position: X={self.offset_x}, Y={self.offset_y}")
        lines.append("")
        lines.append("DETECTION ZONES:")
        lines.append("-" * 70)

        for zone_name, zone_data in self.detection_zones.items():
            original_x = zone_data.get('x', 0)
            original_y = zone_data.get('y', 0)
            w = zone_data.get('w', 0)
            h = zone_data.get('h', 0)
            detected = zone_data.get('detected', False)

            offset = self.zone_offsets.get(zone_name, {'dx': 0, 'dy': 0})
            adjusted_x = original_x + offset['dx']
            adjusted_y = original_y + offset['dy']

            status = "DETECTED" if detected else "NOT FOUND"

            lines.append(f"\n{zone_name}:")
            lines.append(f"  Original Position: x={original_x}, y={original_y}")
            lines.append(f"  Adjusted Position: x={adjusted_x}, y={adjusted_y}")
            lines.append(f"  Manual Offset: dx={offset['dx']}, dy={offset['dy']}")
            lines.append(f"  Size: w={w}, h={h}")
            lines.append(f"  Status: {status}")

        lines.append("")
        lines.append("=" * 70)
        lines.append("NOTES:")
        lines.append("  - Original Position: Calculated by bot based on resolution scaling")
        lines.append("  - Adjusted Position: After manual dragging in overlay window")
        lines.append("  - Manual Offset: Difference between original and adjusted")
        lines.append("=" * 70)

        # Save to file
        try:
            with open(filename, 'w') as f:
                f.write('\n'.join(lines))

            if self.log_callback:
                self.log_callback(f"✅ Debug info saved to: {filename}")
                self.log_callback(f"📍 Window Position: X={self.offset_x}, Y={self.offset_y}")
                for zone_name in self.detection_zones.keys():
                    offset = self.zone_offsets.get(zone_name, {'dx': 0, 'dy': 0})
                    if offset['dx'] != 0 or offset['dy'] != 0:
                        self.log_callback(f"  {zone_name}: Offset dx={offset['dx']}, dy={offset['dy']}")
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"❌ Error saving debug file: {e}")

    def moveEvent(self, event):
        """Track position changes and update title"""
        super().moveEvent(event)
        pos = self.pos()
        self.offset_x = pos.x()
        self.offset_y = pos.y()
        self.setWindowTitle(f"TLOPO Looter - Detection Overlay [Position: {self.offset_x}, {self.offset_y}]")

    def get_offset(self):
        """Get current window offset"""
        return (self.offset_x, self.offset_y)

    def update_detection_data(self, game_image, zones):
        """
        Update the overlay with new detection data.
        Args:
            game_image: numpy array of game window screenshot (BGR format)
            zones: dict of {zone_name: {'x': x, 'y': y, 'w': w, 'h': h, 'detected': bool}}
        """
        import cv2
        import numpy as np

        if game_image is None:
            return

        # Store zones for position logging
        self.detection_zones = zones

        # Create a copy to draw on
        overlay_image = game_image.copy()

        # Draw rectangles for each detection zone
        for zone_name, zone_data in zones.items():
            # Get original position
            x = zone_data.get('x', 0)
            y = zone_data.get('y', 0)
            w = zone_data.get('w', 0)
            h = zone_data.get('h', 0)
            detected = zone_data.get('detected', False)

            # Apply manual offset if dragged
            offset = self.zone_offsets.get(zone_name, {'dx': 0, 'dy': 0})
            x += offset['dx']
            y += offset['dy']

            # Choose color: Green if detected, Red if not
            color = (0, 255, 0) if detected else (0, 0, 255)  # BGR format

            # Draw rectangle (thicker if manually adjusted)
            thickness = 3 if (offset['dx'] != 0 or offset['dy'] != 0) else 2
            cv2.rectangle(overlay_image, (x, y), (x + w, y + h), color, thickness)

            # Draw label with background
            label = f"{zone_name}: {'DETECTED' if detected else 'NOT FOUND'}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)

            # Draw background rectangle for text
            cv2.rectangle(overlay_image, (x, y - text_height - 10), (x + text_width + 10, y), color, -1)

            # Draw text
            text_color = (255, 255, 255)  # White text
            cv2.putText(overlay_image, label, (x + 5, y - 5), font, font_scale, text_color, thickness)

        # Draw click visualizations
        for click in self.click_positions:
            click_x = click['x']
            click_y = click['y']
            click_label = click['label']
            click_color = click['color']  # RGB format, need to convert to BGR

            # Convert RGB to BGR for OpenCV
            bgr_color = (click_color[2], click_color[1], click_color[0])

            # Draw filled circle for click position
            cv2.circle(overlay_image, (click_x, click_y), 8, bgr_color, -1)
            # Draw outline
            cv2.circle(overlay_image, (click_x, click_y), 8, (255, 255, 255), 2)

            # Draw small label next to click
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.4
            thickness = 1
            text_offset_x = click_x + 12
            text_offset_y = click_y + 5
            cv2.putText(overlay_image, click_label, (text_offset_x, text_offset_y),
                       font, font_scale, (255, 255, 255), thickness)

        # Convert BGR to RGB for Qt
        rgb_image = cv2.cvtColor(overlay_image, cv2.COLOR_BGR2RGB)

        # Convert to QImage
        height, width, channel = rgb_image.shape
        bytes_per_line = 3 * width
        q_image = QtGui.QImage(rgb_image.data, width, height, bytes_per_line, QtGui.QImage.Format_RGB888)

        # Update label
        pixmap = QtGui.QPixmap.fromImage(q_image)
        self.image_label.setPixmap(pixmap)
        self.resize(width, height)


class BotWindow(QtWidgets.QMainWindow):
    STATUS_POLL_INTERVAL_MS = 500

    def __init__(self, shared_state):
        super().__init__()
        self.started_flag = shared_state["started"]
        self.gui_settings_opened = shared_state["gui_settings_opened"]
        self.attack_delay = shared_state["attack_delay"]
        self.wait_after_enemy_spawn = shared_state["wait_after_enemy_spawn"]
        self.loot_opened = shared_state["loot_opened"]
        self.legendaries = shared_state["legendaries"]
        self.screenshot_enabled = shared_state["screenshot_enabled"]
        # Template matching thresholds
        self.threshold_open_loot = shared_state["threshold_open_loot"]
        self.threshold_loot_window = shared_state["threshold_loot_window"]
        self.threshold_hp_full = shared_state["threshold_hp_full"]
        self.threshold_hp_damaged = shared_state["threshold_hp_damaged"]
        self.threshold_hp_empty = shared_state["threshold_hp_empty"]
        # Debug options
        self.debug_mode = shared_state["debug_mode"]
        self.show_coords = shared_state["show_coords"]
        self.show_confidence = shared_state["show_confidence"]
        # Debug capture selection
        self.debug_capture_open_loot_flag = shared_state["debug_capture_open_loot"]
        self.debug_capture_loot_window_flag = shared_state["debug_capture_loot_window"]
        self.debug_capture_hp_full_flag = shared_state["debug_capture_hp_full"]
        self.debug_capture_hp_damaged_flag = shared_state["debug_capture_hp_damaged"]
        self.debug_capture_hp_empty_flag = shared_state["debug_capture_hp_empty"]
        # Manual capture trigger
        self.manual_capture_trigger = shared_state["manual_capture_trigger"]
        # Detection overlay
        self.overlay_enabled = shared_state["overlay_enabled"]

        self.status_queue = multiprocessing.Queue()
        self.process = None
        self._bot_start_time = None
        self._accumulated_time = 0  # Total seconds accumulated across sessions
        self._syncing_controls = False
        self._last_started_state = bool(self.started_flag.value)
        self._force_close = False  # Flag to force exit without tray

        # Detection overlay window
        self.overlay_window = None

        # Resolution tracking for overlay debugging
        self.current_resolution = "Unknown"
        self.current_scale_x = 1.0
        self.current_scale_y = 1.0
        self.current_border_offset = (0, 0)

        self._init_window()
        self._build_ui()
        self._connect_signals()
        self._start_status_timer()
        self._apply_theme()
        self._finalize_size()
        self._setup_tray_icon()

    def _init_window(self):
        self.setWindowTitle("TLOPO Looter")
        self.setMinimumSize(600, 650)

    def _build_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 0, 8, 8)  # left, top, right, bottom - no top margin
        main_layout.setSpacing(8)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)  # No margins around header
        header_layout.setSpacing(12)

        # Add animated GIF (left)
        self.gif_label = QtWidgets.QLabel()
        self.gif_label.setAlignment(QtCore.Qt.AlignCenter)
        self.gif_label.setScaledContents(True)
        self.gif_label.setMaximumSize(160, 120)  # Max size limit
        self.gif_label.setMinimumSize(80, 60)   # Min size limit
        gif_path = bot_logic.resource_path("img/pirates_skull.gif")
        self.movie = QMovie(gif_path)
        if self.movie.isValid():
            # Scale the GIF wider but not taller
            self.movie.setScaledSize(QtCore.QSize(128, 96))
            self.gif_label.setMovie(self.movie)
            self.movie.start()
            header_layout.addWidget(self.gif_label)

        # Add stretch to push title to center
        header_layout.addStretch()

        self.title_label = QtWidgets.QLabel("TLOPO Looter")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        header_layout.addWidget(self.title_label)

        # Add stretch to center the title
        header_layout.addStretch()

        # Add second pirate skull GIF on the right side
        self.chest_gif_label = QtWidgets.QLabel()
        self.chest_gif_label.setAlignment(QtCore.Qt.AlignCenter)
        self.chest_gif_label.setScaledContents(True)
        self.chest_gif_label.setMaximumSize(160, 120)  # Max size limit
        self.chest_gif_label.setMinimumSize(80, 60)   # Min size limit
        chest_gif_path = bot_logic.resource_path("img/pirates_skull.gif")
        self.chest_movie = QMovie(chest_gif_path)
        if self.chest_movie.isValid():
            # Scale the GIF to match left skull size
            self.chest_movie.setScaledSize(QtCore.QSize(128, 96))
            self.chest_gif_label.setMovie(self.chest_movie)
            self.chest_movie.start()
            header_layout.addWidget(self.chest_gif_label)

        main_layout.addLayout(header_layout)

        separator = QtWidgets.QFrame()
        separator.setObjectName("separatorLine")
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setLineWidth(1)
        main_layout.addWidget(separator)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setObjectName("tabWidget")
        main_layout.addWidget(self.tab_widget, stretch=1)

        dashboard_page = QtWidgets.QWidget()
        dashboard_layout = QtWidgets.QVBoxLayout(dashboard_page)
        dashboard_layout.setContentsMargins(6, 6, 6, 6)
        dashboard_layout.setSpacing(8)

        self.status_group = QtWidgets.QGroupBox("Current Status")
        self.status_group.setObjectName("statusGroup")
        status_layout = QtWidgets.QGridLayout()
        status_layout.setColumnStretch(1, 1)
        status_layout.setHorizontalSpacing(100)
        status_layout.setVerticalSpacing(8)

        status_layout.addWidget(QtWidgets.QLabel("⚙️ Bot Status"), 0, 0)
        self.status_value_label = QtWidgets.QLabel("Stopped")
        self.status_value_label.setObjectName("statusValueLabel")
        self.status_value_label.setProperty("running", "false")
        status_layout.addWidget(self.status_value_label, 0, 1)

        loot_label = QtWidgets.QLabel("💰 Loot Opened")
        loot_label.setObjectName("lootLabel")
        status_layout.addWidget(loot_label, 1, 0)
        self.loot_value_label = QtWidgets.QLabel("0")
        self.loot_value_label.setObjectName("lootValueLabel")
        status_layout.addWidget(self.loot_value_label, 1, 1)

        legendary_label = QtWidgets.QLabel("💎 Legendaries Found")
        legendary_label.setObjectName("legendaryLabel")
        status_layout.addWidget(legendary_label, 2, 0)
        self.legendary_value_label = QtWidgets.QLabel("0")
        self.legendary_value_label.setObjectName("legendaryValueLabel")
        status_layout.addWidget(self.legendary_value_label, 2, 1)

        status_layout.addWidget(QtWidgets.QLabel("⏱️ Running Time"), 3, 0)
        self.running_time_label = QtWidgets.QLabel("00:00:00")
        self.running_time_label.setObjectName("runningTimeLabel")
        status_layout.addWidget(self.running_time_label, 3, 1)

        self.status_group.setLayout(status_layout)
        dashboard_layout.addWidget(self.status_group)

        control_container = QtWidgets.QGroupBox("Quick Controls")
        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setSpacing(8)
        self.start_button = QtWidgets.QPushButton("▶️ Start")
        self.start_button.setObjectName("startButton")
        self.stop_button = QtWidgets.QPushButton("⏹️ Stop")
        self.stop_button.setObjectName("stopButton")
        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)
        control_container.setLayout(controls_layout)
        dashboard_layout.addWidget(control_container)

        self.tab_widget.addTab(dashboard_page, "Overview")

        advanced_page = QtWidgets.QWidget()
        advanced_layout = QtWidgets.QVBoxLayout(advanced_page)
        advanced_layout.setContentsMargins(6, 6, 6, 6)
        advanced_layout.setSpacing(8)

        timing_group = QtWidgets.QGroupBox("Timing Settings")
        timing_layout = QtWidgets.QGridLayout()
        timing_layout.setHorizontalSpacing(12)
        timing_layout.setVerticalSpacing(8)

        timing_layout.addWidget(QtWidgets.QLabel("Wait after enemy spawn (sec)"), 0, 0)
        self.wait_spin = QtWidgets.QDoubleSpinBox()
        self.wait_spin.setDecimals(3)
        self.wait_spin.setRange(0.0, 30.0)
        self.wait_spin.setSingleStep(0.25)
        self.wait_spin.setValue(float(self.wait_after_enemy_spawn.value))
        timing_layout.addWidget(self.wait_spin, 0, 1)

        timing_layout.addWidget(QtWidgets.QLabel("Time between attacks (sec)"), 1, 0)
        self.attack_spin = QtWidgets.QDoubleSpinBox()
        self.attack_spin.setDecimals(3)
        self.attack_spin.setRange(0.0, 10.0)
        self.attack_spin.setSingleStep(0.1)
        self.attack_spin.setValue(float(self.attack_delay.value))
        timing_layout.addWidget(self.attack_spin, 1, 1)

        timing_group.setLayout(timing_layout)
        advanced_layout.addWidget(timing_group)

        actions_group = QtWidgets.QGroupBox("Reset Options")
        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.setSpacing(8)
        self.reset_timings_button = QtWidgets.QPushButton("Reset Timers")
        self.reset_timings_button.setObjectName("resetTimingButton")
        self.reset_stats_button = QtWidgets.QPushButton("Reset Stats")
        self.reset_stats_button.setObjectName("resetStatsButton")
        actions_layout.addWidget(self.reset_timings_button)
        actions_layout.addWidget(self.reset_stats_button)
        actions_group.setLayout(actions_layout)
        advanced_layout.addWidget(actions_group)

        screenshot_group = QtWidgets.QGroupBox("Screenshot Options")
        screenshot_layout = QtWidgets.QVBoxLayout()
        screenshot_layout.setSpacing(8)

        self.screenshot_checkbox = QtWidgets.QCheckBox("Enable Screenshots")
        self.screenshot_checkbox.setChecked(bool(self.screenshot_enabled.value))
        screenshot_layout.addWidget(self.screenshot_checkbox)

        self.open_folder_button = QtWidgets.QPushButton("Open Screenshot Folder")
        self.open_folder_button.setObjectName("openFolderButton")
        self.open_folder_button.setEnabled(bool(self.screenshot_enabled.value))
        screenshot_layout.addWidget(self.open_folder_button)

        screenshot_group.setLayout(screenshot_layout)
        advanced_layout.addWidget(screenshot_group)

        # Note about thresholds moved to Debug tab
        thresholds_note = QtWidgets.QLabel("🐛 Template matching thresholds moved to Debug tab")
        thresholds_note.setStyleSheet("color: #66d9ff; font-size: 10pt; padding: 10px; background-color: #03101d; border-radius: 5px;")
        advanced_layout.addWidget(thresholds_note)

        # Create threshold spinboxes here (they'll be moved to Debug tab layout later)
        self.threshold_open_loot_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_open_loot_spin.setDecimals(2)
        self.threshold_open_loot_spin.setRange(0.10, 1.0)
        self.threshold_open_loot_spin.setSingleStep(0.05)
        self.threshold_open_loot_spin.setValue(float(self.threshold_open_loot.value))
        self.threshold_open_loot_spin.setToolTip("Default: 0.40 | Detects 'Press SHIFT to open' prompt")

        self.threshold_loot_window_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_loot_window_spin.setDecimals(2)
        self.threshold_loot_window_spin.setRange(0.10, 1.0)
        self.threshold_loot_window_spin.setSingleStep(0.05)
        self.threshold_loot_window_spin.setValue(float(self.threshold_loot_window.value))
        self.threshold_loot_window_spin.setToolTip("Default: 0.35 | Detects loot chest window UI")

        self.threshold_hp_full_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_hp_full_spin.setDecimals(2)
        self.threshold_hp_full_spin.setRange(0.10, 1.0)
        self.threshold_hp_full_spin.setSingleStep(0.05)
        self.threshold_hp_full_spin.setValue(float(self.threshold_hp_full.value))
        self.threshold_hp_full_spin.setToolTip("Default: 0.85 | Detects enemy with full HP")

        self.threshold_hp_damaged_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_hp_damaged_spin.setDecimals(2)
        self.threshold_hp_damaged_spin.setRange(0.10, 1.0)
        self.threshold_hp_damaged_spin.setSingleStep(0.05)
        self.threshold_hp_damaged_spin.setValue(float(self.threshold_hp_damaged.value))
        self.threshold_hp_damaged_spin.setToolTip("Default: 0.95 | Detects enemy with damaged HP")

        self.threshold_hp_empty_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_hp_empty_spin.setDecimals(2)
        self.threshold_hp_empty_spin.setRange(0.10, 1.0)
        self.threshold_hp_empty_spin.setSingleStep(0.05)
        self.threshold_hp_empty_spin.setValue(float(self.threshold_hp_empty.value))
        self.threshold_hp_empty_spin.setToolTip("Default: 0.90 | Detects enemy with empty HP")

        self.reset_thresholds_button = QtWidgets.QPushButton("Reset Thresholds to Defaults")
        self.reset_thresholds_button.setObjectName("resetThresholdsButton")

        log_group = QtWidgets.QGroupBox("Event Log")
        log_layout = QtWidgets.QVBoxLayout()
        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000)
        self.log_view.setPlaceholderText("Event trace will appear here...")
        self.log_view.setMinimumHeight(120)
        self.log_view.setMaximumHeight(150)
        log_layout.addWidget(self.log_view)
        log_group.setLayout(log_layout)
        advanced_layout.addWidget(log_group)

        self.tab_widget.addTab(advanced_page, "Advanced Settings")

        # Help Tab
        help_page = QtWidgets.QWidget()
        help_layout = QtWidgets.QVBoxLayout(help_page)
        help_layout.setContentsMargins(6, 6, 6, 6)
        help_layout.setSpacing(8)

        # Help text view
        help_text = QtWidgets.QTextBrowser()
        help_text.setOpenExternalLinks(False)
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <style>
            body { font-family: 'Consolas', monospace; color: #d1f7ff; background-color: #010b10; }
            h2 { color: #46ff9a; border-bottom: 2px solid #1f8b4c; padding-bottom: 5px; }
            h3 { color: #66d9ff; margin-top: 15px; }
            ul { margin-left: 20px; }
            li { margin-bottom: 8px; line-height: 1.5; }
            .warning { color: #ff5f6d; font-weight: bold; }
            .important { color: #FFD700; font-weight: bold; }
            .tip { color: #1ed760; }
        </style>

        <h2>📚 TLOPO Looter - User Manual</h2>
        <br>

        <h3>⚙️ First Time Setup</h3>
        <p><span class="warning"><b>IMPORTANT:</b></span></p>
        <ol>
            <li>Configure game DPI settings:
                <ul>
                    <li>Right-click the game shortcut → Properties</li>
                    <li>Compatibility tab → "Change high DPI settings"</li>
                    <li>Check "Override high DPI scaling"</li>
                    <li>Select <b>"System"</b> from the dropdown</li>
                    <li>Click OK and restart the game</li>
                </ul>
            </li>
            <li>Make sure the game window is <b>1280x800 resolution</b> (bot auto-adjusts)</li>
        </ol>

        <h3>🚀 How to Use</h3>
        <ol>
            <li><b>Start the game</b> - Open "The Legend of Pirates Online [BETA]"</li>
            <li><b>Position your character very close to the ENEMIES</b></li>
            <li><b>Click the "Start" button</b> in the Overview tab</li>
            <li><b>Let it run!</b> - The bot will <b>fully automatically</b>:
                <ul>
                    <li>Detect and attack enemies using the Ctrl key</li>
                    <li>Open chests that drop from defeated enemies</li>
                    <li>Collect small items</li>
                    <li>Collect legendary items</li>
                    <li>Trash regular loot</li>
                </ul>
            </li>
            <li><b>Click "Stop"</b> when you're done farming</li>
        </ol>

        <h3>📊 Statistics Explained</h3>
        <ul>
            <li><b>💰 Loot Opened:</b> Total chests/loot windows processed</li>
            <li><b>💎 Legendaries Found:</b> Number of legendary items detected</li>
            <li><b>⏱️ Running Time:</b> How long the bot has been active</li>
        </ul>

        <h3>📸 Screenshots</h3>
        <ul>
            <li>Enable/disable in the <b>Advanced Settings</b> tab</li>
            <li>Screenshots are saved in the <b>Data/All Loot Screenshots/</b> folder</li>
            <li>Each session gets its own timestamped folder</li>
            <li>Click "Open Screenshot Folder" to view</li>
        </ul>

        <h3>⚙️ Timing Settings</h3>
        <ul>
            <li><b>Wait after enemy spawn:</b> Delay before attacking (default 5.5s)</li>
            <li><b>Time between attacks:</b> Attack speed (default 0.1s)</li>
            <li>Adjust if the bot attacks too fast/slow</li>
        </ul>

        <h3>❓ Troubleshooting</h3>
        <ul>
            <li><span class="warning">Bot not clicking correctly?</span>
                <ul>
                    <li>Check DPI settings (see Setup above)</li>
                    <li>Make sure the game is exactly 1280x800</li>
                    <li>Restart the game after changing settings</li>
                </ul>
            </li>
            <li><span class="warning">Game window not detected?</span>
                <ul>
                    <li>Make sure the game window title is exact</li>
                    <li>Don't minimize the game window</li>
                </ul>
            </li>
            <li><span class="warning">Bot not collecting loot?</span>
                <ul>
                    <li>Make sure enemies are nearby and spawning</li>
                    <li>The bot automatically opens chests from defeated enemies</li>
                    <li>Check the Event Log for detection messages</li>
                </ul>
            </li>
        </ul>

        <h3>💡 Tips & Important Notes</h3>
        <ul>
            <li>Let the bot run while you do other things</li>
            <li>Check the Event Log in the Advanced Settings tab for details</li>
            <li>The Reset Stats button clears counters and timer</li>
            <li>Screenshots help track legendary drops</li>
        </ul>

        <p style="text-align: center; margin-top: 20px; color: #46ff9a; font-size: 11pt;">
            <b>🏴‍☠️ Happy Looting, Pirate! 🏴‍☠️</b>
        </p>
        """)

        help_layout.addWidget(help_text)
        self.tab_widget.addTab(help_page, "❓ Help")

        # Debug Tab
        debug_page = QtWidgets.QWidget()
        debug_layout = QtWidgets.QVBoxLayout(debug_page)
        debug_layout.setContentsMargins(6, 6, 6, 6)
        debug_layout.setSpacing(8)

        # Threshold controls (now in Debug tab)
        debug_threshold_group = QtWidgets.QGroupBox("🎯 Template Matching Thresholds")
        debug_threshold_layout = QtWidgets.QGridLayout()
        debug_threshold_layout.setHorizontalSpacing(12)
        debug_threshold_layout.setVerticalSpacing(8)

        # Info label
        threshold_info = QtWidgets.QLabel("⚠️ Range: 0.10 (very lenient) to 1.00 (strict)\n"
                                         "Lower = easier detection, more false positives\n"
                                         "At 1024x768: Try 0.20-0.30 for Open Loot and Loot Window")
        threshold_info.setStyleSheet("color: #ffa500; font-size: 9pt; padding: 5px;")
        debug_threshold_layout.addWidget(threshold_info, 0, 0, 1, 2)

        # Reference existing spinboxes (already created in Advanced tab)
        row = 1
        debug_threshold_layout.addWidget(QtWidgets.QLabel("Open Loot Detection"), row, 0)
        debug_threshold_layout.addWidget(self.threshold_open_loot_spin, row, 1)
        row += 1

        debug_threshold_layout.addWidget(QtWidgets.QLabel("Loot Window Detection"), row, 0)
        debug_threshold_layout.addWidget(self.threshold_loot_window_spin, row, 1)
        row += 1

        debug_threshold_layout.addWidget(QtWidgets.QLabel("HP Full Detection"), row, 0)
        debug_threshold_layout.addWidget(self.threshold_hp_full_spin, row, 1)
        row += 1

        debug_threshold_layout.addWidget(QtWidgets.QLabel("HP Damaged Detection"), row, 0)
        debug_threshold_layout.addWidget(self.threshold_hp_damaged_spin, row, 1)
        row += 1

        debug_threshold_layout.addWidget(QtWidgets.QLabel("HP Empty Detection"), row, 0)
        debug_threshold_layout.addWidget(self.threshold_hp_empty_spin, row, 1)
        row += 1

        # Reset button
        debug_threshold_layout.addWidget(self.reset_thresholds_button, row, 0, 1, 2)

        debug_threshold_group.setLayout(debug_threshold_layout)
        debug_layout.addWidget(debug_threshold_group)

        # Debug Visualization Options
        debug_viz_group = QtWidgets.QGroupBox("🔍 Detection Visualization")
        debug_viz_layout = QtWidgets.QVBoxLayout()
        debug_viz_layout.setSpacing(8)

        # Enable debug mode
        self.debug_mode_checkbox = QtWidgets.QCheckBox("Enable Debug Mode (saves detection screenshots)")
        self.debug_mode_checkbox.setChecked(False)
        self.debug_mode_checkbox.setToolTip("Saves screenshots of each detection attempt to Data/Debug/ folder")
        debug_viz_layout.addWidget(self.debug_mode_checkbox)

        # Show click coordinates
        self.show_coords_checkbox = QtWidgets.QCheckBox("Log click coordinates in Event Log")
        self.show_coords_checkbox.setChecked(False)
        self.show_coords_checkbox.setToolTip("Shows exact X,Y coordinates where bot clicks")
        debug_viz_layout.addWidget(self.show_coords_checkbox)

        # Show detection confidence
        self.show_confidence_checkbox = QtWidgets.QCheckBox("Log template match confidence scores")
        self.show_confidence_checkbox.setChecked(False)
        self.show_confidence_checkbox.setToolTip("Shows how confident the bot is about each detection (0.0-1.0)")
        debug_viz_layout.addWidget(self.show_confidence_checkbox)

        # Add separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        debug_viz_layout.addWidget(separator)

        # Debug capture selection label
        capture_label = QtWidgets.QLabel("📷 Select which detections to capture (when Debug Mode enabled):")
        capture_label.setStyleSheet("color: #ffa500; font-weight: bold; margin-top: 5px;")
        debug_viz_layout.addWidget(capture_label)

        # Checkboxes for each detection type
        self.debug_capture_open_loot = QtWidgets.QCheckBox("Capture Open Loot prompt")
        self.debug_capture_open_loot.setChecked(True)
        debug_viz_layout.addWidget(self.debug_capture_open_loot)

        self.debug_capture_loot_window = QtWidgets.QCheckBox("Capture Loot Window")
        self.debug_capture_loot_window.setChecked(True)
        debug_viz_layout.addWidget(self.debug_capture_loot_window)

        self.debug_capture_hp_full = QtWidgets.QCheckBox("Capture Enemy HP (Full)")
        self.debug_capture_hp_full.setChecked(False)
        debug_viz_layout.addWidget(self.debug_capture_hp_full)

        self.debug_capture_hp_damaged = QtWidgets.QCheckBox("Capture Enemy HP (Damaged)")
        self.debug_capture_hp_damaged.setChecked(False)
        debug_viz_layout.addWidget(self.debug_capture_hp_damaged)

        self.debug_capture_hp_empty = QtWidgets.QCheckBox("Capture Enemy HP (Empty)")
        self.debug_capture_hp_empty.setChecked(False)
        debug_viz_layout.addWidget(self.debug_capture_hp_empty)

        # Capture current state button
        self.capture_state_button = QtWidgets.QPushButton("📸 Capture Current Detection State")
        self.capture_state_button.setObjectName("captureStateButton")
        self.capture_state_button.setToolTip("Saves screenshots of all detection zones RIGHT NOW for inspection")
        debug_viz_layout.addWidget(self.capture_state_button)

        # Open debug folder button
        self.open_debug_folder_button = QtWidgets.QPushButton("📂 Open Debug Screenshot Folder")
        self.open_debug_folder_button.setObjectName("openDebugFolderButton")
        debug_viz_layout.addWidget(self.open_debug_folder_button)

        # Add separator
        separator2 = QtWidgets.QFrame()
        separator2.setFrameShape(QtWidgets.QFrame.HLine)
        separator2.setFrameShadow(QtWidgets.QFrame.Sunken)
        debug_viz_layout.addWidget(separator2)

        # Detection overlay window button
        self.show_overlay_button = QtWidgets.QPushButton("🎯 Show Detection Overlay Window")
        self.show_overlay_button.setObjectName("showOverlayButton")
        self.show_overlay_button.setToolTip("Opens real-time window showing detection zones (Green = detected, Red = not detected)")
        self.show_overlay_button.setCheckable(True)
        self.show_overlay_button.setChecked(False)
        debug_viz_layout.addWidget(self.show_overlay_button)

        debug_viz_group.setLayout(debug_viz_layout)
        debug_layout.addWidget(debug_viz_group)

        # Detection Info Display
        debug_info_group = QtWidgets.QGroupBox("📊 Current Detection Info")
        debug_info_layout = QtWidgets.QGridLayout()
        debug_info_layout.setHorizontalSpacing(12)
        debug_info_layout.setVerticalSpacing(6)

        # Resolution info
        debug_info_layout.addWidget(QtWidgets.QLabel("Game Resolution:"), 0, 0)
        self.debug_resolution_label = QtWidgets.QLabel("Not detected yet")
        self.debug_resolution_label.setStyleSheet("color: #66d9ff; font-weight: bold;")
        debug_info_layout.addWidget(self.debug_resolution_label, 0, 1)

        # Scale factors
        debug_info_layout.addWidget(QtWidgets.QLabel("Scale Factors:"), 1, 0)
        self.debug_scale_label = QtWidgets.QLabel("Not detected yet")
        self.debug_scale_label.setStyleSheet("color: #66d9ff; font-weight: bold;")
        debug_info_layout.addWidget(self.debug_scale_label, 1, 1)

        # Last detection
        debug_info_layout.addWidget(QtWidgets.QLabel("Last Detection:"), 2, 0)
        self.debug_last_detection_label = QtWidgets.QLabel("None")
        self.debug_last_detection_label.setStyleSheet("color: #46ff9a; font-weight: bold;")
        debug_info_layout.addWidget(self.debug_last_detection_label, 2, 1)

        # Last click
        debug_info_layout.addWidget(QtWidgets.QLabel("Last Click:"), 3, 0)
        self.debug_last_click_label = QtWidgets.QLabel("None")
        self.debug_last_click_label.setStyleSheet("color: #46ff9a; font-weight: bold;")
        debug_info_layout.addWidget(self.debug_last_click_label, 3, 1)

        debug_info_group.setLayout(debug_info_layout)
        debug_layout.addWidget(debug_info_group)

        # Debug hints
        debug_hints = QtWidgets.QLabel(
            "💡 Troubleshooting Tips:\n"
            "• At 1024x768: Lower Open Loot to 0.20-0.25, Loot Window to 0.15-0.20\n"
            "• Enable Debug Mode to see what the bot sees\n"
            "• Check 'Log coordinates' to verify click positions\n"
            "• Use 'Capture State' button when bot should detect something but doesn't"
        )
        debug_hints.setStyleSheet("color: #8af7ff; font-size: 9pt; padding: 10px; background-color: #03101d; border-radius: 5px;")
        debug_hints.setWordWrap(True)
        debug_layout.addWidget(debug_hints)

        debug_layout.addStretch()

        self.tab_widget.addTab(debug_page, "🐛 Debug")

        self._update_status_labels(initial=True)

    def _connect_signals(self):
        self.start_button.clicked.connect(self._handle_start_clicked)
        self.stop_button.clicked.connect(self._handle_stop_clicked)
        self.reset_timings_button.clicked.connect(self._handle_reset_timings)
        self.reset_stats_button.clicked.connect(self._handle_reset_stats)

        self.wait_spin.valueChanged.connect(self._handle_wait_changed)
        self.attack_spin.valueChanged.connect(self._handle_attack_changed)

        self.screenshot_checkbox.stateChanged.connect(self._handle_screenshot_toggled)
        self.open_folder_button.clicked.connect(self._handle_open_folder)

        # Threshold spinbox signals
        self.threshold_open_loot_spin.valueChanged.connect(self._handle_threshold_open_loot_changed)
        self.threshold_loot_window_spin.valueChanged.connect(self._handle_threshold_loot_window_changed)
        self.threshold_hp_full_spin.valueChanged.connect(self._handle_threshold_hp_full_changed)
        self.threshold_hp_damaged_spin.valueChanged.connect(self._handle_threshold_hp_damaged_changed)
        self.threshold_hp_empty_spin.valueChanged.connect(self._handle_threshold_hp_empty_changed)
        self.reset_thresholds_button.clicked.connect(self._handle_reset_thresholds)

        # Debug signals
        self.debug_mode_checkbox.stateChanged.connect(self._handle_debug_mode_toggled)
        self.show_coords_checkbox.stateChanged.connect(self._handle_show_coords_toggled)
        self.show_confidence_checkbox.stateChanged.connect(self._handle_show_confidence_toggled)
        self.capture_state_button.clicked.connect(self._handle_capture_state)
        self.open_debug_folder_button.clicked.connect(self._handle_open_debug_folder)
        self.show_overlay_button.toggled.connect(self._handle_show_overlay_toggled)
        # Debug capture selection signals
        self.debug_capture_open_loot.stateChanged.connect(lambda state: self._handle_debug_capture_toggled('open_loot', state))
        self.debug_capture_loot_window.stateChanged.connect(lambda state: self._handle_debug_capture_toggled('loot_window', state))
        self.debug_capture_hp_full.stateChanged.connect(lambda state: self._handle_debug_capture_toggled('hp_full', state))
        self.debug_capture_hp_damaged.stateChanged.connect(lambda state: self._handle_debug_capture_toggled('hp_damaged', state))
        self.debug_capture_hp_empty.stateChanged.connect(lambda state: self._handle_debug_capture_toggled('hp_empty', state))

    def _start_status_timer(self):
        self.status_timer = QtCore.QTimer(self)
        self.status_timer.setInterval(self.STATUS_POLL_INTERVAL_MS)
        self.status_timer.timeout.connect(self._poll_status)
        self.status_timer.start()

    def _apply_theme(self):
        palette = self.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor("#070d15"))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor("#d1f7ff"))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor("#03101d"))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor("#0f1f2e"))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor("#8af7ff"))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor("#0f1f2e"))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor("#46ff9a"))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor("#1f8b4c"))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor("#0b1724"))
        self.setPalette(palette)
        self.setStyleSheet(STYLE_SHEET)

    def _finalize_size(self):
        self.adjustSize()
        size_hint = self.sizeHint()
        if size_hint.isValid():
            width = max(600, size_hint.width())
            height = size_hint.height()
            self.setMinimumSize(width, height)
            self.resize(width, height)

    def _setup_tray_icon(self):
        """Setup system tray icon with menu"""
        # Check if system tray is available
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self)

        # Try to load icon, fallback to default if not found
        icon_path = bot_logic.resource_path("icon.ico")
        try:
            icon = QIcon(icon_path)
            if not icon.isNull():
                self.tray_icon.setIcon(icon)
                self.setWindowIcon(icon)  # Also set window icon
            else:
                # Fallback to default icon
                self.tray_icon.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))
        except:
            self.tray_icon.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon))

        # Create tray menu
        tray_menu = QMenu()

        show_action = tray_menu.addAction("Show Window")
        show_action.triggered.connect(self._restore_from_tray)

        tray_menu.addSeparator()

        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(self._exit_application)

        self.tray_icon.setContextMenu(tray_menu)

        # Connect double-click to restore
        self.tray_icon.activated.connect(self._tray_icon_activated)

        # Show tray icon
        self.tray_icon.show()

    def _tray_icon_activated(self, reason):
        """Handle tray icon activation (click)"""
        if reason == QSystemTrayIcon.DoubleClick:
            self._restore_from_tray()

    def _restore_from_tray(self):
        """Restore window from system tray"""
        self.show()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized | QtCore.Qt.WindowActive)
        self.activateWindow()

    def _minimize_to_tray(self):
        """Minimize window to system tray"""
        self.hide()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.showMessage(
                "TLOPO Looter",
                "Application minimized to tray. Double-click to restore.",
                QSystemTrayIcon.Information,
                2000
            )

    def _exit_application(self):
        """Force exit the application"""
        self._force_close = True
        self.close()

    def _validate_startup_requirements(self):
        """
        Validate all requirements before starting bot.
        Runs in separate process to avoid PyQt5 event loop interference.
        Returns: (success, error_message)
        """
        try:
            # Run validation in subprocess to avoid PyQt5 event loop interference
            # PyQt5's event loop causes window resize to fail
            import subprocess
            import sys

            # Run validation script directly
            result = subprocess.run(
                [sys.executable, "-c",
                 "import bot_logic; success, msg, details = bot_logic.validate_game_ready(); print('SUCCESS' if success else f'FAIL:{msg}')"],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Get last line only (ignore any debug output)
            lines = result.stdout.strip().split('\n')
            last_line = lines[-1] if lines else ''

            if last_line == 'SUCCESS':
                return (True, "Validation passed")
            elif last_line.startswith('FAIL:'):
                return (False, last_line[5:])  # Remove 'FAIL:' prefix
            else:
                return (False, f"Validation error: {last_line if last_line else 'No output'}")

        except subprocess.TimeoutExpired:
            return (False, "Validation timeout")
        except Exception as e:
            return (False, f"Validation error: {e}")

    def _show_validation_error(self, error_message):
        """Show error dialog and switch to Help tab"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Startup Validation Failed")
        msg_box.setText(error_message)
        msg_box.setInformativeText("Please check the Help tab for setup instructions.")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()

        # Switch to Help tab (index 2: Overview=0, Advanced=1, Help=2)
        self.tab_widget.setCurrentIndex(2)

        # Log the validation failure
        self._append_log(f"Startup blocked: {error_message}")

    def _handle_start_clicked(self):
        if self._bot_is_running():
            self._append_log("Bot is already running.")
            return

        # Validate before starting
        is_valid, error_msg = self._validate_startup_requirements()
        if not is_valid:
            self._show_validation_error(error_msg)
            return

        try:
            self.gui_settings_opened.value = False
            self._drain_status_queue(log_messages=False)
            self.process = multiprocessing.Process(
                target=bot_logic.run_bot,
                args=(
                    self.started_flag,
                    self.attack_delay,
                    self.wait_after_enemy_spawn,
                    self.gui_settings_opened,
                    self.loot_opened,
                    self.legendaries,
                    self.status_queue,
                    self.screenshot_enabled,
                    self.threshold_open_loot,
                    self.threshold_loot_window,
                    self.threshold_hp_full,
                    self.threshold_hp_damaged,
                    self.threshold_hp_empty,
                    self.debug_mode,
                    self.show_coords,
                    self.show_confidence,
                    self.debug_capture_open_loot_flag,
                    self.debug_capture_loot_window_flag,
                    self.debug_capture_hp_full_flag,
                    self.debug_capture_hp_damaged_flag,
                    self.debug_capture_hp_empty_flag,
                    self.manual_capture_trigger,
                    self.overlay_enabled,
                ),
            )
            self.process.daemon = True
            self.process.start()
            with self.started_flag.get_lock():
                self.started_flag.value = True
            self._bot_start_time = datetime.now()
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000002)
            speak_async("Bot Started")
            self._append_log("Bot process started.")
        except Exception as exc:  # pragma: no cover - runtime safeguard
            self._append_log(f"Failed to start bot: {exc}")
            self.process = None
            with self.started_flag.get_lock():
                self.started_flag.value = False
        finally:
            self._update_status_labels()

    def _handle_stop_clicked(self):
        self._stop_bot_process(manual=True)

    def _handle_reset_timings(self):
        defaults = {"attack_delay": 0.1, "wait_after_enemy_spawn": 5.5}
        with self.attack_delay.get_lock():
            self.attack_delay.value = defaults["attack_delay"]
        with self.wait_after_enemy_spawn.get_lock():
            self.wait_after_enemy_spawn.value = defaults["wait_after_enemy_spawn"]
        self._syncing_controls = True
        self.attack_spin.setValue(defaults["attack_delay"])
        self.wait_spin.setValue(defaults["wait_after_enemy_spawn"])
        self._syncing_controls = False
        self._append_log("Timing settings reset to defaults.")

    def _handle_reset_stats(self):
        with self.loot_opened.get_lock():
            self.loot_opened.value = 0
        with self.legendaries.get_lock():
            self.legendaries.value = 0
        self._accumulated_time = 0
        # If bot is running, restart timer from now; otherwise clear it
        if self._bot_is_running():
            self._bot_start_time = datetime.now()
        else:
            self._bot_start_time = None
        self._append_log("Statistics and timer reset.")
        self._update_status_labels()

    def _handle_wait_changed(self, value):
        if self._syncing_controls:
            return
        with self.wait_after_enemy_spawn.get_lock():
            self.wait_after_enemy_spawn.value = float(value)
        if self.wait_spin.hasFocus():
            self._append_log(f"Updated wait after spawn to {value:.3f}s.")

    def _handle_attack_changed(self, value):
        if self._syncing_controls:
            return
        with self.attack_delay.get_lock():
            self.attack_delay.value = float(value)
        if self.attack_spin.hasFocus():
            self._append_log(f"Updated attack delay to {value:.3f}s.")

    def _handle_threshold_open_loot_changed(self, value):
        if self._syncing_controls:
            return
        with self.threshold_open_loot.get_lock():
            self.threshold_open_loot.value = float(value)
        if self.threshold_open_loot_spin.hasFocus():
            self._append_log(f"Updated Open Loot threshold to {value:.2f}.")

    def _handle_threshold_loot_window_changed(self, value):
        if self._syncing_controls:
            return
        with self.threshold_loot_window.get_lock():
            self.threshold_loot_window.value = float(value)
        if self.threshold_loot_window_spin.hasFocus():
            self._append_log(f"Updated Loot Window threshold to {value:.2f}.")

    def _handle_threshold_hp_full_changed(self, value):
        if self._syncing_controls:
            return
        with self.threshold_hp_full.get_lock():
            self.threshold_hp_full.value = float(value)
        if self.threshold_hp_full_spin.hasFocus():
            self._append_log(f"Updated HP Full threshold to {value:.2f}.")

    def _handle_threshold_hp_damaged_changed(self, value):
        if self._syncing_controls:
            return
        with self.threshold_hp_damaged.get_lock():
            self.threshold_hp_damaged.value = float(value)
        if self.threshold_hp_damaged_spin.hasFocus():
            self._append_log(f"Updated HP Damaged threshold to {value:.2f}.")

    def _handle_threshold_hp_empty_changed(self, value):
        if self._syncing_controls:
            return
        with self.threshold_hp_empty.get_lock():
            self.threshold_hp_empty.value = float(value)
        if self.threshold_hp_empty_spin.hasFocus():
            self._append_log(f"Updated HP Empty threshold to {value:.2f}.")

    def _handle_reset_thresholds(self):
        defaults = {
            "threshold_open_loot": 0.40,
            "threshold_loot_window": 0.35,
            "threshold_hp_full": 0.85,
            "threshold_hp_damaged": 0.95,
            "threshold_hp_empty": 0.90,
        }
        with self.threshold_open_loot.get_lock():
            self.threshold_open_loot.value = defaults["threshold_open_loot"]
        with self.threshold_loot_window.get_lock():
            self.threshold_loot_window.value = defaults["threshold_loot_window"]
        with self.threshold_hp_full.get_lock():
            self.threshold_hp_full.value = defaults["threshold_hp_full"]
        with self.threshold_hp_damaged.get_lock():
            self.threshold_hp_damaged.value = defaults["threshold_hp_damaged"]
        with self.threshold_hp_empty.get_lock():
            self.threshold_hp_empty.value = defaults["threshold_hp_empty"]

        self._syncing_controls = True
        self.threshold_open_loot_spin.setValue(defaults["threshold_open_loot"])
        self.threshold_loot_window_spin.setValue(defaults["threshold_loot_window"])
        self.threshold_hp_full_spin.setValue(defaults["threshold_hp_full"])
        self.threshold_hp_damaged_spin.setValue(defaults["threshold_hp_damaged"])
        self.threshold_hp_empty_spin.setValue(defaults["threshold_hp_empty"])
        self._syncing_controls = False
        self._append_log("Threshold settings reset to defaults.")

    def _handle_debug_mode_toggled(self, state):
        """Handle debug mode checkbox toggle"""
        is_enabled = (state == QtCore.Qt.Checked)
        with self.debug_mode.get_lock():
            self.debug_mode.value = is_enabled
        status_text = "enabled" if is_enabled else "disabled"
        self._append_log(f"Debug mode {status_text}. Detection screenshots will {'be saved' if is_enabled else 'NOT be saved'} to Data/Debug/")

    def _handle_show_coords_toggled(self, state):
        """Handle show coordinates checkbox toggle"""
        is_enabled = (state == QtCore.Qt.Checked)
        with self.show_coords.get_lock():
            self.show_coords.value = is_enabled
        status_text = "enabled" if is_enabled else "disabled"
        self._append_log(f"Coordinate logging {status_text}.")

    def _handle_show_confidence_toggled(self, state):
        """Handle show confidence checkbox toggle"""
        is_enabled = (state == QtCore.Qt.Checked)
        with self.show_confidence.get_lock():
            self.show_confidence.value = is_enabled
        status_text = "enabled" if is_enabled else "disabled"
        self._append_log(f"Confidence score logging {status_text}.")

    def _handle_debug_capture_toggled(self, detection_type, state):
        """Handle debug capture checkbox toggle"""
        is_enabled = (state == QtCore.Qt.Checked)
        flag_map = {
            'open_loot': self.debug_capture_open_loot_flag,
            'loot_window': self.debug_capture_loot_window_flag,
            'hp_full': self.debug_capture_hp_full_flag,
            'hp_damaged': self.debug_capture_hp_damaged_flag,
            'hp_empty': self.debug_capture_hp_empty_flag,
        }
        if detection_type in flag_map:
            with flag_map[detection_type].get_lock():
                flag_map[detection_type].value = is_enabled
            name_map = {
                'open_loot': 'Open Loot',
                'loot_window': 'Loot Window',
                'hp_full': 'HP Full',
                'hp_damaged': 'HP Damaged',
                'hp_empty': 'HP Empty',
            }
            status = "enabled" if is_enabled else "disabled"
            self._append_log(f"Debug capture for {name_map[detection_type]}: {status}")

    def _handle_capture_state(self):
        """Capture current detection state for debugging"""
        if not self._bot_is_running():
            self._append_log("❌ Cannot capture state: Bot is not running.")
            return

        # Trigger manual capture by incrementing the counter
        with self.manual_capture_trigger.get_lock():
            self.manual_capture_trigger.value += 1

        self._append_log(f"📸 Manual capture triggered! Bot will save screenshots of all detection zones on next loop iteration.")
        self._append_log(f"   Check Data/Debug/ folder for files with 'MANUAL' in the name.")

    def _handle_open_debug_folder(self):
        """Open the debug screenshot folder in Windows Explorer"""
        import os
        import subprocess

        debug_folder = bot_logic.get_data_path('Data\\Debug')

        # Create folder if it doesn't exist
        folder_existed = os.path.exists(debug_folder)
        success, error = bot_logic.ensure_directory_exists(debug_folder)
        if not success:
            self._append_log(f"Error creating debug folder: {error}")
            return
        if not folder_existed:
            self._append_log(f"Created debug folder: {debug_folder}")

        # Open folder in Explorer
        try:
            subprocess.Popen(f'explorer "{debug_folder}"')
            self._append_log("Opened debug screenshot folder.")
        except Exception as e:
            self._append_log(f"Error opening debug folder: {e}")

    def _handle_show_overlay_toggled(self, checked):
        """Handle detection overlay window toggle"""
        if not self._bot_is_running():
            self._append_log("❌ Cannot show overlay: Bot is not running.")
            self.show_overlay_button.setChecked(False)
            return

        if checked:
            # Enable overlay data sending in bot
            with self.overlay_enabled.get_lock():
                self.overlay_enabled.value = True

            # Create and show overlay window
            self._append_log("📍 TIP: Drag zones to adjust positions. Press 'P' to save debug file.")
            if self.overlay_window is None:
                self.overlay_window = DetectionOverlayWindow(log_callback=self._append_log)
                # Set resolution info if available
                self.overlay_window.set_resolution_info(
                    self.current_resolution,
                    self.current_scale_x,
                    self.current_scale_y,
                    self.current_border_offset
                )
            self.overlay_window.show()
            self._append_log("✅ Detection overlay opened. Drag zones, press 'P' to save positions.")
        else:
            # Disable overlay data sending
            with self.overlay_enabled.get_lock():
                self.overlay_enabled.value = False

            # Hide overlay window
            if self.overlay_window:
                self.overlay_window.hide()
            self._append_log("Overlay window closed.")

    def _handle_screenshot_toggled(self, state):
        """Handle screenshot checkbox toggle"""
        is_enabled = (state == QtCore.Qt.Checked)
        with self.screenshot_enabled.get_lock():
            self.screenshot_enabled.value = is_enabled

        # Enable/disable the open folder button based on checkbox state
        self.open_folder_button.setEnabled(is_enabled)

        status_text = "enabled" if is_enabled else "disabled"
        self._append_log(f"Screenshots {status_text}.")

    def _handle_open_folder(self):
        """Open the screenshot folder in Windows Explorer"""
        import os
        import subprocess

        # Base screenshot folder
        base_folder = bot_logic.get_data_path('Data\\All Loot Screenshots')

        # Try to find the latest session folder
        folder_to_open = base_folder
        try:
            if os.path.exists(base_folder):
                # List all session folders
                session_folders = [
                    f for f in os.listdir(base_folder)
                    if os.path.isdir(os.path.join(base_folder, f)) and f.startswith('Session_')
                ]
                if session_folders:
                    # Sort by name (timestamp in folder name ensures chronological order)
                    session_folders.sort(reverse=True)
                    latest_session = session_folders[0]
                    folder_to_open = os.path.join(base_folder, latest_session)
                    self._append_log(f"Opening latest session: {latest_session}")
        except Exception as e:
            self._append_log(f"Error finding latest session: {e}")

        # Create folder if it doesn't exist
        folder_existed = os.path.exists(folder_to_open)
        success, error = bot_logic.ensure_directory_exists(folder_to_open)
        if not success:
            self._append_log(f"Error creating folder: {error}")
            return
        if not folder_existed:
            self._append_log(f"Created screenshot folder: {folder_to_open}")

        # Open folder in Explorer
        try:
            subprocess.Popen(f'explorer "{folder_to_open}"')
            self._append_log("Opened screenshot folder.")
        except Exception as e:
            self._append_log(f"Error opening folder: {e}")

    def _poll_status(self):
        current_started = bool(self.started_flag.value)
        process_alive = self.process.is_alive() if self.process else False

        if self.process and not process_alive and current_started:
            # Bot ended unexpectedly; update state and accumulate time.
            if self._bot_start_time is not None:
                elapsed = (datetime.now() - self._bot_start_time).total_seconds()
                self._accumulated_time += elapsed
                self._bot_start_time = None
            with self.started_flag.get_lock():
                self.started_flag.value = False
            self._append_log("Bot process ended unexpectedly.")
            self.process = None
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

        if self._last_started_state and not current_started:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            if self.process and not process_alive:
                self._append_log("Bot process stopped.")
            if self._bot_start_time is not None:
                elapsed = (datetime.now() - self._bot_start_time).total_seconds()
                self._accumulated_time += elapsed
                self._bot_start_time = None
            self.process = None

        self._drain_status_queue()

        self._syncing_controls = True
        self.wait_spin.setValue(float(self.wait_after_enemy_spawn.value))
        self.attack_spin.setValue(float(self.attack_delay.value))
        self._syncing_controls = False

        self._update_status_labels()
        self._last_started_state = current_started

    def _update_status_labels(self, initial=False):
        running = bool(self.started_flag.value)
        self.status_value_label.setText("Running" if running else "Stopped")
        self.status_value_label.setProperty("running", "true" if running else "false")
        self._refresh_status_style()
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

        self.loot_value_label.setText(str(int(self.loot_opened.value)))
        self.legendary_value_label.setText(str(int(self.legendaries.value)))

        # Update running time display
        total_seconds = self._accumulated_time
        if running and self._bot_start_time is not None:
            # Add current session time to accumulated time
            current_elapsed = (datetime.now() - self._bot_start_time).total_seconds()
            total_seconds += current_elapsed

        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        self.running_time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def _refresh_status_style(self):
        self.status_value_label.style().unpolish(self.status_value_label)
        self.status_value_label.style().polish(self.status_value_label)
        self.status_value_label.update()

    def _drain_status_queue(self, log_messages=True):
        if self.status_queue is None:
            return
        while True:
            try:
                event = self.status_queue.get_nowait()
            except queue.Empty:
                break
            else:
                self._handle_status_event(event, log_messages)

    def _handle_status_event(self, event, log_messages):
        if not log_messages:
            return

        if isinstance(event, dict):
            event_type = event.get("type", "status")
            message = event.get("message") or event_type.replace("_", " ").title()

            # Update debug info labels
            if event_type == "resolution_detected":
                resolution = event.get("resolution")
                scale_x = event.get("scale_x")
                scale_y = event.get("scale_y")
                border_offset = event.get("border_offset", (0, 0))

                # Store for overlay window
                self.current_resolution = resolution
                self.current_scale_x = scale_x if scale_x is not None else 1.0
                self.current_scale_y = scale_y if scale_y is not None else 1.0
                self.current_border_offset = border_offset

                # Update overlay window if it exists
                if self.overlay_window:
                    self.overlay_window.set_resolution_info(
                        resolution or "Unknown",
                        self.current_scale_x,
                        self.current_scale_y,
                        border_offset
                    )

                if resolution:
                    self.debug_resolution_label.setText(resolution)
                if scale_x is not None and scale_y is not None:
                    self.debug_scale_label.setText(f"{scale_x:.2f}x, {scale_y:.2f}x")

            if event_type == "detection":
                template_name = event.get("template")
                confidence = event.get("confidence")
                if template_name:
                    display_text = template_name
                    if confidence is not None and bool(self.show_confidence.value):
                        display_text += f" ({confidence:.2f})"
                    self.debug_last_detection_label.setText(display_text)

            if event_type == "click":
                x = event.get("x")
                y = event.get("y")
                if x is not None and y is not None:
                    self.debug_last_click_label.setText(f"({x}, {y})")

            # Handle overlay click visualization
            if event_type == "overlay_click":
                if self.overlay_window:
                    x = event.get("x")
                    y = event.get("y")
                    label = event.get("label", "Click")
                    color = event.get("color", (255, 255, 0))  # Default yellow
                    if x is not None and y is not None:
                        self.overlay_window.add_click(x, y, label, color)

            # Handle overlay click clearing
            if event_type == "overlay_clear_clicks":
                if self.overlay_window:
                    self.overlay_window.clear_clicks()

            # Handle detection overlay updates
            if event_type == "detection_overlay":
                if self.overlay_window and self.show_overlay_button.isChecked():
                    import numpy as np
                    # Decode the image data
                    image_bytes = event.get("image")
                    zones = event.get("zones", {})
                    if image_bytes:
                        # Convert bytes back to numpy array
                        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
                        width = event.get("width", 0)
                        height = event.get("height", 0)
                        if width and height:
                            image_array = image_array.reshape((height, width, 3))
                            self.overlay_window.update_detection_data(image_array, zones)

            loot_count = event.get("loot_count")
            legendary_count = event.get("legendary_count")
            screenshot_path = event.get("screenshot")
            info_path = event.get("info_file")

            log_parts = [message]

            if loot_count is not None:
                loot_count = int(loot_count)
                self.loot_value_label.setText(str(loot_count))
                log_parts.append(f"loot={loot_count}")

            if legendary_count is not None:
                legendary_count = int(legendary_count)
                self.legendary_value_label.setText(str(legendary_count))
                log_parts.append(f"legendaries={legendary_count}")

            if event_type == "legendary":
                if screenshot_path:
                    log_parts.append(f"image={screenshot_path}")
                if info_path:
                    log_parts.append(f"info={info_path}")

            extras = " | ".join(log_parts[1:]) if len(log_parts) > 1 else ""

            # Skip logging for certain debug events based on flags
            should_log = True
            if event_type == "detection":
                # Only log detection events if show_confidence is enabled
                should_log = bool(self.show_confidence.value)
            elif event_type == "click":
                # Only log click events if show_coords is enabled
                should_log = bool(self.show_coords.value)

            if should_log:
                if event_type == "error":
                    log_entry = f"[ERROR] {message}"
                    level = "error"
                elif event_type == "legendary":
                    log_entry = f"[LEGENDARY] {message}"
                    if extras:
                        log_entry += f" | {extras}"
                    level = "legendary"
                else:
                    log_entry = " | ".join(filter(None, [message, extras]))
                    level = "info"

                self._append_log(log_entry)
        else:
            text = str(event)
            self._append_log(text)

    def _append_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"> [{timestamp}] {message}")
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _stop_bot_process(self, manual=False):
        running = self._bot_is_running()
        if not running:
            if manual:
                self._append_log("Bot is not running.")
            return

        # Accumulate elapsed time before stopping
        if self._bot_start_time is not None:
            elapsed = (datetime.now() - self._bot_start_time).total_seconds()
            self._accumulated_time += elapsed
            self._bot_start_time = None

        if self.process:
            self.process.terminate()
            self.process.join(timeout=2.0)
            # Force kill if process didn't terminate gracefully
            if self.process.is_alive():
                self._append_log("Process didn't stop gracefully, force killing...")
                self.process.kill()
                self.process.join(timeout=1.0)
            self.process = None

        with self.started_flag.get_lock():
            self.started_flag.value = False
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        speak_async("Bot Stopped")
        note = "Bot stopped." if manual else "Bot process ended."
        self._append_log(note)

        # Reset overlay zones to default positions
        if self.overlay_window:
            self.overlay_window.reset_offsets()

        self._drain_status_queue()
        self._update_status_labels()

    def _bot_is_running(self):
        return bool(self.started_flag.value) or (
            self.process is not None and self.process.is_alive()
        )

    def closeEvent(self, event):
        """Handle window close event - ask user if they want to minimize to tray or exit"""
        # If force close flag is set, exit without asking
        if self._force_close:
            self.status_timer.stop()
            # Stop animated GIFs
            if hasattr(self, 'movie') and self.movie:
                self.movie.stop()
            if hasattr(self, 'chest_movie') and self.chest_movie:
                self.chest_movie.stop()
            # Hide tray icon
            if hasattr(self, 'tray_icon'):
                self.tray_icon.hide()
            try:
                self._stop_bot_process(manual=False)
                try:
                    self.status_queue.close()
                    self.status_queue.join_thread()
                except Exception:
                    pass
            finally:
                event.accept()
            return

        # Ask user if they want to minimize to tray or exit
        if hasattr(self, 'tray_icon') and QSystemTrayIcon.isSystemTrayAvailable():
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("TLOPO Looter")
            msg_box.setText("What would you like to do?")
            msg_box.setIcon(QMessageBox.Question)

            minimize_btn = msg_box.addButton("Minimize to Tray", QMessageBox.ActionRole)
            exit_btn = msg_box.addButton("Exit Application", QMessageBox.DestructiveRole)
            cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole)

            msg_box.exec_()

            clicked_button = msg_box.clickedButton()

            if clicked_button == minimize_btn:
                # Minimize to tray
                event.ignore()
                self._minimize_to_tray()
            elif clicked_button == exit_btn:
                # Exit application
                self._force_close = True
                self.close()
            else:
                # Cancel - do nothing
                event.ignore()
        else:
            # No tray icon available, just close normally
            self._force_close = True
            self.close()

    def changeEvent(self, event):
        """Handle window state changes (minimize)"""
        if event.type() == QtCore.QEvent.WindowStateChange:
            if self.isMinimized():
                # Ask user if they want to minimize to tray
                if hasattr(self, 'tray_icon') and QSystemTrayIcon.isSystemTrayAvailable():
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("TLOPO Looter")
                    msg_box.setText("Minimize to system tray?")
                    msg_box.setIcon(QMessageBox.Question)

                    tray_btn = msg_box.addButton("Minimize to Tray", QMessageBox.YesRole)
                    taskbar_btn = msg_box.addButton("Keep in Taskbar", QMessageBox.NoRole)

                    msg_box.exec_()

                    if msg_box.clickedButton() == tray_btn:
                        event.ignore()
                        self._minimize_to_tray()
                        return

        super().changeEvent(event)


def _build_shared_state():
    return {
        "started": multiprocessing.Value("i", False),
        "gui_settings_opened": multiprocessing.Value("i", False),
        "attack_delay": multiprocessing.Value("d", 0.1),
        "wait_after_enemy_spawn": multiprocessing.Value("d", 5.5),
        "loot_opened": multiprocessing.Value("i", 0),
        "legendaries": multiprocessing.Value("i", 0),
        "screenshot_enabled": multiprocessing.Value("i", True),  # Default: enabled
        # Template matching thresholds (0.0 to 1.0)
        "threshold_open_loot": multiprocessing.Value("d", 0.40),
        "threshold_loot_window": multiprocessing.Value("d", 0.35),
        "threshold_hp_full": multiprocessing.Value("d", 0.85),
        "threshold_hp_damaged": multiprocessing.Value("d", 0.95),
        "threshold_hp_empty": multiprocessing.Value("d", 0.90),
        # Debug options
        "debug_mode": multiprocessing.Value("i", False),  # Save detection screenshots
        "show_coords": multiprocessing.Value("i", False),  # Log click coordinates
        "show_confidence": multiprocessing.Value("i", False),  # Log confidence scores
        # Debug capture selection (which detections to save)
        "debug_capture_open_loot": multiprocessing.Value("i", True),
        "debug_capture_loot_window": multiprocessing.Value("i", True),
        "debug_capture_hp_full": multiprocessing.Value("i", False),
        "debug_capture_hp_damaged": multiprocessing.Value("i", False),
        "debug_capture_hp_empty": multiprocessing.Value("i", False),
        # Manual capture trigger (button press)
        "manual_capture_trigger": multiprocessing.Value("i", 0),  # Increments each button press
        # Detection overlay
        "overlay_enabled": multiprocessing.Value("i", False),  # Whether to send overlay data
    }


if __name__ == "__main__":
    multiprocessing.freeze_support()
    shared_state = _build_shared_state()
    app = QtWidgets.QApplication(sys.argv)
    window = BotWindow(shared_state)
    window.show()
    sys.exit(app.exec_())
