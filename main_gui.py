import ctypes
import multiprocessing
import queue
import sys
import threading
from datetime import datetime

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
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
"""

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

        self.status_queue = multiprocessing.Queue()
        self.process = None
        self._bot_start_time = None
        self._accumulated_time = 0  # Total seconds accumulated across sessions
        self._syncing_controls = False
        self._last_started_state = bool(self.started_flag.value)

        self._init_window()
        self._build_ui()
        self._connect_signals()
        self._start_status_timer()
        self._apply_theme()
        self._finalize_size()

    def _init_window(self):
        self.setWindowTitle("TLOPO Bot Controller")
        self.setMinimumSize(600, 650)

    def _build_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(12)

        self.title_label = QtWidgets.QLabel("TLOPO Looter")
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        header_layout.addWidget(self.title_label)

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

        status_layout.addWidget(QtWidgets.QLabel("Bot Status"), 0, 0)
        self.status_value_label = QtWidgets.QLabel("Stopped")
        self.status_value_label.setObjectName("statusValueLabel")
        self.status_value_label.setProperty("running", "false")
        status_layout.addWidget(self.status_value_label, 0, 1)

        loot_label = QtWidgets.QLabel("Loot Opened")
        loot_label.setObjectName("lootLabel")
        status_layout.addWidget(loot_label, 1, 0)
        self.loot_value_label = QtWidgets.QLabel("0")
        self.loot_value_label.setObjectName("lootValueLabel")
        status_layout.addWidget(self.loot_value_label, 1, 1)

        legendary_label = QtWidgets.QLabel("Legendaries Found")
        legendary_label.setObjectName("legendaryLabel")
        status_layout.addWidget(legendary_label, 2, 0)
        self.legendary_value_label = QtWidgets.QLabel("0")
        self.legendary_value_label.setObjectName("legendaryValueLabel")
        status_layout.addWidget(self.legendary_value_label, 2, 1)

        status_layout.addWidget(QtWidgets.QLabel("Running Time"), 3, 0)
        self.running_time_label = QtWidgets.QLabel("00:00:00")
        self.running_time_label.setObjectName("runningTimeLabel")
        status_layout.addWidget(self.running_time_label, 3, 1)

        self.status_group.setLayout(status_layout)
        dashboard_layout.addWidget(self.status_group)

        control_container = QtWidgets.QGroupBox("Quick Controls")
        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setSpacing(8)
        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.setObjectName("startButton")
        self.stop_button = QtWidgets.QPushButton("Stop")
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

    def _handle_start_clicked(self):
        if self._bot_is_running():
            self._append_log("Bot is already running.")
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
        defaults = {"attack_delay": 0.0, "wait_after_enemy_spawn": 5.5}
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
        if not os.path.exists(folder_to_open):
            try:
                os.makedirs(folder_to_open)
                self._append_log(f"Created screenshot folder: {folder_to_open}")
            except Exception as e:
                self._append_log(f"Error creating folder: {e}")
                return

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
        self._drain_status_queue()
        self._update_status_labels()

    def _bot_is_running(self):
        return bool(self.started_flag.value) or (
            self.process is not None and self.process.is_alive()
        )

    def closeEvent(self, event):
        self.status_timer.stop()
        try:
            self._stop_bot_process(manual=False)
            try:
                self.status_queue.close()
                self.status_queue.join_thread()
            except Exception:
                pass
        finally:
            event.accept()


def _build_shared_state():
    return {
        "started": multiprocessing.Value("i", False),
        "gui_settings_opened": multiprocessing.Value("i", False),
        "attack_delay": multiprocessing.Value("d", 0.0),
        "wait_after_enemy_spawn": multiprocessing.Value("d", 5.5),
        "loot_opened": multiprocessing.Value("i", 0),
        "legendaries": multiprocessing.Value("i", 0),
        "screenshot_enabled": multiprocessing.Value("i", True),  # Default: enabled
    }


if __name__ == "__main__":
    multiprocessing.freeze_support()
    shared_state = _build_shared_state()
    app = QtWidgets.QApplication(sys.argv)
    window = BotWindow(shared_state)
    window.show()
    sys.exit(app.exec_())
