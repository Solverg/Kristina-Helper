"""
Kristina Helper — панель управления автозагрузкой сторонних приложений.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from app.startup_manager import StartupAppsManager


class StartupPanel(QWidget):
    """Панель для pause/resume приложений из автозагрузки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_apps()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("🚀 Автозагрузка")
        title.setObjectName("section_title")
        layout.addWidget(title)

        subtitle = QLabel("Управление автозапуском сторонних приложений в HKCU")
        subtitle.setObjectName("section_subtitle")
        layout.addWidget(subtitle)

        controls = QHBoxLayout()
        controls.addStretch()

        self._btn_refresh = QPushButton("↻ Обновить список")
        self._btn_refresh.setObjectName("refresh_btn")
        self._btn_refresh.clicked.connect(self._load_apps)
        controls.addWidget(self._btn_refresh)

        layout.addLayout(controls)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Приложение", "Статус", "Путь", "Действие"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(False)
        layout.addWidget(self._table)

    def _load_apps(self):
        try:
            apps = StartupAppsManager.get_apps()
        except ModuleNotFoundError:
            self._show_registry_error()
            return

        self._table.setRowCount(len(apps))

        for row, app in enumerate(apps):
            name_item = QTableWidgetItem(app["name"])
            status_text = "Активно" if app["status"] == "active" else "Остановлено"
            status_item = QTableWidgetItem(status_text)
            path_item = QTableWidgetItem(app["path"])

            status_color = "#3fb950" if app["status"] == "active" else "#f0883e"
            status_item.setData(Qt.ItemDataRole.UserRole, app["status"])
            status_item.setToolTip(f"Текущий статус: {status_text}")
            status_item.setText(f"● {status_text}")
            status_item.setForeground(QColor(status_color))

            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, status_item)
            self._table.setItem(row, 2, path_item)

            action_btn = QPushButton("Приостановить" if app["status"] == "active" else "Возобновить")
            action_btn.setObjectName("action_btn" if app["status"] == "paused" else "refresh_btn")
            action_btn.clicked.connect(
                lambda _, app_name=app["name"], is_active=app["status"] == "active": self._toggle_app(app_name, is_active)
            )
            self._table.setCellWidget(row, 3, action_btn)

        if not apps:
            self._table.setRowCount(1)
            empty_item = QTableWidgetItem("Нет приложений в автозагрузке")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(0, 0, empty_item)
            self._table.setSpan(0, 0, 1, 4)

    def _toggle_app(self, app_name: str, is_active: bool):
        try:
            success = StartupAppsManager.pause_app(app_name) if is_active else StartupAppsManager.resume_app(app_name)
        except ModuleNotFoundError:
            self._show_registry_error()
            return

        if not success:
            action = "приостановить" if is_active else "возобновить"
            QMessageBox.warning(self, "Автозагрузка", f"Не удалось {action} '{app_name}'.")
            return

        self._load_apps()

    def _show_registry_error(self):
        QMessageBox.warning(
            self,
            "Автозагрузка",
            "Управление автозагрузкой доступно только в Windows (winreg недоступен).",
        )
