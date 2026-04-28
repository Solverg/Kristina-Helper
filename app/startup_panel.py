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

        # Явно убираем виджеты из ячеек перед пересозданием строк
        self._table.clearContents()
        self._table.clearSpans()

        if not self._apps:
            self._table.setRowCount(1)
            self._table.setColumnCount(5)
            self._table.setHorizontalHeaderLabels(["Приложение", "Источник", "Статус", "Путь/ключ", "Действие"])
            empty_item = QTableWidgetItem("Нет элементов автозагрузки")
            empty_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(0, 0, empty_item)
            self._table.setSpan(0, 0, 1, 5)
            return

        self._table.setRowCount(len(self._apps))

        for row, item in enumerate(self._apps):
            self._table.setRowHeight(row, 48)
            self._table.setItem(row, 0, QTableWidgetItem(item.name))
            self._table.setItem(row, 1, QTableWidgetItem(item.source))

            status_text = "● Активно" if item.status == "active" else "● Остановлено"
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor("#3fb950" if item.status == "active" else "#f0883e"))
            self._table.setItem(row, 2, status_item)

            self._table.setItem(row, 3, QTableWidgetItem(item.target_path))

            needs_admin = item.source in {"HKLM", "FOLDER_SYSTEM"} and not self._is_admin
            is_active = item.status == "active"

            if is_active:
                btn_text = "⏸ Приостановить"
                btn_style = (
                    "QPushButton {"
                    "  background-color: #21262d;"
                    "  color: #e6edf3;"
                    "  border: 1px solid #30363d;"
                    "  border-radius: 6px;"
                    "  padding: 5px 14px;"
                    "  font-size: 11px;"
                    "}"
                    "QPushButton:hover { background-color: #30363d; border-color: #8b949e; }"
                    "QPushButton:disabled { color: #484f58; border-color: #21262d; }"
                )
            else:
                btn_text = "▶ Возобновить"
                btn_style = (
                    "QPushButton {"
                    "  background-color: #238636;"
                    "  color: #ffffff;"
                    "  border: none;"
                    "  border-radius: 6px;"
                    "  padding: 5px 14px;"
                    "  font-size: 11px;"
                    "  font-weight: 600;"
                    "}"
                    "QPushButton:hover { background-color: #2ea043; }"
                    "QPushButton:disabled { background-color: #1a3a20; color: #484f58; }"
                )

            action_btn = QPushButton(btn_text)
            action_btn.setMinimumHeight(30)
            action_btn.setMinimumWidth(132)
            action_btn.setStyleSheet(btn_style)
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.clicked.connect(lambda _, startup_item=item: self._on_toggle(startup_item))

            if needs_admin:
                action_btn.setEnabled(False)
                action_btn.setToolTip("Требуются права Администратора")

            # Враппер с отступами: без него кнопка растягивается на всю ячейку
            # и может не получить корректный фон через наследование QTableWidget
            cell_widget = QWidget()
            cell_widget.setStyleSheet("background: transparent;")
            cell_layout = QHBoxLayout(cell_widget)
            cell_layout.setContentsMargins(6, 4, 6, 4)
            cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell_layout.addWidget(action_btn)
            self._table.setCellWidget(row, 4, cell_widget)

    def _on_toggle(self, item: StartupItem):
        needs_admin = item.source in {"HKLM", "FOLDER_SYSTEM"} and not self._is_admin
        if needs_admin:
            QMessageBox.warning(
                self,
                "Автозагрузка",
                f"Для изменения «{item.name}» требуются права Администратора.\n"
                "Перезапустите Kristina Helper от имени администратора."
            )
            return

        success = StartupAppsManager.toggle_app(item)
        if not success:
            QMessageBox.warning(
                self,
                "Автозагрузка",
                f"Не удалось изменить статус автозагрузки для «{item.name}».\n"
                "Подробности смотрите в журнале приложения."
            )
            return

        self._load_apps()
