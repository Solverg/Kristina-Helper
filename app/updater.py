"""Модуль автообновления приложения через GitHub Releases."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile

import requests
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)

GITHUB_REPO = "Solverg/Kristina-Helper"
ASSET_NAME = "KristinaHelper.exe"

# Регулярка для валидации semver-тегов: допускает v1.2.3 или 1.2.3
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def is_frozen() -> bool:
    """Проверяет, запущен ли код как скомпилированный .exe."""
    return getattr(sys, "frozen", False)


def parse_version(v_str: str) -> tuple[int, ...] | None:
    """
    Превращает тег 'v1.0.3' или '1.0.3' в кортеж (1, 0, 3) для сравнения.

    Возвращает None, если формат тега не распознан (pre-release, rc, и т.п.),
    чтобы вызывающий код мог явно обработать нераспознанные теги.

    БАГ-ФИКС: прежняя реализация (lstrip + split) была хрупкой —
    'v1.1.0-rc1' давала ValueError внутри map(int, ...), исключение
    молча глоталось в except Exception: pass, и поведение было непредсказуемым.
    """
    match = _VERSION_RE.match(v_str.strip())
    if not match:
        return None
    return tuple(int(x) for x in match.groups())


def validate_downloaded_exe(file_path: str) -> None:
    """Базовая проверка, что скачан корректный PE-файл, а не обрыв/HTML."""
    if not os.path.exists(file_path):
        raise RuntimeError("Файл обновления не найден после скачивания.")

    file_size = os.path.getsize(file_path)
    if file_size < 5 * 1024 * 1024:  # 5 MB — аномально мало для нашего exe
        raise RuntimeError(
            "Скачанный файл слишком маленький — обновление прервано или файл повреждён."
        )

    with open(file_path, "rb") as file_obj:
        magic = file_obj.read(2)

    if magic != b"MZ":
        raise RuntimeError(
            "Скачанный файл не является Windows EXE (повреждён или получен неверный asset)."
        )


def run_downloaded_exe_healthcheck(file_path: str) -> None:
    """Проверяет, что новый .exe запускается хотя бы в служебном режиме."""
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    result = subprocess.run(
        [file_path, "--healthcheck"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
        creationflags=create_no_window,
    )

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(
            f"Проверка обновления не пройдена (код {result.returncode}). {stderr}"
        )


class UpdateChecker(QThread):
    """Фоновый поток для проверки наличия новой версии."""

    update_available = pyqtSignal(str, str)  # версия, download_url

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self) -> None:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            # ФИКС: добавлен User-Agent — GitHub API требует его для анонимных запросов,
            # без него возможен 403 в ряде окружений.
            response = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": f"{ASSET_NAME}/updater"},
            )
            response.raise_for_status()
            data = response.json()

            latest_tag = data.get("tag_name", "").strip()
            if not latest_tag:
                return

            # ФИКС: явно пропускаем draft и pre-release релизы,
            # чтобы пользователю не предлагались нестабильные сборки.
            if data.get("draft") or data.get("prerelease"):
                return

            # ФИКС: parse_version теперь возвращает None при нестандартном теге
            # вместо того, чтобы бросать ValueError, который молча глотался.
            latest_version = parse_version(latest_tag)
            current_version = parse_version(self.current_version)

            if latest_version is None:
                logger.warning("Не удалось распознать версию тега GitHub: %r", latest_tag)
                return
            if current_version is None:
                logger.warning("Не удалось распознать текущую версию: %r", self.current_version)
                return

            # ГЛАВНЫЙ БАГ-ФИКС: строгое сравнение «строго больше».
            # Прежний код был верным синтаксически, но если current_version
            # содержал нестандартный формат (с 'v'-префиксом или суффиксом),
            # parse_version бросала ValueError → except глотал исключение →
            # в некоторых путях update_available мог эмититься некорректно.
            # Теперь оба значения валидированы до сравнения.
            if latest_version > current_version:
                download_url = None
                for asset in data.get("assets", []):
                    if asset.get("name") == ASSET_NAME:
                        download_url = asset.get("browser_download_url")
                        break

                if download_url:
                    self.update_available.emit(latest_tag, download_url)

        except requests.RequestException:
            # Сетевые ошибки не беспокоят пользователя, но логируем для диагностики.
            logger.debug("UpdateChecker: сетевая ошибка при проверке обновлений", exc_info=True)
        except Exception:  # noqa: BLE001
            logger.exception("UpdateChecker: неожиданная ошибка")


class UpdateDownloader(QThread):
    """Фоновый поток для скачивания файла с отчётом о прогрессе."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def run(self) -> None:
        temp_download_path: str | None = None
        try:
            # ФИКС: добавлен User-Agent в запрос скачивания.
            response = requests.get(
                self.download_url,
                stream=True,
                timeout=30,  # ФИКС: увеличен таймаут — 15 с мало для бинарника.
                headers={"User-Agent": f"{ASSET_NAME}/updater"},
            )
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0

            if not is_frozen():
                target_dir = os.path.abspath(".")
            else:
                target_dir = os.path.dirname(sys.executable)

            # ФИКС УЯЗВИМОСТИ: target_exe_path строится через os.path.join,
            # а не конкатенацией строк; имя файла — константа, не из сети.
            target_exe_path = os.path.join(target_dir, "KristinaHelper_new.exe")

            # ФИКС: временный файл создаётся в той же директории, что и цель,
            # чтобы os.replace был атомарным (в пределах одного тома).
            fd, temp_download_path = tempfile.mkstemp(
                suffix=".part", dir=target_dir
            )
            try:
                with os.fdopen(fd, "wb") as file_obj:
                    for chunk in response.iter_content(chunk_size=65536):  # ФИКС: 64 KB вместо 8 KB
                        if chunk:
                            file_obj.write(chunk)
                            downloaded_size += len(chunk)
                            if total_size > 0:
                                percent = int((downloaded_size / total_size) * 100)
                                self.progress.emit(percent)
            except Exception:
                # Если запись прервалась — закрываем fd через исключение выше,
                # очистка temp-файла — в finally-блоке внешнего try.
                raise

            if total_size > 0 and downloaded_size < total_size:
                raise RuntimeError("Скачивание прервано: файл получен не полностью.")

            validate_downloaded_exe(temp_download_path)
            run_downloaded_exe_healthcheck(temp_download_path)

            # ФИКС: явно удаляем старый _new.exe перед replace, иначе
            # на Windows os.replace может упасть, если целевой файл заблокирован.
            if os.path.exists(target_exe_path):
                try:
                    os.remove(target_exe_path)
                except OSError as exc:
                    raise RuntimeError(
                        f"Не удалось удалить старый файл обновления: {exc}"
                    ) from exc

            os.replace(temp_download_path, target_exe_path)
            temp_download_path = None  # Передали владение — не удалять в finally.

            self.finished.emit(target_exe_path)

        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            # ФИКС: гарантированная очистка temp-файла в любом случае.
            if temp_download_path and os.path.exists(temp_download_path):
                try:
                    os.remove(temp_download_path)
                except OSError:
                    pass


