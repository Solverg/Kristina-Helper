# Kristina Helper 🛡️

Нативное Windows 11 приложение на PyQt6 для мониторинга и блокировки процессов с AI-чатом на Gemini.

---

## Структура проекта

```
kristina_helper/
│
├── main.py                    # Точка входа
├── requirements.txt
│
├── assets/
│   └── avatar.png             # Иконка / аватар Кристины
│
└── app/
    ├── __init__.py
    ├── main_window.py         # Главное окно (QMainWindow)
    ├── styles.py              # Глобальный QSS stylesheet
    ├── process_manager.py     # Ядро: сканирование и завершение процессов
    ├── processes_panel.py     # UI: таблица процессов + статистика
    ├── ai_chat.py             # UI: чат с Gemini API
    ├── settings_panel.py      # UI: панель настроек
    ├── settings.py            # Менеджер настроек (JSON)
    ├── autostart.py           # Автозапуск через Windows Registry
    └── tray.py                # Системный трей
```

---

## Быстрый старт

```bash
# 1. Установить зависимости
pip install -r requirements.txt

# 2. Запустить
python main.py
```

---

## Архитектура

### ProcessManager (app/process_manager.py)
- Использует `psutil` для получения списка процессов
- Хранит правила блокировки в `~/.kristina_helper/blocked.json`
- `QTimer` каждые N секунд вызывает `scan_and_enforce()`
- При обнаружении заблокированного процесса — `proc.terminate()`
- Сигналы Qt: `processes_updated`, `process_killed`, `stats_updated`

### MainWindow (app/main_window.py)
- `QStackedWidget` — 3 страницы (Процессы / AI-чат / Настройки)
- Кастомный Sidebar с круглым аватаром
- Передаёт сигнал `ask_ai_about` из ProcessesPanel → AIChatWidget

### AIChatWidget (app/ai_chat.py)
- Gemini 2.5 Flash-Lite через REST API (`urllib`, без сторонних HTTP-библиотек)
- `GeminiWorker(QThread)` — запросы в фоне, не блокируют UI
- История диалога передаётся в каждый запрос (контекст)
- System prompt: Кристина знает о процессах Windows

### AutostartManager (app/autostart.py)
- `winreg` — запись в `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
- Поддерживает режим разработки (python main.py) и PyInstaller сборку

### TrayManager (app/tray.py)
- `QSystemTrayIcon` с контекстным меню
- `closeEvent` в MainWindow сворачивает в трей вместо выхода

---

## Сборка в .exe (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=assets/avatar.png --name="KristinaHelper" main.py
```

---

## Конфигурация

Все данные хранятся в `%USERPROFILE%\.kristina_helper\`:
- `settings.json` — настройки приложения
- `blocked.json` — список заблокированных процессов

---

## Требования

- Windows 10/11
- Python 3.11+
- PyQt6 >= 6.6
- psutil >= 5.9
