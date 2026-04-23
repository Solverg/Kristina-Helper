"""
Kristina Helper — главное окно приложения.
"""

import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QSizePolicy,
    QStatusBar, QFrame
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QFont

from app.styles import STYLESHEET
from app.settings import SettingsManager
from app.process_manager import ProcessManager
from app.processes_panel import ProcessesPanel
from app.ai_chat import AIChatWidget
from app.settings_panel import SettingsPanel


ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

NAV_ITEMS = [
    ("🖥", "Процессы",  0),
    ("✨", "AI-чат",    1),
    ("⚙️", "Настройки", 2),
]


class NavButton(QPushButton):
    """Кнопка бокового меню."""

    def __init__(self, icon_char: str, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("nav_btn")
        self.setText(f"  {icon_char}   {label}")
        self.setCheckable(True)
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, active: bool):
        self.setChecked(active)
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class Sidebar(QWidget):
    """Боковая панель навигации с аватаром."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(360)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(4)
        avatar_width = 300
        avatar_height = 300
        avatar_radius = 24

        # ── Аватар ────────────────────────────────────────────────────────────
        avatar_container = QWidget()
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        avatar_layout.setSpacing(8)

        avatar_label = QLabel()
        avatar_path = os.path.join(ASSETS_DIR, "avatar.png")
        if os.path.exists(avatar_path):
            pixmap = QPixmap(avatar_path).scaled(
                avatar_width, avatar_height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            # Прямоугольная маска со слегка скруглёнными углами
            from PyQt6.QtGui import QPainter, QPainterPath
            from PyQt6.QtCore import QRectF
            rounded = QPixmap(avatar_width, avatar_height)
            rounded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(
                QRectF(0, 0, avatar_width, avatar_height),
                avatar_radius,
                avatar_radius,
            )
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            avatar_label.setPixmap(rounded)
        else:
            avatar_label.setText("👩‍💻")
            avatar_label.setStyleSheet("font-size: 96px;")
            avatar_label.setMinimumSize(avatar_width, avatar_height)

        avatar_label.setFixedSize(avatar_width, avatar_height)
        avatar_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        avatar_layout.addWidget(avatar_label)

        name_label = QLabel("Kristina Helper")
        name_label.setObjectName("logo_label")
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        tagline = QLabel("Process Guardian ✨")
        tagline.setObjectName("subtitle_label")
        tagline.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        avatar_layout.addWidget(name_label)
        avatar_layout.addWidget(tagline)
        layout.addWidget(avatar_container)

        # ── Разделитель ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #21262d; max-height: 1px; margin: 8px 0;")
        layout.addWidget(sep)

        # ── Навигация ─────────────────────────────────────────────────────────
        self._nav_buttons: list[NavButton] = []
        for icon, label, _ in NAV_ITEMS:
            btn = NavButton(icon, label)
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # ── Статус мониторинга ────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background-color: #21262d; max-height: 1px; margin: 8px 0;")
        layout.addWidget(sep2)

        self._status_dot = QLabel("● Кристина на страже")
        self._status_dot.setStyleSheet(
            "color: #3fb950; font-size: 11px; font-weight: 600; padding: 4px 8px;"
        )
        self._status_dot.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._status_dot)

    def get_buttons(self) -> list[NavButton]:
        return self._nav_buttons

    def set_status(self, text: str, color: str = "#3fb950"):
        self._status_dot.setText(f"● {text}")
        self._status_dot.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: 600; padding: 4px 8px;"
        )


class MainWindow(QMainWindow):
    """Главное окно Kristina Helper."""

    def __init__(self):
        super().__init__()
        self.settings = SettingsManager()
        self.pm = ProcessManager()
        self._build_ui()
        self._connect_signals()
        self._start_monitoring()

    def _build_ui(self):
        self.setWindowTitle("Kristina Helper")
        self.setMinimumSize(1100, 680)
        self.resize(1280, 780)

        # Иконка
        icon_path = os.path.join(ASSETS_DIR, "avatar.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Глобальный стиль
        self.setStyleSheet(STYLESHEET)

        # ── Центральный виджет ────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Сайдбар ───────────────────────────────────────────────────────────
        self._sidebar = Sidebar()
        root_layout.addWidget(self._sidebar)

        # ── Основная область ──────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._stack, stretch=1)

        # ── Страницы ──────────────────────────────────────────────────────────
        self._processes_panel = ProcessesPanel(self.pm)
        self._chat_panel = AIChatWidget(self.settings)
        self._settings_panel = SettingsPanel(self.settings)

        self._stack.addWidget(self._processes_panel)  # index 0
        self._stack.addWidget(self._chat_panel)        # index 1
        self._stack.addWidget(self._settings_panel)   # index 2

        # ── Статусная строка ──────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self._status_bar.showMessage("Kristina Helper запущена · Мониторинг активен")
        self.setStatusBar(self._status_bar)

        # Выбрать первую страницу
        self._select_page(0)

    def _connect_signals(self):
        # Навигация
        for i, btn in enumerate(self._sidebar.get_buttons()):
            btn.clicked.connect(lambda checked, idx=i: self._select_page(idx))

        # Переход в чат при нажатии "Спросить AI"
        self._processes_panel.ask_ai_about.connect(self._ask_ai_about_process)

        # Обновление статуса
        self.pm.stats_updated.connect(self._on_stats_updated)
        self.pm.process_killed.connect(self._on_process_killed)

    def _select_page(self, index: int):
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._sidebar.get_buttons()):
            btn.set_active(i == index)

    def _start_monitoring(self):
        interval = self.settings.get("scan_interval_sec", 5) * 1000
        self.pm.start_monitoring(interval)
        # Первое сканирование сразу
        QTimer.singleShot(500, self.pm.scan_and_enforce)

    def _ask_ai_about_process(self, process_name: str):
        """Переключиться в чат и вставить вопрос про процесс."""
        self._select_page(1)
        self._chat_panel.inject_process_context(process_name)

    def _on_stats_updated(self, stats: dict):
        total = stats.get("total_processes", 0)
        rules = stats.get("blocked_rules", 0)
        running_blocked = stats.get("blocked_running", 0)

        msg = f"Процессов: {total}  ·  Правил блокировки: {rules}"
        if running_blocked > 0:
            msg += f"  ·  ⚠ Активных блокированных: {running_blocked}"
        self._status_bar.showMessage(msg)

        if running_blocked > 0:
            self._sidebar.set_status("Завершаю процессы...", "#f0883e")
        else:
            self._sidebar.set_status("Кристина на страже", "#3fb950")

    def _on_process_killed(self, name: str, pid: int):
        self._status_bar.showMessage(f"✓ Завершён: {name} (PID {pid})", 4000)

        if self.settings.get("show_notifications"):
            # Уведомление через трей (если есть)
            tray = self.parent()  # TrayManager передаётся снаружи если нужно
            # Простое сообщение в статусбаре достаточно

    def closeEvent(self, event):
        """При закрытии — сворачиваем в трей, не выходим."""
        if self.settings.get("minimize_to_tray"):
            event.ignore()
            self.hide()
        else:
            self.pm.stop_monitoring()
            event.accept()
