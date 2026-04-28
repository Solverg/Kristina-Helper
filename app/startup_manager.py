"""
Kristina Helper — расширенное управление автозапуском (Windows Registry + Startup folders).
"""

from __future__ import annotations

import ctypes
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import winreg
except ModuleNotFoundError:  # pragma: no cover - не Windows окружение
    winreg = None


@dataclass(slots=True)
class StartupItem:
    """Модель элемента автозагрузки."""

    name: str
    target_path: str
    source: str  # 'HKCU', 'HKLM', 'FOLDER_USER', 'FOLDER_SYSTEM'
    status: str  # 'active', 'paused'
    raw_key: str | None = None  # Оригинальный идентификатор для восстановления


class StartupAppsManager:
    """Менеджер автозапуска для HKCU/HKLM и Startup-папок."""

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    BACKUP_KEY_BASE = r"Software\KristinaHelper\PausedStartup"

    FOLDER_USER = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup",
    )
    FOLDER_SYSTEM = os.path.join(
        os.environ.get("PROGRAMDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup",
    )

    _SYSTEM_SOURCES = {"HKLM", "FOLDER_SYSTEM"}
    _SELF_APP_NAMES = {"KristinaHelper", "Kristina Helper"}

    @classmethod
    def _is_windows_registry_available(cls) -> bool:
        return winreg is not None

    @staticmethod
    def is_admin() -> bool:
        """Проверяет, запущена ли программа с правами администратора."""
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @classmethod
    def _ensure_registry_backup_key(cls, hive):
        """Создаёт backup-ветку в реестре (если доступна)."""
        if not cls._is_windows_registry_available():
            return

        try:
            winreg.CreateKey(hive, cls.BACKUP_KEY_BASE)
        except PermissionError:
            logger.debug("Недостаточно прав для создания backup-ветки в системном hive.")
        except Exception as e:
            logger.debug(f"Не удалось создать backup-ветку: {e}")

    @classmethod
    def get_apps(cls) -> list[StartupItem]:
        """Собирает элементы автозагрузки из всех источников."""
        apps: list[StartupItem] = []

        if cls._is_windows_registry_available():
            apps.extend(cls._read_registry_hive(winreg.HKEY_CURRENT_USER, "HKCU"))
            apps.extend(cls._read_registry_hive(winreg.HKEY_LOCAL_MACHINE, "HKLM"))

        apps.extend(cls._read_startup_folder(cls.FOLDER_USER, "FOLDER_USER"))
        apps.extend(cls._read_startup_folder(cls.FOLDER_SYSTEM, "FOLDER_SYSTEM"))

        return sorted(apps, key=lambda item: (item.name.lower(), item.source, item.status))

    @classmethod
    def _read_registry_hive(cls, hive, source_name: str) -> list[StartupItem]:
        items: list[StartupItem] = []
        cls._ensure_registry_backup_key(hive)

        try:
            with winreg.OpenKey(hive, cls.RUN_KEY, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, path, _ = winreg.EnumValue(key, i)
                        if name not in cls._SELF_APP_NAMES and isinstance(path, str):
                            items.append(StartupItem(name=name, target_path=path, source=source_name, status="active", raw_key=name))
                        i += 1
                    except OSError:
                        break
        except Exception as e:
            logger.debug(f"Чтение {source_name} RUN_KEY пропущено: {e}")

        try:
            with winreg.OpenKey(hive, cls.BACKUP_KEY_BASE, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, path, _ = winreg.EnumValue(key, i)
                        if isinstance(path, str):
                            items.append(StartupItem(name=name, target_path=path, source=source_name, status="paused", raw_key=name))
                        i += 1
                    except OSError:
                        break
        except Exception as e:
            logger.debug(f"Чтение {source_name} BACKUP пропущено: {e}")

        return items

    @classmethod
    def _read_startup_folder(cls, folder_path: str, source_name: str) -> list[StartupItem]:
        items: list[StartupItem] = []
        if not folder_path or not os.path.isdir(folder_path):
            return items

        try:
            filenames = sorted(os.listdir(folder_path))
        except Exception as e:
            logger.debug(f"Не удалось прочитать папку автозагрузки {folder_path}: {e}")
            return items

        for file_name in filenames:
            full_path = os.path.join(folder_path, file_name)
            if file_name.endswith(".lnk"):
                items.append(StartupItem(name=file_name, target_path=full_path, source=source_name, status="active", raw_key=full_path))
            elif file_name.endswith(".lnk.disabled"):
                clean_name = file_name.removesuffix(".disabled")
                items.append(StartupItem(name=clean_name, target_path=full_path, source=source_name, status="paused", raw_key=full_path))

        return items

    @classmethod
    def toggle_app(cls, item: StartupItem) -> bool:
        """Переключает состояние элемента автозагрузки."""
        if item.source in cls._SYSTEM_SOURCES and not cls.is_admin():
            logger.warning(f"Нет прав администратора для изменения {item.name}")
            return False

        if item.status == "active":
            return cls._pause_app(item)
        return cls._resume_app(item)

    @classmethod
    def _pause_app(cls, item: StartupItem) -> bool:
        try:
            if item.source.startswith("FOLDER"):
                if not item.raw_key:
                    return False
                os.rename(item.raw_key, f"{item.raw_key}.disabled")
                return True

            if not cls._is_windows_registry_available() or not item.raw_key:
                return False

            hive = winreg.HKEY_LOCAL_MACHINE if item.source == "HKLM" else winreg.HKEY_CURRENT_USER
            cls._ensure_registry_backup_key(hive)
            with winreg.OpenKey(hive, cls.RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as run_key:
                path, _ = winreg.QueryValueEx(run_key, item.raw_key)
                with winreg.OpenKey(hive, cls.BACKUP_KEY_BASE, 0, winreg.KEY_SET_VALUE) as backup_key:
                    winreg.SetValueEx(backup_key, item.raw_key, 0, winreg.REG_SZ, path)
                winreg.DeleteValue(run_key, item.raw_key)
            return True
        except Exception as e:
            logger.error(f"Ошибка приостановки {item.name}: {e}")
            return False

    @classmethod
    def _resume_app(cls, item: StartupItem) -> bool:
        try:
            if item.source.startswith("FOLDER"):
                if not item.raw_key:
                    return False
                os.rename(item.raw_key, item.raw_key.removesuffix(".disabled"))
                return True

            if not cls._is_windows_registry_available() or not item.raw_key:
                return False

            hive = winreg.HKEY_LOCAL_MACHINE if item.source == "HKLM" else winreg.HKEY_CURRENT_USER
            with winreg.OpenKey(hive, cls.BACKUP_KEY_BASE, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as backup_key:
                path, _ = winreg.QueryValueEx(backup_key, item.raw_key)
                with winreg.OpenKey(hive, cls.RUN_KEY, 0, winreg.KEY_SET_VALUE) as run_key:
                    winreg.SetValueEx(run_key, item.raw_key, 0, winreg.REG_SZ, path)
                winreg.DeleteValue(backup_key, item.raw_key)
            return True
        except Exception as e:
            logger.error(f"Ошибка возобновления {item.name}: {e}")
            return False
