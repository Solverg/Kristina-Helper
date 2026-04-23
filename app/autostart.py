"""
Kristina Helper — управление автозапуском (Windows Registry).
"""

import sys
import os
import logging

logger = logging.getLogger(__name__)

REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "KristinaHelper"


class AutostartManager:
    """Добавляет/удаляет приложение из автозапуска Windows."""

    @staticmethod
    def _get_exe_path() -> str:
        """Путь к исполняемому файлу (или python main.py)."""
        if getattr(sys, "frozen", False):
            # PyInstaller сборка
            return sys.executable
        else:
            # Режим разработки
            return f'"{sys.executable}" "{os.path.abspath("main.py")}"'

    @staticmethod
    def is_enabled() -> bool:
        """Проверить, есть ли запись в реестре."""
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
                winreg.QueryValueEx(key, APP_NAME)
                return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Ошибка проверки автозапуска: {e}")
            return False

    @staticmethod
    def enable() -> bool:
        """Добавить в автозапуск."""
        try:
            import winreg
            exe_path = AutostartManager._get_exe_path()
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, REGISTRY_KEY,
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
            logger.info(f"Автозапуск включён: {exe_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка включения автозапуска: {e}")
            return False

    @staticmethod
    def disable() -> bool:
        """Убрать из автозапуска."""
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, REGISTRY_KEY,
                0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, APP_NAME)
            logger.info("Автозапуск отключён")
            return True
        except FileNotFoundError:
            return True  # Уже не было
        except Exception as e:
            logger.error(f"Ошибка отключения автозапуска: {e}")
            return False

    @staticmethod
    def toggle() -> bool:
        """Переключить состояние. Возвращает новое состояние."""
        if AutostartManager.is_enabled():
            AutostartManager.disable()
            return False
        else:
            AutostartManager.enable()
            return True
