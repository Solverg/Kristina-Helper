"""Модуль автообновления приложения через GitHub Releases."""

from __future__ import annotations

import os
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

GITHUB_REPO = "Solverg/Kristina-Helper"
ASSET_NAME = "KristinaHelper.exe"


def is_frozen() -> bool:
    """Проверяет, запущен ли код как скомпилированный .exe."""
    return getattr(sys, "frozen", False)


def parse_version(v_str: str) -> tuple[int, ...]:
    """Превращает тег 'v1.0.3' в кортеж (1, 0, 3) для сравнения."""
    return tuple(map(int, v_str.lstrip("v").split(".")))


def validate_downloaded_exe(file_path: str) -> None:
    """Базовая проверка, что скачан корректный PE-файл, а не обрыв/HTML."""
    if not os.path.exists(file_path):
        raise RuntimeError("Файл обновления не найден после скачивания.")

    file_size = os.path.getsize(file_path)
    if file_size < 5 * 1024 * 1024:  # 5MB: для нашего exe это аномально мало
        raise RuntimeError("Скачанный файл слишком маленький, обновление прервано или файл поврежден.")

    with open(file_path, "rb") as file_obj:
        magic = file_obj.read(2)

    if magic != b"MZ":
        raise RuntimeError("Скачанный файл не является Windows EXE (поврежден или получен неверный asset).")


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
        raise RuntimeError(f"Проверка обновления не пройдена (код {result.returncode}). {stderr}")


class UpdateChecker(QThread):
    """Фоновый поток для проверки наличия новой версии."""

    update_available = pyqtSignal(str, str)  # версия, download_url

    def __init__(self, current_version: str):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            latest_version_tag = data.get("tag_name", "")
            if not latest_version_tag:
                return

            latest_version = parse_version(latest_version_tag)
            current = parse_version(self.current_version)

            if latest_version > current:
                download_url = None
                for asset in data.get("assets", []):
                    if asset.get("name") == ASSET_NAME:
                        download_url = asset.get("browser_download_url")
                        break

                if download_url:
                    self.update_available.emit(latest_version_tag, download_url)
        except Exception:
            # Игнорируем ошибки сети, чтобы не беспокоить пользователя.
            pass


class UpdateDownloader(QThread):
    """Фоновый поток для скачивания файла с отчетом о прогрессе."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, download_url: str):
        super().__init__()
        self.download_url = download_url

    def run(self):
        temp_download_path = None
        try:
            response = requests.get(self.download_url, stream=True, timeout=15)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0

            if not is_frozen():
                target_exe_path = "KristinaHelper_new.exe"
            else:
                current_exe = sys.executable
                target_exe_path = os.path.join(os.path.dirname(current_exe), "KristinaHelper_new.exe")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".part") as temp_file:
                temp_download_path = temp_file.name

            with open(temp_download_path, "wb") as file_obj:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file_obj.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded_size / total_size) * 100)
                            self.progress.emit(percent)

            if total_size > 0 and downloaded_size < total_size:
                raise RuntimeError("Скачивание прервано: файл получен не полностью.")

            validate_downloaded_exe(temp_download_path)
            run_downloaded_exe_healthcheck(temp_download_path)

            if os.path.exists(target_exe_path):
                os.remove(target_exe_path)
            os.replace(temp_download_path, target_exe_path)

            self.finished.emit(target_exe_path)
        except Exception as exc:
            if temp_download_path and os.path.exists(temp_download_path):
                try:
                    os.remove(temp_download_path)
                except OSError:
                    pass
            self.error.emit(str(exc))


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

        self.lbl_info = QLabel(f"<b>Вышла новая версия {version}</b><br><br>Установить обновление сейчас?")
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

    def start_update(self):
        self.btn_update.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.show()
        self.lbl_info.setText("Скачивание обновления...")

        self.downloader = UpdateDownloader(self.download_url)
        self.downloader.progress.connect(self.progress_bar.setValue)
        self.downloader.finished.connect(self.apply_update)
        self.downloader.error.connect(self.show_error)
        self.downloader.start()

    def show_error(self, _err_msg: str):
        self.lbl_info.setText(f"Ошибка обновления: {_err_msg}")
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("Закрыть")

    def apply_update(self, new_exe_path: str):
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

        # Добавляем taskkill для уверенности и используем полные пути в кавычках
        bat_content = f'''@echo off
chcp 65001 > NUL
timeout /t 3 /nobreak > NUL
taskkill /F /IM "{exe_name}" /T > NUL 2>&1
:loop
del "{current_exe}" > NUL 2>&1
if exist "{current_exe}" (
    timeout /t 1 /nobreak > NUL
    goto loop
)
ren "{new_exe_path}" "{exe_name}"
start "" "{current_exe}"
del "%~f0"
'''
        with open(bat_path, "w", encoding="utf-8") as file_obj:
            file_obj.write(bat_content)

        create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # На Windows для bat-файлов лучше передавать строку, а не список
        subprocess.Popen(f'"{bat_path}"', shell=True, creationflags=create_no_window)

        # Мгновенно завершаем процесс на уровне ОС, чтобы освободить мьютекс
        os._exit(0)
