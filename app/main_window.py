"""
Kristina Helper — главное окно приложения.
"""

import sys
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QStackedWidget, QSizePolicy,
    QStatusBar, QFrame, QApplication
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPixmap, QIcon, QFont

from app.styles import STYLESHEET
from app.settings import SettingsManager
from app.process_manager import ProcessManager
from app.processes_panel import ProcessesPanel
from app.ai_chat import AIChatWidget
from app.settings_panel import SettingsPanel
from app.startup_panel import StartupPanel
from app.updater import UpdateChecker, UpdateDialog


def get_resource_path(relative_path):
    """Возвращает абсолютный путь к ресурсу, работает и для dev, и для PyInstaller"""
    try:
        # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Если запуск обычный, берем путь от текущего файла
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)


ASSETS_DIR = get_resource_path("assets")

NAV_ITEMS = [
    ("🖥", "Процессы",     0),
    ("🚀", "Автозагрузка", 1),
    ("✨", "AI-чат",       2),
    ("⚙️", "Настройки",   3),
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
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._avatar_path = os.path.join(ASSETS_DIR, "avatar.png")
        self._avatar_radius = 24
        self._avatar_label: QLabel | None = None
        self._module_icon_labels: list[QLabel] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(4)
        # ── Аватар ────────────────────────────────────────────────────────────
        avatar_container = QWidget()
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        avatar_layout.setSpacing(8)

        self._avatar_label = QLabel()
        self._avatar_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        avatar_layout.addWidget(self._avatar_label)
        self._update_avatar()

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

        # ── Дополнительные модули (иконки) ────────────────────────────────────
        modules_sep = QFrame()
        modules_sep.setFrameShape(QFrame.Shape.HLine)
        modules_sep.setStyleSheet("background-color: #21262d; max-height: 1px; margin: 12px 0 8px 0;")
        layout.addWidget(modules_sep)

        modules_layout = QHBoxLayout()
        modules_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        modules_layout.setSpacing(16)

        icon_files = ["icon1.png", "icon2.png", "icon3.png"]

        for icon_file in icon_files:
            icon_path = os.path.join(ASSETS_DIR, icon_file)
            icon_label = QLabel()
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setProperty("icon_path", icon_path)

            icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
            icon_label.setToolTip(f"Модуль {icon_file}")
            self._module_icon_labels.append(icon_label)

            modules_layout.addWidget(icon_label)

        layout.addLayout(modules_layout)
        self._update_module_icons()

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_avatar()
        self._update_module_icons()

    def _update_module_icons(self):
        if not self._module_icon_labels:
            return

        # Адаптивный размер: иконки всегда помещаются целиком в сайдбаре.
        icon_side = max(24, min(64, (self.width() - 80) // 3))

        for icon_label in self._module_icon_labels:
            icon_label.setFixedSize(icon_side, icon_side)
            icon_label.setStyleSheet("")
            icon_path = icon_label.property("icon_path")

            if icon_path and os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    icon_label.setPixmap(
                        pixmap.scaled(
                            icon_side,
                            icon_side,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    continue

            icon_label.setPixmap(QPixmap())
            icon_label.setStyleSheet("background-color: #30363d; border-radius: 6px;")

    def _update_avatar(self):
        if self._avatar_label is None:
            return

        avatar_side = max(180, min(300, self.width() - 40))
        self._avatar_label.setFixedSize(avatar_side, avatar_side)

        if os.path.exists(self._avatar_path):
            pixmap = QPixmap(self._avatar_path).scaled(
                avatar_side,
                avatar_side,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )

            from PyQt6.QtGui import QPainter, QPainterPath
            from PyQt6.QtCore import QRectF
            rounded = QPixmap(avatar_side, avatar_side)
            rounded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(
                QRectF(0, 0, avatar_side, avatar_side),
                self._avatar_radius,
                self._avatar_radius,
            )
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            self._avatar_label.setPixmap(rounded)
            self._avatar_label.setText("")
            self._avatar_label.setStyleSheet("")
        else:
            font_size = max(56, int(avatar_side * 0.32))
            self._avatar_label.setPixmap(QPixmap())
            self._avatar_label.setText("👩‍💻")
            self._avatar_label.setStyleSheet(f"font-size: {font_size}px;")

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
        self._update_checked = False
        self._build_ui()
        self._connect_signals()
        self._start_monitoring()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._update_checked:
            self._update_checked = True
            self.check_for_updates()

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
        self._processes_panel = ProcessesPanel(self.pm, self.settings)
        self._chat_panel = AIChatWidget(self.settings)
        self._settings_panel = SettingsPanel(self.settings)
        self._startup_panel = StartupPanel()

        self._stack.addWidget(self._processes_panel)  # index 0 — Процессы
        self._stack.addWidget(self._startup_panel)    # index 1 — Автозагрузка
        self._stack.addWidget(self._chat_panel)        # index 2 — AI-чат
        self._stack.addWidget(self._settings_panel)   # index 3 — Настройки

        # ── Статусная строка ──────────────────────────────────────────────────
        self._status_bar = QStatusBar()
        self._status_bar.showMessage("Kristina Helper запущена · Мониторинг активен")
        self.setStatusBar(self._status_bar)

        # Выбрать первую страницу
        self._select_page(0)
        self._update_sidebar_width()

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_sidebar_width()

    def _update_sidebar_width(self):
        sidebar_width = max(280, min(420, int(self.width() * 0.3)))
        self._sidebar.setFixedWidth(sidebar_width)

    def _start_monitoring(self):
        interval = self.settings.get("scan_interval_sec", 5) * 1000
        self.pm.start_monitoring(interval)
        # Первое сканирование сразу
        QTimer.singleShot(500, self.pm.scan_and_enforce)

    def check_for_updates(self):
        current_version = QApplication.instance().applicationVersion()
        if not current_version:
            current_version = "1.0.3"

        self.updater_thread = UpdateChecker(current_version)
        self.updater_thread.update_available.connect(self.show_update_dialog)
        self.updater_thread.start()

    def show_update_dialog(self, version: str, download_url: str):
        self.update_dlg = UpdateDialog(version, download_url, self)
        self.update_dlg.exec()

    def _ask_ai_about_process(self, process_name: str):
        """Переключиться в чат и вставить вопрос про процесс."""
        self._select_page(2)  # AI-чат теперь index 2
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
