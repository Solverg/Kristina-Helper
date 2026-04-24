"""
Kristina Helper — менеджер настроек.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".kristina_helper", "settings.json")

DEFAULTS = {
    "gemini_api_key": "",
    "gemini_model": "gemini-3-flash-preview",
    "scan_interval_sec": 5,
    "autostart": False,
    "minimize_to_tray": True,
    "show_notifications": True,
}


class SettingsManager:
    """Простой key-value store для настроек приложения."""

    def __init__(self):
        self._data: dict = dict(DEFAULTS)
        self._load()

    def _load(self):
        try:
            if os.path.exists(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self._data.update(loaded)
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}")

    def get(self, key: str, default=None):
        return self._data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key: str, value):
        self._data[key] = value
        self.save()
