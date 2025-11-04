import ctypes
import multiprocessing
import queue
import sys
import threading
from datetime import datetime

import cv2
import numpy as np

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

_shared_manager = None


def _get_shared_manager():
    """Lazy-create a single multiprocessing.Manager instance for shared overlay state."""
    global _shared_manager
    if _shared_manager is None:
        _shared_manager = multiprocessing.Manager()
    return _shared_manager


class DetectionOverlayWindow(QtWidgets.QWidget):
    """
    Debug overlay window that visualizes detection zones and allows manual adjustment.
    """

    def __init__(self, parent=None, log_callback=None, update_callback=None):
        super().__init__(parent)
        self.setWindowTitle("TLOPO Looter - Detection Overlay")
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        self.setMouseTracking(True)

        self.log_callback = log_callback
        self.update_callback = update_callback

        self.info_label = QtWidgets.QLabel("Drag zones | P: save | R: reset | C: clear clicks")
        self.info_label.setAlignment(QtCore.Qt.AlignCenter)
        self.info_label.setStyleSheet("background-color: #222222; color: #00FF00; padding: 5px; font-weight: bold;")

        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.image_label.setStyleSheet("background-color: #000000;")
        self.image_label.setMouseTracking(True)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.info_label)
        layout.addWidget(self.image_label)
        self.setLayout(layout)

        # Stored state
        self.base_image = None  # QtGui.QImage
        self.current_pixmap = None
        self.detection_zones = {}  # zone_name -> dict
        self.zone_offsets = {}  # zone_name -> {'dx': int, 'dy': int}
        self.click_positions = []  # list of dicts with x, y, label, color

        # Interaction tracking
        self.dragging_zone = None
        self.drag_start_pos = None
        self.drag_start_zone_pos = None
        self.drag_start_zone_data = None  # Immutable snapshot of zone data at drag start

        # Interaction mode and resize tracking
        self.interaction_mode = "move"  # "move" or "resize"
        self.zone_size_changes = {}  # zone_name -> {'dw': int, 'dh': int}
        self.zone_min_sizes = {}  # zone_name -> {'w': int, 'h': int}
        self.resizing_zone = None
        self.resize_start_pos = None
        self.resize_start_size = None
        self.resize_start_offset = None  # Store starting offset for left/top edge resizing
        self.resize_start_zone_data = None  # Immutable snapshot of zone data at resize start
        self.resize_type = None  # "corner", "right", "bottom", or None

        # Resize constraints
        self.MIN_ZONE_WIDTH = 2
        self.MIN_ZONE_HEIGHT = 2
        self.RESIZE_EDGE_MARGIN = 8  # pixels from edge to trigger edge resize
        self.RESIZE_CORNER_SIZE = 16  # corner region size (takes priority)

        # Metadata
        self.resolution = "Unknown"
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.border_offset = (0, 0)

        # Persistent zone storage (for restoring custom zones across updates)
        self.overlay_last_regions = None

        # Initialize mode label
        self._update_mode_label()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_resolution_info(self, resolution, scale_x, scale_y, border_offset):
        self.resolution = resolution or "Unknown"
        self.scale_x = float(scale_x)
        self.scale_y = float(scale_y)
        self.border_offset = tuple(border_offset) if border_offset else (0, 0)

    def update_detection_data(self, image_bytes, width, height, zones):
        if not image_bytes or width <= 0 or height <= 0:
            return

        try:
            bytes_per_line = width * 3
            qimage = QtGui.QImage(image_bytes, width, height, bytes_per_line, QtGui.QImage.Format_BGR888)
            self.base_image = qimage.copy()

            # Expand/refresh detection zones dictionary
            new_zones = {}
            min_sizes = {}
            for zone in zones or []:
                name = zone.get("name")
                if not name:
                    continue
                new_zones[name] = {
                    "x": int(zone.get("x", 0)),
                    "y": int(zone.get("y", 0)),
                    "w": int(zone.get("w", 0)),
                    "h": int(zone.get("h", 0)),
                    "detected": bool(zone.get("detected", False)),
                }
                min_w = int(zone.get("min_w", new_zones[name]["w"]))
                min_h = int(zone.get("min_h", new_zones[name]["h"]))
                min_sizes[name] = {
                    "w": max(self.MIN_ZONE_WIDTH, min_w),
                    "h": max(self.MIN_ZONE_HEIGHT, min_h),
                }

                # Skip updating offsets/sizes for zones currently being manipulated
                # This prevents incoming data from interfering with user drag/resize operations
                if name == self.dragging_zone or name == self.resizing_zone:
                    # Keep existing offsets and sizes, don't reset them
                    self.zone_offsets.setdefault(name, {"dx": 0, "dy": 0})
                    self.zone_size_changes.setdefault(name, {"dw": 0, "dh": 0})
                    continue

                need_offsets = name not in self.zone_offsets
                need_sizes = name not in self.zone_size_changes
                desired = None

                if (need_offsets or need_sizes) and self.overlay_last_regions:
                    desired = self.overlay_last_regions.get(name)

                if need_offsets or need_sizes:
                    if desired:
                        dx = int(desired.get("x", new_zones[name]["x"])) - new_zones[name]["x"]
                        dy = int(desired.get("y", new_zones[name]["y"])) - new_zones[name]["y"]
                        dw = int(desired.get("w", new_zones[name]["w"])) - new_zones[name]["w"]
                        dh = int(desired.get("h", new_zones[name]["h"])) - new_zones[name]["h"]
                        self.zone_offsets[name] = {"dx": dx, "dy": dy}
                        self.zone_size_changes[name] = {"dw": dw, "dh": dh}
                    else:
                        self.zone_offsets.setdefault(name, {"dx": 0, "dy": 0})
                        self.zone_size_changes.setdefault(name, {"dw": 0, "dh": 0})
                else:
                    self.zone_offsets.setdefault(name, {"dx": 0, "dy": 0})
                    self.zone_size_changes.setdefault(name, {"dw": 0, "dh": 0})

            self.detection_zones = new_zones
            self.zone_min_sizes = min_sizes

            # Remove stale offsets for zones no longer present
            # BUT: Don't remove offsets for zones currently being dragged/resized
            for name in list(self.zone_offsets.keys()):
                if name not in self.detection_zones:
                    # Protect zones being actively manipulated
                    if name == self.dragging_zone or name == self.resizing_zone:
                        continue  # Keep offsets for zone being interacted with
                    self.zone_offsets.pop(name, None)
                    self.zone_size_changes.pop(name, None)

            # Resize label to match raw image size for accurate dragging
            self.image_label.setFixedSize(width, height)
            self._render_overlay()

        except Exception as e:
            # Prevent overlay crashes from taking down the entire app
            if self.log_callback:
                self.log_callback(f"Overlay update error: {e}")
            # Keep the overlay functional even if one update fails
            pass

    def add_click(self, x, y, label="Click", color=(255, 255, 0)):
        if x is None or y is None:
            return
        try:
            cx = int(x)
            cy = int(y)
        except Exception:
            return

        if isinstance(color, (list, tuple)) and len(color) >= 3:
            color_value = tuple(int(c) for c in color[:3])
        else:
            color_value = (255, 255, 0)

        self.click_positions.append({
            "x": cx,
            "y": cy,
            "label": label,
            "color": color_value,
        })
        if len(self.click_positions) > 100:
            self.click_positions = self.click_positions[-100:]
        self._render_overlay()

    def clear_clicks(self):
        self.click_positions.clear()
        if self.log_callback:
            self.log_callback("Cleared overlay click markers.")
        self._render_overlay()

    def reset_offsets(self):
        self.zone_offsets = {name: {"dx": 0, "dy": 0} for name in self.detection_zones}
        self.zone_size_changes = {name: {"dw": 0, "dh": 0} for name in self.detection_zones}
        if self.log_callback:
            self.log_callback("Overlay zones reset to default positions and sizes.")
        self._render_overlay()
        self._emit_zone_update()

    def get_adjusted_regions(self):
        if not self.detection_zones:
            return None
        adjusted = {}
        for name, zone in self.detection_zones.items():
            offset = self.zone_offsets.get(name, {"dx": 0, "dy": 0})
            size_change = self.zone_size_changes.get(name, {"dw": 0, "dh": 0})
            min_w, min_h = self._get_zone_min_size(name)
            adjusted[name] = {
                "x": zone["x"] + offset["dx"],
                "y": zone["y"] + offset["dy"],
                "w": max(min_w, zone["w"] + size_change["dw"]),
                "h": max(min_h, zone["h"] + size_change["dh"]),
            }
        return adjusted

    def _emit_zone_update(self):
        if self.update_callback:
            try:
                adjusted = self.get_adjusted_regions()
                # Store adjusted regions to enable restoration if bot sends stale data
                # during the async update propagation delay (~15-50ms)
                # This prevents zones from resetting to base position during the update window
                if adjusted:
                    self.overlay_last_regions = {
                        name: dict(values) for name, values in adjusted.items()
                    }
                self.update_callback(adjusted)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Internal rendering helpers
    # ------------------------------------------------------------------
    def _render_overlay(self):
        if self.base_image is None:
            return

        pixmap = QtGui.QPixmap.fromImage(self.base_image)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)

        for zone_name, zone_data in self.detection_zones.items():
            offset = self.zone_offsets.get(zone_name, {"dx": 0, "dy": 0})
            size_change = self.zone_size_changes.get(zone_name, {"dw": 0, "dh": 0})

            x = zone_data["x"] + offset["dx"]
            y = zone_data["y"] + offset["dy"]
            w = zone_data["w"] + size_change["dw"]
            h = zone_data["h"] + size_change["dh"]
            detected = zone_data["detected"]

            # Draw rectangle
            pen = QtGui.QPen(QtGui.QColor(0, 255, 0) if detected else QtGui.QColor(255, 0, 0))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(x, y, w, h)

            # Draw resize indicator in resize mode
            if self.interaction_mode == "resize":
                # Draw small corner handle indicator
                handle_size = 6
                painter.fillRect(
                    x + w - handle_size,
                    y + h - handle_size,
                    handle_size,
                    handle_size,
                    QtGui.QColor(255, 165, 0)  # Orange
                )

            # Draw label with size info
            text_bg = QtGui.QColor(0, 0, 0, 160)
            label_text = f"{zone_name} [{w}x{h}]"
            label_width = int(painter.fontMetrics().horizontalAdvance(label_text) + 6)
            painter.fillRect(x, y - 18, label_width, 18, text_bg)
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
            painter.drawText(x + 3, y - 4, label_text)

        for click in self.click_positions:
            cx = click["x"]
            cy = click["y"]
            color = click.get("color", (255, 255, 0))
            label = click.get("label", "Click")

            pen = QtGui.QPen(QtGui.QColor(*color))
            pen.setWidth(2)
            painter.setPen(pen)
            brush = QtGui.QBrush(QtGui.QColor(color[0], color[1], color[2], 80))
            painter.setBrush(brush)
            painter.drawEllipse(QtCore.QPoint(cx, cy), 6, 6)
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
            painter.drawText(cx + 8, cy + 4, label)

        painter.end()

        self.current_pixmap = pixmap
        self.image_label.setPixmap(pixmap)

    def _update_mode_label(self):
        """Update info label to show current mode"""
        mode_text = "MOVE" if self.interaction_mode == "move" else "RESIZE"
        color = "#00FF00" if self.interaction_mode == "move" else "#FFA500"
        self.info_label.setText(
            f"Mode: <span style='color: {color}; font-weight: bold;'>{mode_text}</span> | "
            f"Right-click: change mode | P: save | R: reset | C: clear clicks"
        )

    def _get_zone_min_size(self, zone_name):
        minima = self.zone_min_sizes.get(zone_name) or {}
        min_w = max(self.MIN_ZONE_WIDTH, int(minima.get("w", self.MIN_ZONE_WIDTH)))
        min_h = max(self.MIN_ZONE_HEIGHT, int(minima.get("h", self.MIN_ZONE_HEIGHT)))
        return min_w, min_h

    def _detect_resize_region(self, click_x, click_y, zone_x, zone_y, zone_w, zone_h):
        """
        Determines which resize region was clicked.

        Args:
            click_x, click_y: Mouse click position
            zone_x, zone_y, zone_w, zone_h: Zone boundaries

        Returns:
            "top_left", "top_right", "bottom_left", "bottom_right" - Corner resize
            "left", "right", "top", "bottom" - Edge resize
            None - Interior or outside (no resize)
        """
        # Calculate distances from all 4 edges
        dist_from_left = abs(click_x - zone_x)
        dist_from_right = abs(click_x - (zone_x + zone_w))
        dist_from_top = abs(click_y - zone_y)
        dist_from_bottom = abs(click_y - (zone_y + zone_h))

        # Check all 4 corners first (highest priority, larger hit area)
        if dist_from_left <= self.RESIZE_CORNER_SIZE and dist_from_top <= self.RESIZE_CORNER_SIZE:
            return "top_left"
        if dist_from_right <= self.RESIZE_CORNER_SIZE and dist_from_top <= self.RESIZE_CORNER_SIZE:
            return "top_right"
        if dist_from_left <= self.RESIZE_CORNER_SIZE and dist_from_bottom <= self.RESIZE_CORNER_SIZE:
            return "bottom_left"
        if dist_from_right <= self.RESIZE_CORNER_SIZE and dist_from_bottom <= self.RESIZE_CORNER_SIZE:
            return "bottom_right"

        # Check all 4 edges (must be within bounds of zone perpendicular to edge)
        if dist_from_left <= self.RESIZE_EDGE_MARGIN and zone_y <= click_y <= zone_y + zone_h:
            return "left"
        if dist_from_right <= self.RESIZE_EDGE_MARGIN and zone_y <= click_y <= zone_y + zone_h:
            return "right"
        if dist_from_top <= self.RESIZE_EDGE_MARGIN and zone_x <= click_x <= zone_x + zone_w:
            return "top"
        if dist_from_bottom <= self.RESIZE_EDGE_MARGIN and zone_x <= click_x <= zone_x + zone_w:
            return "bottom"

        return None

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            click_x = event.pos().x()
            click_y = event.pos().y() - self.info_label.height()
            if 0 <= click_y <= self.image_label.height() and 0 <= click_x <= self.image_label.width():
                for zone_name, zone_data in self.detection_zones.items():
                    offset = self.zone_offsets.get(zone_name, {"dx": 0, "dy": 0})
                    size_change = self.zone_size_changes.get(zone_name, {"dw": 0, "dh": 0})
                    x = zone_data["x"] + offset["dx"]
                    y = zone_data["y"] + offset["dy"]
                    w = zone_data["w"] + size_change["dw"]
                    h = zone_data["h"] + size_change["dh"]

                    if x <= click_x <= x + w and y <= click_y <= y + h:
                        if self.interaction_mode == "move":
                            self.dragging_zone = zone_name
                            self.drag_start_pos = QtCore.QPoint(event.pos())
                            self.drag_start_zone_pos = QtCore.QPoint(x, y)
                            self.drag_start_zone_data = zone_data.copy()  # Snapshot zone data to prevent drift
                            self.setCursor(QtCore.Qt.ClosedHandCursor)
                        else:  # resize mode
                            # Detect which resize region was clicked
                            resize_region = self._detect_resize_region(click_x, click_y, x, y, w, h)
                            if resize_region:
                                self.resizing_zone = zone_name
                                self.resize_start_pos = QtCore.QPoint(event.pos())
                                self.resize_start_size = QtCore.QSize(w, h)
                                self.resize_start_offset = offset.copy()  # Store starting offset for left/top edge resizing
                                self.resize_start_zone_data = zone_data.copy()  # Snapshot zone data to prevent drift
                                self.resize_type = resize_region

                                # Set cursor based on resize type
                                cursor_map = {
                                    "top_left": QtCore.Qt.SizeFDiagCursor,
                                    "bottom_right": QtCore.Qt.SizeFDiagCursor,
                                    "top_right": QtCore.Qt.SizeBDiagCursor,
                                    "bottom_left": QtCore.Qt.SizeBDiagCursor,
                                    "left": QtCore.Qt.SizeHorCursor,
                                    "right": QtCore.Qt.SizeHorCursor,
                                    "top": QtCore.Qt.SizeVerCursor,
                                    "bottom": QtCore.Qt.SizeVerCursor,
                                }
                                self.setCursor(cursor_map.get(resize_region, QtCore.Qt.ArrowCursor))
                        break
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging_zone and self.drag_start_pos:
            # Move mode
            delta_x = event.pos().x() - self.drag_start_pos.x()
            delta_y = event.pos().y() - self.drag_start_pos.y()
            original = self.drag_start_zone_data  # Use snapshot instead of live data
            start_x = self.drag_start_zone_pos.x()
            start_y = self.drag_start_zone_pos.y()

            new_x = start_x + delta_x
            new_y = start_y + delta_y

            self.zone_offsets[self.dragging_zone]["dx"] = new_x - original["x"]
            self.zone_offsets[self.dragging_zone]["dy"] = new_y - original["y"]

            self._render_overlay()

        elif self.resizing_zone and self.resize_start_pos:
            # Resize mode
            delta_x = event.pos().x() - self.resize_start_pos.x()
            delta_y = event.pos().y() - self.resize_start_pos.y()

            original = self.resize_start_zone_data  # Use snapshot instead of live data
            start_w = self.resize_start_size.width()
            start_h = self.resize_start_size.height()
            start_offset = self.resize_start_offset
            min_w, min_h = self._get_zone_min_size(self.resizing_zone)

            # Calculate new dimensions and offsets based on resize type
            if self.resize_type == "bottom_right":
                # Bottom-right corner: resize width and height (right and bottom edges move)
                new_w = max(min_w, start_w + delta_x)
                new_h = max(min_h, start_h + delta_y)
                new_offset_dx = start_offset["dx"]
                new_offset_dy = start_offset["dy"]

            elif self.resize_type == "right":
                # Right edge: resize width only
                new_w = max(min_w, start_w + delta_x)
                new_h = start_h
                new_offset_dx = start_offset["dx"]
                new_offset_dy = start_offset["dy"]

            elif self.resize_type == "bottom":
                # Bottom edge: resize height only
                new_w = start_w
                new_h = max(min_h, start_h + delta_y)
                new_offset_dx = start_offset["dx"]
                new_offset_dy = start_offset["dy"]

            elif self.resize_type == "left":
                # Left edge: move left edge, keep right edge fixed
                new_w = max(min_w, start_w - delta_x)
                new_h = start_h
                new_offset_dx = start_offset["dx"] + start_w - new_w
                new_offset_dy = start_offset["dy"]

            elif self.resize_type == "top":
                # Top edge: move top edge, keep bottom edge fixed
                new_w = start_w
                new_h = max(min_h, start_h - delta_y)
                new_offset_dx = start_offset["dx"]
                new_offset_dy = start_offset["dy"] + start_h - new_h

            elif self.resize_type == "top_left":
                # Top-left corner: move top and left edges
                new_w = max(min_w, start_w - delta_x)
                new_h = max(min_h, start_h - delta_y)
                new_offset_dx = start_offset["dx"] + start_w - new_w
                new_offset_dy = start_offset["dy"] + start_h - new_h

            elif self.resize_type == "top_right":
                # Top-right corner: move top edge, resize width
                new_w = max(min_w, start_w + delta_x)
                new_h = max(min_h, start_h - delta_y)
                new_offset_dx = start_offset["dx"]
                new_offset_dy = start_offset["dy"] + start_h - new_h

            elif self.resize_type == "bottom_left":
                # Bottom-left corner: move left edge, resize height
                new_w = max(min_w, start_w - delta_x)
                new_h = max(min_h, start_h + delta_y)
                new_offset_dx = start_offset["dx"] + start_w - new_w
                new_offset_dy = start_offset["dy"]

            else:
                # Fallback (shouldn't happen)
                new_w = start_w
                new_h = start_h
                new_offset_dx = start_offset["dx"]
                new_offset_dy = start_offset["dy"]

            # Apply window bounds constraint
            zone_x = original["x"] + new_offset_dx
            zone_y = original["y"] + new_offset_dy

            # Ensure zone stays within image bounds
            if zone_x < 0:
                new_offset_dx -= zone_x
                zone_x = 0
            if zone_y < 0:
                new_offset_dy -= zone_y
                zone_y = 0

            max_w = self.image_label.width() - zone_x
            max_h = self.image_label.height() - zone_y
            new_w = max(min_w, min(new_w, max_w))
            new_h = max(min_h, min(new_h, max_h))

            if self.resize_type in ("left", "top_left", "bottom_left"):
                new_offset_dx = start_offset["dx"] + start_w - new_w
            if self.resize_type in ("top", "top_left", "top_right"):
                new_offset_dy = start_offset["dy"] + start_h - new_h

            # Store offset and size changes
            self.zone_offsets[self.resizing_zone]["dx"] = new_offset_dx
            self.zone_offsets[self.resizing_zone]["dy"] = new_offset_dy
            self.zone_size_changes[self.resizing_zone]["dw"] = new_w - original["w"]
            self.zone_size_changes[self.resizing_zone]["dh"] = new_h - original["h"]

            self._render_overlay()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self.dragging_zone:
                # Move mode release
                if self.log_callback:
                    offset = self.zone_offsets[self.dragging_zone]
                    self.log_callback(
                        f"{self.dragging_zone} moved: offset dx={offset['dx']}, dy={offset['dy']}"
                    )
                self._emit_zone_update()
                # Clear offsets - they're now baked into the base position sent to bot
                # This prevents feedback loop where old offsets get applied to new base
                self.zone_offsets[self.dragging_zone] = {"dx": 0, "dy": 0}
                self.dragging_zone = None
                self.drag_start_pos = None
                self.drag_start_zone_pos = None
                self.drag_start_zone_data = None  # Clear snapshot
                self.setCursor(QtCore.Qt.ArrowCursor)

            elif self.resizing_zone:
                # Resize mode release
                if self.log_callback:
                    size_change = self.zone_size_changes[self.resizing_zone]
                    zone = self.detection_zones[self.resizing_zone]
                    final_w = zone["w"] + size_change["dw"]
                    final_h = zone["h"] + size_change["dh"]
                    resize_type_text = f" [{self.resize_type}]" if self.resize_type else ""
                    self.log_callback(
                        f"{self.resizing_zone} resized{resize_type_text}: {zone['w']}x{zone['h']} -> {final_w}x{final_h} "
                        f"(dw={size_change['dw']}, dh={size_change['dh']})"
                    )
                self._emit_zone_update()
                # Clear size changes - they're now baked into the base size sent to bot
                # This prevents feedback loop where old size changes get applied to new base
                self.zone_size_changes[self.resizing_zone] = {"dw": 0, "dh": 0}
                # Also clear offsets in case resize affected position (left/top edges)
                self.zone_offsets[self.resizing_zone] = {"dx": 0, "dy": 0}
                self.resizing_zone = None
                self.resize_start_pos = None
                self.resize_start_size = None
                self.resize_start_zone_data = None  # Clear snapshot
                self.resize_type = None
                self.setCursor(QtCore.Qt.ArrowCursor)

        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leaving widget - cancel any active drag/resize"""
        # If mouse leaves the overlay window while dragging, stop the operation
        # This prevents "stuck" drags where release event isn't captured
        if self.dragging_zone or self.resizing_zone:
            if self.log_callback:
                self.log_callback("Mouse left overlay area - cancelling drag/resize operation")

            # Clear all drag/resize state
            self.dragging_zone = None
            self.drag_start_pos = None
            self.drag_start_zone_pos = None
            self.drag_start_zone_data = None  # Clear snapshot
            self.resizing_zone = None
            self.resize_start_pos = None
            self.resize_start_size = None
            self.resize_start_offset = None
            self.resize_start_zone_data = None  # Clear snapshot
            self.resize_type = None
            self.setCursor(QtCore.Qt.ArrowCursor)

        super().leaveEvent(event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_P:
            self._save_debug_file()
        elif event.key() == QtCore.Qt.Key_S:
            self._save_screenshot()
        elif event.key() == QtCore.Qt.Key_R:
            self.reset_offsets()
        elif event.key() == QtCore.Qt.Key_C:
            self.clear_clicks()
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Show context menu for mode selection"""
        click_x = event.pos().x()
        click_y = event.pos().y() - self.info_label.height()

        # Check if click is on a zone
        zone_under_cursor = None
        if 0 <= click_y <= self.image_label.height() and 0 <= click_x <= self.image_label.width():
            for zone_name, zone_data in self.detection_zones.items():
                offset = self.zone_offsets.get(zone_name, {"dx": 0, "dy": 0})
                size_change = self.zone_size_changes.get(zone_name, {"dw": 0, "dh": 0})
                x = zone_data["x"] + offset["dx"]
                y = zone_data["y"] + offset["dy"]
                w = zone_data["w"] + size_change["dw"]
                h = zone_data["h"] + size_change["dh"]

                if x <= click_x <= x + w and y <= click_y <= y + h:
                    zone_under_cursor = zone_name
                    break

        menu = QtWidgets.QMenu(self)

        # Mode selection
        move_label = "[*] Move Mode" if self.interaction_mode == "move" else "Move Mode"
        resize_label = "[*] Resize Mode" if self.interaction_mode == "resize" else "Resize Mode"
        move_action = menu.addAction(move_label)
        resize_action = menu.addAction(resize_label)

        if zone_under_cursor:
            menu.addSeparator()
            reset_zone_action = menu.addAction(f"Reset '{zone_under_cursor}'")
        else:
            reset_zone_action = None

        action = menu.exec_(event.globalPos())

        if action == move_action:
            self.interaction_mode = "move"
            self._update_mode_label()
            self._render_overlay()  # Re-render to hide resize handles
            if self.log_callback:
                self.log_callback("Switched to Move mode.")
        elif action == resize_action:
            self.interaction_mode = "resize"
            self._update_mode_label()
            self._render_overlay()  # Re-render to show resize handles
            if self.log_callback:
                self.log_callback("Switched to Resize mode.")
        elif action == reset_zone_action and zone_under_cursor:
            self.zone_offsets[zone_under_cursor] = {"dx": 0, "dy": 0}
            self.zone_size_changes[zone_under_cursor] = {"dw": 0, "dh": 0}
            if self.log_callback:
                self.log_callback(f"Reset {zone_under_cursor} to defaults.")
            self._render_overlay()
            self._emit_zone_update()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _save_debug_file(self):
        if not self.detection_zones:
            if self.log_callback:
                self.log_callback("No detection zone data available to save.")
            return

        from datetime import datetime
        import os

        safe_resolution = self.resolution.replace("x", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"overlay_debug_{safe_resolution}_{timestamp}.txt"
        debug_path = bot_logic.get_data_path(filename)

        lines = []
        lines.append("=" * 72)
        lines.append("TLOPO Looter - Overlay Debug Snapshot")
        lines.append(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
        lines.append("=" * 72)
        lines.append("")
        lines.append(f"Resolution: {self.resolution}")
        lines.append(f"Scale: X={self.scale_x:.4f}, Y={self.scale_y:.4f}")
        lines.append(f"Border Offset: {self.border_offset}")
        lines.append("")
        lines.append("Detection Zones:")
        lines.append("-" * 72)

        for name, zone in self.detection_zones.items():
            offset = self.zone_offsets.get(name, {"dx": 0, "dy": 0})
            size_change = self.zone_size_changes.get(name, {"dw": 0, "dh": 0})
            adjusted_w = zone['w'] + size_change['dw']
            adjusted_h = zone['h'] + size_change['dh']

            lines.extend([
                f"\n{name}:",
                f"  Base: x={zone['x']}, y={zone['y']}, w={zone['w']}, h={zone['h']}",
                f"  Offset: dx={offset['dx']}, dy={offset['dy']}",
                f"  Size Change: dw={size_change['dw']}, dh={size_change['dh']}",
                f"  Adjusted: x={zone['x'] + offset['dx']}, y={zone['y'] + offset['dy']}, "
                f"w={adjusted_w}, h={adjusted_h}",
                f"  Detected: {'YES' if zone['detected'] else 'NO'}",
            ])

        try:
            with open(debug_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            if self.log_callback:
                self.log_callback(f"Overlay debug saved to {debug_path}.")
        except Exception as exc:
            if self.log_callback:
                self.log_callback(f"Failed to save overlay debug file: {exc}")

    def _save_screenshot(self):
        """Save the current overlay view as a screenshot (press 's' key)"""
        if self.current_pixmap is None or self.current_pixmap.isNull():
            if self.log_callback:
                self.log_callback("No overlay frame available to save.")
            return

        from datetime import datetime

        safe_resolution = self.resolution.replace("x", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"overlay_screenshot_{safe_resolution}_{timestamp}.jpg"
        screenshot_path = bot_logic.get_data_path(filename)

        try:
            # Convert QPixmap -> QImage and ensure 24-bit BGR order for OpenCV
            qimage = self.current_pixmap.toImage().convertToFormat(QtGui.QImage.Format_BGR888)

            width = qimage.width()
            height = qimage.height()
            bytes_per_line = qimage.bytesPerLine()

            ptr = qimage.bits()
            ptr.setsize(bytes_per_line * height)

            # Convert QImage -> numpy array while respecting stride
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, bytes_per_line // 3, 3))
            if bytes_per_line != width * 3:
                arr = arr[:, :width, :]
            arr = np.ascontiguousarray(arr)

            # Save using OpenCV
            cv2.imwrite(screenshot_path, arr)

            if self.log_callback:
                self.log_callback(f"Screenshot saved to {screenshot_path}.")
        except Exception as exc:
            if self.log_callback:
                self.log_callback(f"Failed to save screenshot: {exc}")

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

        self.resolution_mode = shared_state["resolution_mode"]
        self.threshold_open_loot = shared_state["threshold_open_loot"]
        self.threshold_loot_window = shared_state["threshold_loot_window"]
        self.threshold_hp_full = shared_state["threshold_hp_full"]
        self.threshold_hp_damaged = shared_state["threshold_hp_damaged"]
        self.threshold_hp_empty = shared_state["threshold_hp_empty"]

        self.debug_mode = shared_state["debug_mode"]
        self.show_coords = shared_state["show_coords"]
        self.show_confidence = shared_state["show_confidence"]
        self.debug_capture_open_loot_flag = shared_state["debug_capture_open_loot"]
        self.debug_capture_loot_window_flag = shared_state["debug_capture_loot_window"]
        self.debug_capture_hp_full_flag = shared_state["debug_capture_hp_full"]
        self.debug_capture_hp_damaged_flag = shared_state["debug_capture_hp_damaged"]
        self.debug_capture_hp_empty_flag = shared_state["debug_capture_hp_empty"]
        self.manual_capture_trigger = shared_state["manual_capture_trigger"]
        self.overlay_enabled = shared_state["overlay_enabled"]
        self.disable_bot_actions = shared_state["disable_bot_actions"]
        self.use_overlay_zones_flag = shared_state["use_overlay_zones_flag"]
        self.overlay_zones_dict = shared_state["overlay_zones_dict"]

        self.overlay_window = None
        self.overlay_last_regions = None

        try:
            self.use_overlay_zones = bool(self.use_overlay_zones_flag.value)
        except Exception:
            self.use_overlay_zones = False

        try:
            initial_zones = dict(self.overlay_zones_dict)
        except Exception:
            initial_zones = None
        if initial_zones:
            normalized = self._normalize_overlay_regions(initial_zones)
            if normalized:
                self.overlay_last_regions = normalized
        else:
            self.overlay_last_regions = None

        self.current_resolution = "Unknown"
        self.current_scale_x = 1.0
        self.current_scale_y = 1.0
        self.current_border_offset = (0, 0)

        self.status_queue = multiprocessing.Queue()
        self.process = None
        self._bot_start_time = None
        self._accumulated_time = 0  # Total seconds accumulated across sessions
        self._syncing_controls = False
        self._last_started_state = bool(self.started_flag.value)
        self._force_close = False  # Flag to force exit without tray

        # Create session folder once per application run (not per Start/Stop)
        # Session persists until app is fully closed and reopened
        self._session_folder = datetime.now().strftime("Session_%d-%m-%Y_%H.%M.%S")

        self._init_window()
        self._build_ui()
        self._connect_signals()
        self._start_status_timer()
        self._apply_theme()
        self._finalize_size()
        self._setup_tray_icon()

        # Log session creation
        self._append_log(f"📁 Session folder created: {self._session_folder}")
        self._append_log("ℹ️ Session persists until app is closed (not affected by Start/Stop)")

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

        resolution_group = QtWidgets.QGroupBox("Resolution Strategy")
        resolution_layout = QtWidgets.QVBoxLayout()
        resolution_layout.setSpacing(8)

        resolution_info = QtWidgets.QLabel(
            "Choose whether the bot adapts to the current game resolution or forces 1280x800."
        )
        resolution_info.setWordWrap(True)
        self.resolution_mode_combo = QtWidgets.QComboBox()
        self.resolution_mode_combo.addItem(
            bot_logic.RESOLUTION_MODE_LABELS[bot_logic.RESOLUTION_MODE_ADAPTIVE],
            bot_logic.RESOLUTION_MODE_ADAPTIVE,
        )
        self.resolution_mode_combo.addItem(
            bot_logic.RESOLUTION_MODE_LABELS[bot_logic.RESOLUTION_MODE_FORCED],
            bot_logic.RESOLUTION_MODE_FORCED,
        )
        current_mode_index = self.resolution_mode_combo.findData(int(self.resolution_mode.value))
        if current_mode_index != -1:
            self.resolution_mode_combo.setCurrentIndex(current_mode_index)

        resolution_layout.addWidget(resolution_info)
        resolution_layout.addWidget(self.resolution_mode_combo)
        resolution_group.setLayout(resolution_layout)
        advanced_layout.addWidget(resolution_group)

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

        debug_page = QtWidgets.QWidget()
        debug_layout = QtWidgets.QVBoxLayout(debug_page)
        debug_layout.setContentsMargins(6, 6, 6, 6)
        debug_layout.setSpacing(8)

        debug_mode_group = QtWidgets.QGroupBox("Debug Options")
        debug_mode_layout = QtWidgets.QVBoxLayout()
        self.debug_mode_checkbox = QtWidgets.QCheckBox("Enable debug mode (save detection snapshots)")
        self.debug_mode_checkbox.setChecked(bool(self.debug_mode.value))
        debug_mode_layout.addWidget(self.debug_mode_checkbox)

        self.show_coords_checkbox = QtWidgets.QCheckBox("Log click coordinates to event log")
        self.show_coords_checkbox.setChecked(bool(self.show_coords.value))
        debug_mode_layout.addWidget(self.show_coords_checkbox)

        self.show_confidence_checkbox = QtWidgets.QCheckBox("Log template match confidence values")
        self.show_confidence_checkbox.setChecked(bool(self.show_confidence.value))
        debug_mode_layout.addWidget(self.show_confidence_checkbox)

        self.disable_bot_actions_checkbox = QtWidgets.QCheckBox("Disable bot actions (detection only mode)")
        self.disable_bot_actions_checkbox.setChecked(bool(self.disable_bot_actions.value))
        debug_mode_layout.addWidget(self.disable_bot_actions_checkbox)

        self.use_overlay_zones_checkbox = QtWidgets.QCheckBox("Use overlay detection zones")
        self.use_overlay_zones_checkbox.setChecked(self.use_overlay_zones)
        self.use_overlay_zones_checkbox.setToolTip(
            "When enabled, the bot will use detection zones adjusted in the overlay window."
        )
        debug_mode_layout.addWidget(self.use_overlay_zones_checkbox)

        debug_mode_group.setLayout(debug_mode_layout)
        debug_layout.addWidget(debug_mode_group)

        threshold_group = QtWidgets.QGroupBox("Template Thresholds")
        threshold_layout = QtWidgets.QGridLayout()

        self.threshold_open_loot_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_open_loot_spin.setDecimals(2)
        self.threshold_open_loot_spin.setRange(0.1, 1.0)
        self.threshold_open_loot_spin.setSingleStep(0.05)
        self.threshold_open_loot_spin.setValue(float(self.threshold_open_loot.value))

        self.threshold_loot_window_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_loot_window_spin.setDecimals(2)
        self.threshold_loot_window_spin.setRange(0.1, 1.0)
        self.threshold_loot_window_spin.setSingleStep(0.05)
        self.threshold_loot_window_spin.setValue(float(self.threshold_loot_window.value))

        self.threshold_hp_full_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_hp_full_spin.setDecimals(2)
        self.threshold_hp_full_spin.setRange(0.1, 1.0)
        self.threshold_hp_full_spin.setSingleStep(0.05)
        self.threshold_hp_full_spin.setValue(float(self.threshold_hp_full.value))

        self.threshold_hp_damaged_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_hp_damaged_spin.setDecimals(2)
        self.threshold_hp_damaged_spin.setRange(0.1, 1.0)
        self.threshold_hp_damaged_spin.setSingleStep(0.05)
        self.threshold_hp_damaged_spin.setValue(float(self.threshold_hp_damaged.value))

        self.threshold_hp_empty_spin = QtWidgets.QDoubleSpinBox()
        self.threshold_hp_empty_spin.setDecimals(2)
        self.threshold_hp_empty_spin.setRange(0.1, 1.0)
        self.threshold_hp_empty_spin.setSingleStep(0.05)
        self.threshold_hp_empty_spin.setValue(float(self.threshold_hp_empty.value))

        threshold_layout.addWidget(QtWidgets.QLabel("Open Loot"), 0, 0)
        threshold_layout.addWidget(self.threshold_open_loot_spin, 0, 1)
        threshold_layout.addWidget(QtWidgets.QLabel("Loot Window"), 1, 0)
        threshold_layout.addWidget(self.threshold_loot_window_spin, 1, 1)
        threshold_layout.addWidget(QtWidgets.QLabel("Enemy HP Full"), 2, 0)
        threshold_layout.addWidget(self.threshold_hp_full_spin, 2, 1)
        threshold_layout.addWidget(QtWidgets.QLabel("Enemy HP Damaged"), 3, 0)
        threshold_layout.addWidget(self.threshold_hp_damaged_spin, 3, 1)
        threshold_layout.addWidget(QtWidgets.QLabel("Enemy HP Empty"), 4, 0)
        threshold_layout.addWidget(self.threshold_hp_empty_spin, 4, 1)

        self.reset_thresholds_button = QtWidgets.QPushButton("Reset Thresholds")
        threshold_layout.addWidget(self.reset_thresholds_button, 5, 0, 1, 2)

        threshold_group.setLayout(threshold_layout)
        debug_layout.addWidget(threshold_group)

        capture_group = QtWidgets.QGroupBox("Debug Capture Filters")
        capture_layout = QtWidgets.QVBoxLayout()
        self.debug_capture_open_loot_checkbox = QtWidgets.QCheckBox("Capture open-loot prompt region")
        self.debug_capture_open_loot_checkbox.setChecked(bool(self.debug_capture_open_loot_flag.value))
        capture_layout.addWidget(self.debug_capture_open_loot_checkbox)

        self.debug_capture_loot_window_checkbox = QtWidgets.QCheckBox("Capture loot window contents")
        self.debug_capture_loot_window_checkbox.setChecked(bool(self.debug_capture_loot_window_flag.value))
        capture_layout.addWidget(self.debug_capture_loot_window_checkbox)

        self.debug_capture_hp_full_checkbox = QtWidgets.QCheckBox("Capture enemy HP (full)")
        self.debug_capture_hp_full_checkbox.setChecked(bool(self.debug_capture_hp_full_flag.value))
        capture_layout.addWidget(self.debug_capture_hp_full_checkbox)

        self.debug_capture_hp_damaged_checkbox = QtWidgets.QCheckBox("Capture enemy HP (damaged)")
        self.debug_capture_hp_damaged_checkbox.setChecked(bool(self.debug_capture_hp_damaged_flag.value))
        capture_layout.addWidget(self.debug_capture_hp_damaged_checkbox)

        self.debug_capture_hp_empty_checkbox = QtWidgets.QCheckBox("Capture enemy HP (empty)")
        self.debug_capture_hp_empty_checkbox.setChecked(bool(self.debug_capture_hp_empty_flag.value))
        capture_layout.addWidget(self.debug_capture_hp_empty_checkbox)

        capture_group.setLayout(capture_layout)
        debug_layout.addWidget(capture_group)

        control_row = QtWidgets.QHBoxLayout()
        self.manual_capture_button = QtWidgets.QPushButton("Manual Capture")
        self.manual_capture_button.setEnabled(bool(self.debug_mode.value))
        control_row.addWidget(self.manual_capture_button)
        self.overlay_checkbox = QtWidgets.QCheckBox("Show detection overlay window")
        self.overlay_checkbox.setChecked(bool(self.overlay_enabled.value))
        control_row.addWidget(self.overlay_checkbox)
        control_row.addStretch()
        debug_layout.addLayout(control_row)

        debug_layout.addStretch()
        self.tab_widget.addTab(debug_page, "Debug")

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
                    <li>Right-click the game shortcut -> Properties</li>
                    <li>Compatibility tab -> "Change high DPI settings"</li>
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
        self.resolution_mode_combo.currentIndexChanged.connect(self._handle_resolution_mode_changed)

        self.threshold_open_loot_spin.valueChanged.connect(self._handle_threshold_open_loot_changed)
        self.threshold_loot_window_spin.valueChanged.connect(self._handle_threshold_loot_window_changed)
        self.threshold_hp_full_spin.valueChanged.connect(self._handle_threshold_hp_full_changed)
        self.threshold_hp_damaged_spin.valueChanged.connect(self._handle_threshold_hp_damaged_changed)
        self.threshold_hp_empty_spin.valueChanged.connect(self._handle_threshold_hp_empty_changed)
        self.reset_thresholds_button.clicked.connect(self._handle_reset_thresholds)

        self.debug_mode_checkbox.stateChanged.connect(self._handle_debug_mode_toggled)
        self.show_coords_checkbox.stateChanged.connect(self._handle_show_coords_toggled)
        self.show_confidence_checkbox.stateChanged.connect(self._handle_show_confidence_toggled)

        self.debug_capture_open_loot_checkbox.stateChanged.connect(
            lambda state: self._handle_debug_capture_toggled(self.debug_capture_open_loot_flag, state)
        )
        self.debug_capture_loot_window_checkbox.stateChanged.connect(
            lambda state: self._handle_debug_capture_toggled(self.debug_capture_loot_window_flag, state)
        )
        self.debug_capture_hp_full_checkbox.stateChanged.connect(
            lambda state: self._handle_debug_capture_toggled(self.debug_capture_hp_full_flag, state)
        )
        self.debug_capture_hp_damaged_checkbox.stateChanged.connect(
            lambda state: self._handle_debug_capture_toggled(self.debug_capture_hp_damaged_flag, state)
        )
        self.debug_capture_hp_empty_checkbox.stateChanged.connect(
            lambda state: self._handle_debug_capture_toggled(self.debug_capture_hp_empty_flag, state)
        )

        self.disable_bot_actions_checkbox.stateChanged.connect(self._handle_disable_bot_actions_toggled)
        self.use_overlay_zones_checkbox.stateChanged.connect(self._handle_use_overlay_zones_toggled)

        self.manual_capture_button.clicked.connect(self._handle_manual_capture)
        self.overlay_checkbox.stateChanged.connect(self._handle_overlay_toggled)

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
            mode = int(self.resolution_mode.value)
            # Check if running as frozen exe (PyInstaller)
            if getattr(sys, 'frozen', False):
                # Running as compiled exe - run validation directly (no subprocess)
                # Frozen exe doesn't support -c flag, would cause GUI to open again
                success, msg, details = bot_logic.validate_game_ready(mode)

                self._apply_validation_details(details)

                if success:
                    return (True, "Validation passed")
                else:
                    return (False, msg)
            else:
                # Running as Python script - use subprocess to avoid PyQt5 event loop interference
                # PyQt5's event loop causes window resize to fail
                import subprocess

                # Run validation script directly
                # Use special prefix for DPI issues so GUI can handle them differently
                result = subprocess.run(
                    [sys.executable, "-c",
                     f"import bot_logic; success, msg, details = bot_logic.validate_game_ready({mode}); "
                     "prefix = 'DPI_ERROR:' if not success and 'DPI Override Configuration Issue' in msg else 'FAIL:'; "
                     "print('SUCCESS' if success else f'{prefix}{msg}')"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                # Get output (handle multiline messages)
                output = result.stdout.strip()

                if output == 'SUCCESS':
                    return (True, "Validation passed")
                elif output.startswith('DPI_ERROR:'):
                    # DPI error - return with special marker (may be multiline)
                    return (False, output[10:])  # Remove 'DPI_ERROR:' prefix
                elif output.startswith('FAIL:'):
                    # Get last line only for regular errors (ignore debug output)
                    lines = output.split('\n')
                    last_line = lines[-1] if lines else ''
                    return (False, last_line[5:] if last_line.startswith('FAIL:') else output[5:])
                else:
                    return (False, f"Validation error: {output if output else 'No output'}")

        except Exception as e:
            return (False, f"Validation error: {e}")

    def _show_validation_error(self, error_message):
        """Show error dialog and switch to Help tab. Handles DPI fix automatically."""

        # Check if this is a DPI configuration issue that can be auto-fixed
        if "DPI Override Configuration Issue" in error_message:
            # Show Yes/No dialog for auto-fix
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("DPI Configuration Required")
            msg_box.setText(error_message)
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)

            response = msg_box.exec_()

            if response == QMessageBox.Yes:
                # User wants to apply fix - use centralized workflow
                self._append_log("Applying DPI override fix...")

                try:
                    handle = bot_logic.check_window()
                    if handle:
                        # Use centralized DPI configuration handler
                        result = bot_logic.handle_dpi_configuration(handle)

                        if result['action'] == 'fixed':
                            # Success - show restart instruction
                            success_box = QMessageBox(self)
                            success_box.setIcon(QMessageBox.Information)
                            success_box.setWindowTitle("DPI Override Applied")
                            success_box.setText("✅ DPI override has been set to 'System'")
                            success_box.setInformativeText(
                                "IMPORTANT: You must RESTART the game for changes to take effect.\n\n"
                                "Steps:\n"
                                "1. Close the game completely\n"
                                "2. Restart the game\n"
                                "3. Click Start in the bot again"
                            )
                            success_box.setStandardButtons(QMessageBox.Ok)
                            success_box.exec_()

                            self._append_log(f"✅ {result['message']}")
                            self._append_log("⚠️ Please restart the game for changes to take effect.")
                        elif result['action'] == 'already_correct':
                            # Already configured correctly
                            self._append_log(f"✅ {result['message']}")
                        else:
                            # Failed to apply fix
                            fail_box = QMessageBox(self)
                            fail_box.setIcon(QMessageBox.Critical)
                            fail_box.setWindowTitle("Failed to Apply Fix")
                            fail_box.setText(f"❌ {result['message']}")
                            fail_box.setInformativeText("Please apply the fix manually. Check the Help tab for instructions.")
                            fail_box.setStandardButtons(QMessageBox.Ok)
                            fail_box.exec_()

                            self._append_log(f"❌ {result['message']}")
                            self.tab_widget.setCurrentIndex(2)  # Switch to Help tab
                    else:
                        self._append_log("❌ Could not find game window")
                        self.tab_widget.setCurrentIndex(2)
                except Exception as e:
                    self._append_log(f"❌ Error applying DPI fix: {e}")
                    self.tab_widget.setCurrentIndex(2)
            else:
                # User declined fix - show manual instructions
                self._append_log("DPI fix declined. Please configure manually.")
                self.tab_widget.setCurrentIndex(2)  # Switch to Help tab
        else:
            # Regular validation error - show normal error dialog
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
            use_overlay_zones = self.use_overlay_zones_checkbox.isChecked()
            if use_overlay_zones:
                regions_to_share = self._collect_overlay_regions()
                if regions_to_share:
                    self._update_shared_overlay_zones(regions_to_share, force=True)
                else:
                    self._append_log("Overlay zones requested but not available; using defaults.")
                    use_overlay_zones = False

            try:
                with self.use_overlay_zones_flag.get_lock():
                    self.use_overlay_zones_flag.value = 1 if use_overlay_zones else 0
            except Exception:
                pass

            self.gui_settings_opened.value = False
            self._drain_status_queue(log_messages=False)
            if use_overlay_zones:
                self._append_log("Overlay detection zones will be used for this run.")
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
                    self.resolution_mode,
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
                    self.disable_bot_actions,
                    self.use_overlay_zones_flag,
                    self.overlay_zones_dict,
                    self._session_folder,  # Pass persistent session folder
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
        base_folder = bot_logic.get_data_path(bot_logic.SCREENSHOT_BASE_PATH)

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

    def _handle_resolution_mode_changed(self, index):
        mode = self.resolution_mode_combo.itemData(index)
        if mode is None:
            return
        with self.resolution_mode.get_lock():
            self.resolution_mode.value = int(mode)
        self._append_log(f"Resolution mode set to {self.resolution_mode_combo.currentText()}.")

    def _handle_threshold_open_loot_changed(self, value):
        with self.threshold_open_loot.get_lock():
            self.threshold_open_loot.value = float(value)
        if self.threshold_open_loot_spin.hasFocus():
            self._append_log(f"Open loot threshold set to {value:.2f}.")

    def _handle_threshold_loot_window_changed(self, value):
        with self.threshold_loot_window.get_lock():
            self.threshold_loot_window.value = float(value)
        if self.threshold_loot_window_spin.hasFocus():
            self._append_log(f"Loot window threshold set to {value:.2f}.")

    def _handle_threshold_hp_full_changed(self, value):
        with self.threshold_hp_full.get_lock():
            self.threshold_hp_full.value = float(value)
        if self.threshold_hp_full_spin.hasFocus():
            self._append_log(f"Enemy HP full threshold set to {value:.2f}.")

    def _handle_threshold_hp_damaged_changed(self, value):
        with self.threshold_hp_damaged.get_lock():
            self.threshold_hp_damaged.value = float(value)
        if self.threshold_hp_damaged_spin.hasFocus():
            self._append_log(f"Enemy HP damaged threshold set to {value:.2f}.")

    def _handle_threshold_hp_empty_changed(self, value):
        with self.threshold_hp_empty.get_lock():
            self.threshold_hp_empty.value = float(value)
        if self.threshold_hp_empty_spin.hasFocus():
            self._append_log(f"Enemy HP empty threshold set to {value:.2f}.")

    def _handle_reset_thresholds(self):
        defaults = {
            "open": bot_logic.THRESHOLD_OPEN_LOOT,
            "loot": bot_logic.THRESHOLD_LOOT_WINDOW,
            "hp_full": bot_logic.THRESHOLD_HP_FULL,
            "hp_damaged": bot_logic.THRESHOLD_HP_DAMAGED,
            "hp_empty": bot_logic.THRESHOLD_HP_EMPTY,
        }
        with self.threshold_open_loot.get_lock():
            self.threshold_open_loot.value = defaults["open"]
        with self.threshold_loot_window.get_lock():
            self.threshold_loot_window.value = defaults["loot"]
        with self.threshold_hp_full.get_lock():
            self.threshold_hp_full.value = defaults["hp_full"]
        with self.threshold_hp_damaged.get_lock():
            self.threshold_hp_damaged.value = defaults["hp_damaged"]
        with self.threshold_hp_empty.get_lock():
            self.threshold_hp_empty.value = defaults["hp_empty"]

        self._syncing_controls = True
        self.threshold_open_loot_spin.setValue(defaults["open"])
        self.threshold_loot_window_spin.setValue(defaults["loot"])
        self.threshold_hp_full_spin.setValue(defaults["hp_full"])
        self.threshold_hp_damaged_spin.setValue(defaults["hp_damaged"])
        self.threshold_hp_empty_spin.setValue(defaults["hp_empty"])
        self._syncing_controls = False
        self._append_log("Thresholds reset to defaults.")

    def _handle_debug_mode_toggled(self, state):
        enabled = state == QtCore.Qt.Checked
        with self.debug_mode.get_lock():
            self.debug_mode.value = enabled
        self.manual_capture_button.setEnabled(enabled)
        self._append_log("Debug mode enabled." if enabled else "Debug mode disabled.")

    def _handle_show_coords_toggled(self, state):
        enabled = state == QtCore.Qt.Checked
        with self.show_coords.get_lock():
            self.show_coords.value = enabled
        if self.show_coords_checkbox.hasFocus():
            self._append_log("Click coordinate logging enabled." if enabled else "Click coordinate logging disabled.")

    def _handle_show_confidence_toggled(self, state):
        enabled = state == QtCore.Qt.Checked
        with self.show_confidence.get_lock():
            self.show_confidence.value = enabled
        if self.show_confidence_checkbox.hasFocus():
            self._append_log("Confidence logging enabled." if enabled else "Confidence logging disabled.")

    def _handle_debug_capture_toggled(self, flag, state):
        enabled = state == QtCore.Qt.Checked
        with flag.get_lock():
            flag.value = enabled

    def _handle_disable_bot_actions_toggled(self, state):
        """Handle disable bot actions checkbox toggle"""
        is_disabled = (state == QtCore.Qt.Checked)
        with self.disable_bot_actions.get_lock():
            self.disable_bot_actions.value = is_disabled
        status = "disabled" if is_disabled else "enabled"
        self._append_log(f"Bot actions {status} (detection: {'only' if is_disabled else 'with actions'}).")

    def _handle_use_overlay_zones_toggled(self, state):
        self.use_overlay_zones = (state == QtCore.Qt.Checked)
        status = "enabled" if self.use_overlay_zones else "disabled"
        self._append_log(f"Overlay zone override {status}.")
        try:
            with self.use_overlay_zones_flag.get_lock():
                self.use_overlay_zones_flag.value = 1 if self.use_overlay_zones else 0
        except Exception:
            pass

        if self.use_overlay_zones:
            regions = self._collect_overlay_regions()
            if regions:
                self._update_shared_overlay_zones(regions, force=True)
            if not self.overlay_window:
                self._append_log("Enable the overlay to adjust detection zones before starting the bot.")

    def _handle_manual_capture(self):
        with self.manual_capture_trigger.get_lock():
            self.manual_capture_trigger.value += 1
        self._append_log("Manual debug capture requested.")

    def _handle_overlay_toggled(self, state):
        enabled = state == QtCore.Qt.Checked
        with self.overlay_enabled.get_lock():
            self.overlay_enabled.value = enabled
        if enabled:
            self._ensure_overlay_window()
            self.overlay_window.set_resolution_info(
                self.current_resolution,
                self.current_scale_x,
                self.current_scale_y,
                self.current_border_offset,
            )
            self.overlay_window.show()
            self._append_log("Overlay display enabled.")
        else:
            if self.overlay_window:
                self.overlay_window.hide()
            self._append_log("Overlay display disabled.")

    def _ensure_overlay_window(self):
        if self.overlay_window is None:
            self.overlay_window = DetectionOverlayWindow(
                self,
                log_callback=self._append_log,
                update_callback=self._handle_overlay_zones_updated,
            )

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

    def _format_elapsed_time(self, total_seconds):
        """
        Format elapsed time in seconds to HH:MM:SS string.

        Args:
            total_seconds: Time in seconds (float or int)

        Returns:
            Formatted time string (e.g., "01:23:45")
        """
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

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

        self.running_time_label.setText(self._format_elapsed_time(total_seconds))

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
        if isinstance(event, dict):
            event_type = event.get("type", "status")

            if event_type == "detection_overlay":
                self._handle_overlay_frame(event)
                return

            if event_type == "overlay_click":
                if self.overlay_checkbox.isChecked():
                    self._ensure_overlay_window()
                    self.overlay_window.add_click(
                        event.get("x"),
                        event.get("y"),
                        event.get("label", "Click"),
                        event.get("color", (255, 255, 0)),
                    )
                if log_messages:
                    label = event.get("label", "Click")
                    x = event.get("x")
                    y = event.get("y")
                    self._append_log(f"[OVERLAY] {label} at ({x}, {y})")
                return

            if event_type == "overlay_error":
                if log_messages:
                    self._append_log(f"[OVERLAY] {event.get('message', 'Overlay error')}")
                return

            if not log_messages:
                return

            message = event.get("message") or event_type.replace("_", " ").title()

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

            if event_type == "error":
                log_entry = f"[ERROR] {message}"
            elif event_type == "legendary":
                log_entry = f"[LEGENDARY] {message}"
                if extras:
                    log_entry += f" | {extras}"
            else:
                log_entry = " | ".join(filter(None, [message, extras]))

            self._append_log(log_entry)
        else:
            if log_messages:
                text = str(event)
                self._append_log(text)

    def _handle_overlay_frame(self, event):
        if not self.overlay_checkbox.isChecked():
            return

        image_data = event.get("image")
        width = event.get("width")
        height = event.get("height")
        zones = event.get("zones")
        resolution = event.get("resolution", "Unknown")
        scale_x = event.get("scale_x", 1.0)
        scale_y = event.get("scale_y", 1.0)
        border_offset = event.get("border_offset", (0, 0))

        if image_data is None or not width or not height:
            return

        if isinstance(image_data, list):
            image_data = bytes(image_data)
        elif isinstance(image_data, str):
            image_data = image_data.encode("latin1")

        self._ensure_overlay_window()
        self.overlay_window.set_resolution_info(
            resolution,
            scale_x,
            scale_y,
            border_offset,
        )
        self.overlay_window.update_detection_data(image_data, width, height, zones)
        regions = self.overlay_window.get_adjusted_regions()
        if regions:
            self._update_shared_overlay_zones(regions, force=False)

    @staticmethod
    def _normalize_overlay_regions(regions):
        if not regions:
            return None
        normalized = {}
        for name, data in regions.items():
            if not isinstance(data, dict):
                continue
            try:
                normalized[name] = {
                    "x": int(data.get("x", 0)),
                    "y": int(data.get("y", 0)),
                    "w": max(1, int(data.get("w", 0))),
                    "h": max(1, int(data.get("h", 0))),
                }
            except Exception:
                continue
        return normalized or None

    def _update_shared_overlay_zones(self, regions, force=False):
        normalized = self._normalize_overlay_regions(regions)
        if not force and normalized == self.overlay_last_regions:
            return self.overlay_last_regions

        self.overlay_last_regions = normalized

        if self.overlay_zones_dict is None:
            return normalized

        try:
            self.overlay_zones_dict.clear()
            if normalized:
                for name, data in normalized.items():
                    self.overlay_zones_dict[name] = data
        except Exception as exc:
            self._append_log(f"Failed to sync overlay zones: {exc}")

        return normalized

    def _handle_overlay_zones_updated(self, regions):
        self._update_shared_overlay_zones(regions, force=True)

    def _collect_overlay_regions(self):
        if self.overlay_window:
            current = self.overlay_window.get_adjusted_regions()
            if current:
                normalized = self._normalize_overlay_regions(current)
                if normalized:
                    self.overlay_last_regions = normalized
        if self.overlay_last_regions:
            return {name: dict(values) for name, values in self.overlay_last_regions.items()}
        return None

    def _apply_validation_details(self, details):
        if not isinstance(details, dict):
            return
        self.current_resolution = details.get("detected_resolution", "Unknown")
        self.current_scale_x = float(details.get("scale_x", 1.0))
        self.current_scale_y = float(details.get("scale_y", 1.0))
        border = details.get("border_offset")
        if isinstance(border, (tuple, list)) and len(border) == 2:
            self.current_border_offset = (int(border[0]), int(border[1]))
        if self.overlay_window:
            self.overlay_window.set_resolution_info(
                self.current_resolution,
                self.current_scale_x,
                self.current_scale_y,
                self.current_border_offset,
            )

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

        if self.overlay_window:
            self.overlay_window.hide()

        with self.started_flag.get_lock():
            self.started_flag.value = False
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        speak_async("Bot Stopped")
        note = "Bot stopped." if manual else "Bot process ended."
        self._append_log(note)
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
    manager = _get_shared_manager()
    return {
        "started": multiprocessing.Value("i", False),
        "gui_settings_opened": multiprocessing.Value("i", False),
        "attack_delay": multiprocessing.Value("d", 0.1),
        "wait_after_enemy_spawn": multiprocessing.Value("d", 5.5),
        "loot_opened": multiprocessing.Value("i", 0),
        "legendaries": multiprocessing.Value("i", 0),
        "screenshot_enabled": multiprocessing.Value("i", True),  # Default: enabled
        "resolution_mode": multiprocessing.Value("i", bot_logic.DEFAULT_RESOLUTION_MODE),
        "threshold_open_loot": multiprocessing.Value("d", bot_logic.THRESHOLD_OPEN_LOOT),
        "threshold_loot_window": multiprocessing.Value("d", bot_logic.THRESHOLD_LOOT_WINDOW),
        "threshold_hp_full": multiprocessing.Value("d", bot_logic.THRESHOLD_HP_FULL),
        "threshold_hp_damaged": multiprocessing.Value("d", bot_logic.THRESHOLD_HP_DAMAGED),
        "threshold_hp_empty": multiprocessing.Value("d", bot_logic.THRESHOLD_HP_EMPTY),
        "debug_mode": multiprocessing.Value("i", False),
        "show_coords": multiprocessing.Value("i", False),
        "show_confidence": multiprocessing.Value("i", False),
        "debug_capture_open_loot": multiprocessing.Value("i", True),
        "debug_capture_loot_window": multiprocessing.Value("i", True),
        "debug_capture_hp_full": multiprocessing.Value("i", False),
        "debug_capture_hp_damaged": multiprocessing.Value("i", False),
        "debug_capture_hp_empty": multiprocessing.Value("i", False),
        "manual_capture_trigger": multiprocessing.Value("i", 0),
        "overlay_enabled": multiprocessing.Value("i", False),
        "disable_bot_actions": multiprocessing.Value("i", False),
        "use_overlay_zones_flag": multiprocessing.Value("i", False),
        "overlay_zones_dict": manager.dict(),
    }


def main():
    """Main entry point - only runs in the main process"""
    shared_state = _build_shared_state()
    app = QtWidgets.QApplication(sys.argv)
    window = BotWindow(shared_state)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    # Required for PyInstaller to work with multiprocessing on Windows
    # freeze_support() must be called FIRST before any other code
    multiprocessing.freeze_support()

    # CRITICAL: Only run GUI in main process, not in spawned subprocesses
    # This prevents the frozen exe from opening multiple windows
    if multiprocessing.current_process().name == 'MainProcess':
        # Set spawn method explicitly for Windows + PyInstaller compatibility
        if sys.platform == 'win32':
            try:
                multiprocessing.set_start_method('spawn')
            except RuntimeError:
                # Already set, ignore
                pass

        main()
