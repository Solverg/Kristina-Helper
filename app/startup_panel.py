"""
Kristina Helper — панель управления автозагрузкой сторонних приложений.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.startup_manager import StartupAppsManager, StartupItem

# Минимальная высота строки — вмещает кнопку + вертикальные отступы
_ROW_MIN_H = 40
# Горизонтальный padding внутри виджет-ячеек (contentsMargins * 2)
_CELL_H_PAD = 16

# Доля ширины таблицы для каждой колонки (сумма = 1.0, кнопка задаётся отдельно)
# [Приложение, Источник, Статус, Путь]
_COL_RATIOS = (0.22, 0.09, 0.12, 0.57)


class StartupPanel(QWidget):
    """Панель для pause/resume приложений из автозагрузки."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apps: list[StartupItem] = []
        self._is_admin = False
        self._initial_layout_done = False

        # Debounce-таймер: пересчёт высот строк после ресайза любой колонки
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(60)
        self._resize_timer.timeout.connect(self._recalc_row_heights)

        self._build_ui()
        self._load_apps()

    # ─────────────────────────────────────────────────────────────────────────
    # Построение UI
    # ─────────────────────────────────────────────────────────────────────────

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

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #21262d; max-height: 1px; margin: 4px 0;")
        layout.addWidget(sep)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self._lbl_count = QLabel("Приложений: 0")
        self._lbl_count.setStyleSheet("color: #8b949e; font-size: 13px;")
        controls_row.addWidget(self._lbl_count)
        controls_row.addStretch()

        self._btn_refresh = QPushButton("↻  Обновить")
        self._btn_refresh.setObjectName("refresh_btn")
        self._btn_refresh.clicked.connect(self._load_apps)
        controls_row.addWidget(self._btn_refresh)

        layout.addLayout(controls_row)

        # ── Таблица ───────────────────────────────────────────────────────────
        self._table = QTreeWidget()
        self._table.setColumnCount(5)
        self._table.setHeaderLabels(["Приложение", "Источник", "Статус", "Путь / ключ", "Действие"])

        header = self._table.header()
        # Все колонки — интерактивные (пользователь двигает границы мышью).
        # Колонка кнопки — Fixed: ширина задаётся программно и не меняется.
        for col in range(4):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(50)

        # Ширина колонки «Действие» считается один раз по sizeHint кнопки
        self._btn_col_w = self._calc_btn_col_width()
        self._table.setColumnWidth(4, self._btn_col_w)

        # Остальные ширины — пропорциональные; выставляются в showEvent / resizeEvent
        # чтобы знать реальную ширину виджета.

        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setRootIsDecorated(False)
        self._table.setUniformRowHeights(False)   # ВАЖНО для индивидуальной высоты строк
        self._table.setStyleSheet("""
            QTreeWidget {
                gridline-color: rgba(139, 148, 158, 0.18);
            }
            QTreeWidget::item {
                border-bottom: 1px solid rgba(139, 148, 158, 0.14);
                padding: 0px 8px;
            }
            QHeaderView::section {
                border-right: 1px solid rgba(139, 148, 158, 0.16);
                padding: 4px 8px;
            }
        """)

        header.sectionResized.connect(self._on_section_resized)

        layout.addWidget(self._table)

        self._empty_label = QLabel(
            "Элементы автозагрузки не найдены.\n"
            "Нажмите «Обновить» или запустите с правами Администратора."
        )
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #484f58; font-size: 14px; padding: 40px;")
        layout.addWidget(self._empty_label)

    # ─────────────────────────────────────────────────────────────────────────
    # Адаптация ширин колонок к размеру виджета
    # ─────────────────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_layout_done:
            self._initial_layout_done = True
            self._distribute_column_widths()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # При изменении размера окна перераспределяем ширины только если
        # пользователь ещё не двигал колонки вручную (флаг сбрасывается при
        # ручном ресайзе через _on_section_resized).
        if self._initial_layout_done:
            self._distribute_column_widths()

    def _distribute_column_widths(self):
        """Распределяет ширины колонок 0–3 пропорционально доступной ширине."""
        total = self._table.viewport().width()
        if total <= 0:
            return

        # Доступная ширина для колонок 0–3 (за вычетом кнопки и полосы прокрутки)
        scrollbar_w = self._table.verticalScrollBar().width() if \
            self._table.verticalScrollBar().isVisible() else 0
        available = max(total - self._btn_col_w - scrollbar_w, 200)

        for col, ratio in enumerate(_COL_RATIOS):
            self._table.setColumnWidth(col, max(int(available * ratio), 50))

        # После изменения ширин пересчитываем высоты строк
        self._resize_timer.start()

    # ─────────────────────────────────────────────────────────────────────────
    # Загрузка данных
    # ─────────────────────────────────────────────────────────────────────────

    def _load_apps(self):
        self._apps = StartupAppsManager.get_apps()
        self._is_admin = StartupAppsManager.is_admin()
        self._warning_label.setVisible(not self._is_admin)
        self._table.clear()

        if not self._apps:
            self._table.setVisible(False)
            self._empty_label.setVisible(True)
            self._lbl_count.setText("Приложений: 0")
            return

        self._table.setVisible(True)
        self._empty_label.setVisible(False)
        self._lbl_count.setText(f"Приложений: {len(self._apps)}")

        for app_item in sorted(self._apps, key=lambda a: a.name.lower()):
            self._add_row(app_item)

        self._recalc_row_heights()

    def _add_row(self, app_item: StartupItem):
        is_active = app_item.status == "active"
        needs_admin = app_item.source in {"HKLM", "FOLDER_SYSTEM"} and not self._is_admin
        status_text = "● Активно" if is_active else "● Остановлено"

        # Все колонки с текстом — пустые; содержимое через setItemWidget
        tree_item = QTreeWidgetItem(["", "", "", "", ""])
        tree_item.setData(0, Qt.ItemDataRole.UserRole, app_item)
        self._table.addTopLevelItem(tree_item)

        # Колонка 0 — Приложение
        self._table.setItemWidget(tree_item, 0,
            self._build_text_cell(app_item.name, "#e6edf3", bold=True,
                                  dimmed=needs_admin))

        # Колонка 1 — Источник
        self._table.setItemWidget(tree_item, 1,
            self._build_text_cell(app_item.source, "#8b949e",
                                  dimmed=needs_admin))

        # Колонка 2 — Статус
        status_color = "#484f58" if needs_admin else ("#3fb950" if is_active else "#f0883e")
        self._table.setItemWidget(tree_item, 2,
            self._build_text_cell(status_text, status_color))

        # Колонка 3 — Путь (с переносом)
        self._table.setItemWidget(tree_item, 3,
            self._build_text_cell(app_item.target_path, "#8b949e",
                                  font_size=12, wrap=True,
                                  tooltip=app_item.target_path,
                                  dimmed=needs_admin))

        # Колонка 4 — Действие
        btn = self._build_action_button(app_item, is_active, needs_admin)
        btn_wrapper = QWidget()
        btn_wrapper.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_wrapper)
        btn_layout.setContentsMargins(6, 4, 6, 4)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(btn)
        self._table.setItemWidget(tree_item, 4, btn_wrapper)

    # ─────────────────────────────────────────────────────────────────────────
    # Построители ячеек
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_text_cell(
        text: str,
        color: str = "#e6edf3",
        bold: bool = False,
        font_size: int = 13,
        wrap: bool = False,
        tooltip: str = "",
        dimmed: bool = False,
    ) -> QWidget:
        cell = QWidget()
        cell.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(cell)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(0)

        lbl = QLabel(text)
        lbl.setWordWrap(wrap)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        actual_color = "#484f58" if dimmed else color
        weight = "600;" if bold else "400;"
        lbl.setStyleSheet(
            f"color: {actual_color}; font-size: {font_size}px; font-weight: {weight}"
        )
        lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if tooltip:
            lbl.setToolTip(tooltip)

        lay.addWidget(lbl)
        return cell

    # ─────────────────────────────────────────────────────────────────────────
    # Пересчёт высот строк
    # ─────────────────────────────────────────────────────────────────────────

    def _on_section_resized(self, _logical: int, _old: int, _new: int):
        self._resize_timer.start()

    def _recalc_row_heights(self):
        """
        Для каждой строки берём максимальную необходимую высоту среди всех
        виджет-ячеек и задаём её через setFixedHeight — Qt знает точный размер
        и не добавляет буфер внизу (в отличие от setMinimumHeight).
        """
        root = self._table.invisibleRootItem()
        for i in range(root.childCount()):
            tree_item = root.child(i)
            needed = _ROW_MIN_H

            for col in range(4):  # кнопку не трогаем
                w = self._table.itemWidget(tree_item, col)
                if w is None:
                    continue
                lbl: QLabel | None = w.findChild(QLabel)
                if lbl is None:
                    continue

                col_w = max(self._table.columnWidth(col) - _CELL_H_PAD, 40)
                if lbl.wordWrap() and lbl.hasHeightForWidth():
                    h = lbl.heightForWidth(col_w) + _CELL_H_PAD
                else:
                    h = lbl.sizeHint().height() + _CELL_H_PAD

                needed = max(needed, h)

            # setFixedHeight даёт Qt точный размер — нет лишнего буфера внизу
            for col in range(5):
                w = self._table.itemWidget(tree_item, col)
                if w is not None:
                    w.setFixedHeight(needed)

        # updateGeometries() применяет изменения синхронно, без отложенного буфера
        self._table.updateGeometries()

    # ─────────────────────────────────────────────────────────────────────────
    # Кнопка действия
    # ─────────────────────────────────────────────────────────────────────────

    def _build_action_button(self, item: StartupItem, is_active: bool, needs_admin: bool) -> QPushButton:
        if is_active:
            btn_text = "⏸  Приостановить"
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
            btn_text = "▶  Возобновить"
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

        btn = QPushButton(btn_text)
        btn.setMinimumHeight(30)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(btn_style)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _, startup_item=item: self._on_toggle(startup_item))

        if needs_admin:
            btn.setEnabled(False)
            btn.setToolTip("Требуются права Администратора")

        return btn

    @staticmethod
    def _calc_btn_col_width() -> int:
        """
        Ширина колонки «Действие» = sizeHint самой широкой кнопки + отступы обёртки.
        Вычисляем через dummy-виджет до показа окна.
        """
        dummy = QPushButton("⏸  Приостановить")
        dummy.setStyleSheet("padding: 5px 14px; font-size: 11px;")
        return dummy.sizeHint().width() + 24   # 24 = contentsMargins(6,4,6,4) * 2

    # ─────────────────────────────────────────────────────────────────────────
    # Обработка toggle
    # ─────────────────────────────────────────────────────────────────────────

    def _on_toggle(self, item: StartupItem):
        needs_admin = item.source in {"HKLM", "FOLDER_SYSTEM"} and not self._is_admin
        if needs_admin:
            QMessageBox.warning(
                self,
                "Автозагрузка",
                f"Для изменения «{item.name}» требуются права Администратора.\n"
                "Перезапустите Kristina Helper от имени администратора.",
            )
            return

        success = StartupAppsManager.toggle_app(item)
        if not success:
            QMessageBox.warning(
                self,
                "Автозагрузка",
                f"Не удалось изменить статус автозагрузки для «{item.name}».\n"
                "Подробности смотрите в журнале приложения.",
            )
            return

        self._load_apps()