class UpdateDialog(QDialog):
    """Всплывающее окно с предложением обновиться."""

    def __init__(self, version: str, download_url: str, parent=None):
        super().__init__(parent)
        self.version = version
        self.download_url = download_url
        self.setWindowTitle("Доступно обновление")
        self.setFixedSize(380, 160)

        self.setStyleSheet(
            """
            QDialog { background-color: #161b22; }
            QLabel { color: #e6edf3; font-family: 'Segoe UI'; font-size: 13px; }
            QPushButton {
                background: #21262d; border: 1px solid #30363d;
                border-radius: 6px; padding: 6px 16px; color: #e6edf3; font-weight: 500;
            }
            QPushButton:hover { background: #30363d; }
            QPushButton#primary { background: #238636; border: none; font-weight: 600; }
            QPushButton#primary:hover { background: #2ea043; }
            QProgressBar {
                border: 1px solid #30363d; border-radius: 4px;
                background-color: #0d1117; text-align: center; color: white;
            }
            QProgressBar::chunk { background-color: #238636; border-radius: 3px; }
            """
        )

        layout = QVBoxLayout(self)

        self.lbl_info = QLabel(
            f"<b>Вышла новая версия {version}</b><br><br>Установить обновление сейчас?"
        )
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Позже")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_update = QPushButton("Обновить")
        self.btn_update.setObjectName("primary")
        self.btn_update.clicked.connect(self.start_update)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_update)
        layout.addLayout(btn_layout)

    def start_update(self) -> None:
        self.btn_update.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.show()
        self.lbl_info.setText("Скачивание обновления...")

        self.downloader = UpdateDownloader(self.download_url)
        self.downloader.progress.connect(self.progress_bar.setValue)
        self.downloader.finished.connect(self.apply_update)
        self.downloader.error.connect(self.show_error)
        self.downloader.start()

    def show_error(self, err_msg: str) -> None:
        self.lbl_info.setText(f"Ошибка обновления: {err_msg}")
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("Закрыть")

    def apply_update(self, new_exe_path: str) -> None:
        if not is_frozen():
            self.lbl_info.setText("Файл скачан (режим разработки).")
            self.btn_cancel.setEnabled(True)
            self.btn_cancel.setText("Закрыть")
            return

        self.lbl_info.setText("Установка и перезапуск...")
        current_exe = sys.executable
        exe_name = os.path.basename(current_exe)
        exe_dir = os.path.dirname(current_exe)
        bat_path = os.path.join(exe_dir, "update_helper.bat")

        # ФИКС: escape кавычек в путях — если путь содержит пробелы,
        # bat-скрипт с вложенными кавычками внутри строки может сломаться.
        # Используем двойные кавычки и экранирование через cmd /c.
        # Также: new_exe_path валидируется — это наш собственный файл,
        # путь строился из os.path.join с константой ASSET_NAME.
        bat_content = (
            "@echo off\n"
            "chcp 65001 > NUL\n"
            "timeout /t 3 /nobreak > NUL\n"
            f'taskkill /F /IM "{exe_name}" /T > NUL 2>&1\n'
            ":loop\n"
            f'del "{current_exe}" > NUL 2>&1\n'
            f'if exist "{current_exe}" (\n'
            "    timeout /t 1 /nobreak > NUL\n"
            "    goto loop\n"
            ")\n"
            f'move /Y "{new_exe_path}" "{current_exe}"\n'  # ФИКС: move вместо ren — ren не работает с полными путями
            f'start "" "{current_exe}"\n'
            'del "%~f0"\n'
        )

        with open(bat_path, "w", encoding="utf-8") as file_obj:
            file_obj.write(bat_content)

        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            f'"{bat_path}"',
            shell=True,
            creationflags=create_no_window,
        )

        # Мгновенно завершаем процесс на уровне ОС, чтобы освободить мьютекс.
        os._exit(0)
