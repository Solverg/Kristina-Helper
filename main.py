"""Kristina Helper — главный файл запуска."""

import os
import sys
import ctypes

# Добавляем папку проекта в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main_window import MainWindow
from app.tray import TrayManager
from app.autostart import AutostartManager


def get_resource_path(relative_path):
    """Возвращает абсолютный путь к ресурсу, работает и для dev, и для PyInstaller"""
    try:
        # PyInstaller создает временную папку и сохраняет путь в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Если запуск обычный, берем путь от текущего файла
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


def main():
    # 1. Служебный режим для апдейтера.
    # Выполняем ДО проверки на дубликаты, чтобы апдейтер мог запустить healthcheck
    # даже если основная программа еще висит в памяти.
    if "--healthcheck" in sys.argv:
        print("healthcheck:ok")
        return

    # 2. Проверка на единственную копию (только для Windows)
    if sys.platform == "win32":
        mutex_name = "KristinaHelper_SingleInstance_Mutex"

        # Держим ссылку до конца main, чтобы mutex не освободился сборщиком мусора.
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)

        if not mutex:
            print("Не удалось создать системный mutex, продолжаем запуск без блокировки дублей.")
        elif ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            print("Kristina Helper уже запущена.")
            sys.exit(0)

    # 3. Стандартный запуск PyQt
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QApplication

    # Включаем HiDPI для Windows 11
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Kristina Helper")
    app.setApplicationVersion("1.2.0")
    app.setQuitOnLastWindowClosed(False)  # Остаёмся в трее при закрытии окна

    # Иконка приложения
    icon_path = get_resource_path(os.path.join("assets", "avatar.png"))
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
