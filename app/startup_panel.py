"""
Kristina Helper — панель управления автозагрузкой сторонних приложений.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.startup_manager import StartupAppsManager, StartupItem


class StartupPanel(QWidget):
    """Панель для pause/resume приложений из автозагрузки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apps: list[StartupItem] = []
        self._is_admin = False
        self._build_ui()
        self._load_apps()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("🚀 Автозагрузка")
        title.setObjectName("section_title")
        layout.addWidget(title)

        subtitle = QLabel("Управление автозапуском: HKCU/HKLM и папки Startup")
        subtitle.setObjectName("section_subtitle")
        layout.addWidget(subtitle)

        self._warning_label = QLabel("⚠ Некоторые приложения нельзя изменить без прав Администратора.")
        self._warning_label.setStyleSheet("color: #f0883e; font-weight: 600;")
        self._warning_label.setVisible(False)
        layout.addWidget(self._warning_label)

        controls = QHBoxLayout()
        controls.addStretch()

        self._btn_refresh = QPushButton("↻ Обновить список")
        self._btn_refresh.setObjectName("refresh_btn")
        self._btn_refresh.clicked.connect(self._load_apps)
        controls.addWidget(self._btn_refresh)

        layout.addLayout(controls)

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["Приложение", "Источник", "Статус", "Путь/ключ", "Действие"])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table)

    def _load_apps(self):
        self._apps = StartupAppsManager.get_apps()
        self._is_admin = StartupAppsManager.is_admin()
        self._warning_label.setVisible(not self._is_admin)

        if not self._apps:
            self._table.clearSpans()
            self._table.setRowCount(1)
            self._table.setColumnCount(5)
            self._table.setHorizontalHeaderLabels(["Приложение", "Источник", "Статус", "Путь/ключ", "Действие"])
            empty_item = QTableWidgetItem("Нет элементов автозагрузки")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(0, 0, empty_item)
            self._table.setSpan(0, 0, 1, 5)
            return

        self._table.clearSpans()
        self._table.setRowCount(len(self._apps))

        for row, item in enumerate(self._apps):
            self._table.setItem(row, 0, QTableWidgetItem(item.name))
            self._table.setItem(row, 1, QTableWidgetItem(item.source))

            status_text = "● Активно" if item.status == "active" else "● Остановлено"
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor("#3fb950" if item.status == "active" else "#f0883e"))
            self._table.setItem(row, 2, status_item)

            self._table.setItem(row, 3, QTableWidgetItem(item.target_path))

            action_btn = QPushButton("Приостановить" if item.status == "active" else "Возобновить")
            action_btn.setObjectName("refresh_btn" if item.status == "active" else "action_btn")
            action_btn.clicked.connect(lambda _, startup_item=item: self._on_toggle(startup_item))

            needs_admin = item.source in {"HKLM", "FOLDER_SYSTEM"} and not self._is_admin
            if needs_admin:
                action_btn.setEnabled(False)
                action_btn.setToolTip("Требуются права Администратора")

            self._table.setCellWidget(row, 4, action_btn)

    def _on_toggle(self, item: StartupItem):
        success = StartupAppsManager.toggle_app(item)
        if not success:
            QMessageBox.warning(self, "Автозагрузка", "Не удалось изменить статус автозагрузки.")
            return

        self._load_apps()
