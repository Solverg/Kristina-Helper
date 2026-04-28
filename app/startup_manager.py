"""
Kristina Helper — управление сторонним автозапуском (Windows Registry).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class StartupAppsManager:
    """Управление автозапуском сторонних приложений в HKCU."""

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    BACKUP_KEY = r"Software\KristinaHelper\PausedStartup"
    _SELF_APP_NAMES = {"KristinaHelper", "Kristina Helper"}

    @staticmethod
    def _winreg():
        import winreg

        return winreg

    @classmethod
    def _ensure_backup_key_exists(cls):
        """Создает резервную ветку реестра, если её нет."""
        try:
            winreg = cls._winreg()
            winreg.CreateKey(winreg.HKEY_CURRENT_USER, cls.BACKUP_KEY)
        except Exception as e:
            logger.error(f"Ошибка создания ключа бекапа: {e}")

    @classmethod
    def _enum_values(cls, key_path: str) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        winreg = cls._winreg()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    name, path, _ = winreg.EnumValue(key, i)
                    if isinstance(path, str):
                        items.append((name, path))
                    i += 1
                except OSError:
                    break
        return items

    @classmethod
    def get_apps(cls) -> list[dict[str, str]]:
        """Возвращает список всех программ (активных и приостановленных)."""
        apps: list[dict[str, str]] = []
        cls._ensure_backup_key_exists()

        try:
            for name, path in cls._enum_values(cls.RUN_KEY):
                if name in cls._SELF_APP_NAMES:
                    continue
                apps.append({"name": name, "path": path, "status": "active"})
        except FileNotFoundError:
            logger.info("Ключ Run не найден в HKCU.")
        except Exception as e:
            logger.error(f"Ошибка чтения активного автозапуска: {e}")

        try:
            for name, path in cls._enum_values(cls.BACKUP_KEY):
                apps.append({"name": name, "path": path, "status": "paused"})
        except FileNotFoundError:
            logger.info("Ключ резервного автозапуска не найден.")
        except Exception as e:
            logger.error(f"Ошибка чтения приостановленного автозапуска: {e}")

        return sorted(apps, key=lambda app: app["name"].lower())

    @classmethod
    def pause_app(cls, app_name: str) -> bool:
        """Перемещает программу из активного реестра в замороженный."""
        cls._ensure_backup_key_exists()
        try:
            winreg = cls._winreg()
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as run_key:
                path, _ = winreg.QueryValueEx(run_key, app_name)

                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.BACKUP_KEY, 0, winreg.KEY_SET_VALUE) as backup_key:
                    winreg.SetValueEx(backup_key, app_name, 0, winreg.REG_SZ, path)

                winreg.DeleteValue(run_key, app_name)

            logger.info(f"Приложение {app_name} приостановлено.")
            return True
        except FileNotFoundError:
            logger.warning(f"Приложение {app_name} не найдено среди активных записей.")
            return False
        except Exception as e:
            logger.error(f"Ошибка при приостановке {app_name}: {e}")
            return False

    @classmethod
    def resume_app(cls, app_name: str) -> bool:
        """Возвращает программу из замороженного состояния в активный автозапуск."""
        try:
            winreg = cls._winreg()
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.BACKUP_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as backup_key:
                path, _ = winreg.QueryValueEx(backup_key, app_name)

                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, cls.RUN_KEY, 0, winreg.KEY_SET_VALUE) as run_key:
                    winreg.SetValueEx(run_key, app_name, 0, winreg.REG_SZ, path)

                winreg.DeleteValue(backup_key, app_name)

            logger.info(f"Приложение {app_name} возобновлено.")
            return True
        except FileNotFoundError:
            logger.warning(f"Приложение {app_name} не найдено среди приостановленных.")
            return False
        except Exception as e:
            logger.error(f"Ошибка при возобновлении {app_name}: {e}")
            return False
