"""
Kristina Helper — системный трей.
"""

import os
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import Qt


class TrayManager:
    """Иконка в системном трее."""

    def __init__(self, main_window, app: QApplication):
        self.window = main_window
        self.app = app
        self.tray: QSystemTrayIcon | None = None

    def setup(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "avatar.png"
        )
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip("Kristina Helper — охраняю твой компьютер 🛡️")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 4px;
                color: #e6edf3;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #1f3a5f;
                color: #58a6ff;
            }
            QMenu::separator {
                height: 1px;
                background: #21262d;
                margin: 4px 0;
            }
        """)

        show_action = QAction("🪟  Открыть окно", menu)
        show_action.triggered.connect(self._show_window)
        menu.addAction(show_action)

        menu.addSeparator()

        status_action = QAction("● Мониторинг активен", menu)
        status_action.setEnabled(False)
        menu.addAction(status_action)

        menu.addSeparator()

        quit_action = QAction("✖  Выйти", menu)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.show()

    def _show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def show_notification(self, title: str, message: str):
        if self.tray:
            self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
