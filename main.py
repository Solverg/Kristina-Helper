"""
Kristina Helper — главный файл запуска.
"""

import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt

# Добавляем папку проекта в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main_window import MainWindow
from app.tray import TrayManager
from app.autostart import AutostartManager


def main():
    # Включаем HiDPI для Windows 11
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Kristina Helper")
    app.setApplicationVersion("1.0.0")
    app.setQuitOnLastWindowClosed(False)  # Остаёмся в трее при закрытии окна

    # Иконка приложения
    icon_path = os.path.join(os.path.dirname(__file__), "assets", "avatar.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Основное окно
    window = MainWindow()

    # Системный трей
    tray = TrayManager(window, app)
    tray.setup()

    # Показываем окно при первом запуске
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
