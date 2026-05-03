"""
Kristina Helper — панель заблокированных процессов.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QAbstractItemView, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from app.process_manager import ProcessManager


class BlockedPanel(QWidget):
    """
    Панель со списком заблокированных процессов (правил блокировки).
    """

    def __init__(self, process_manager: ProcessManager, parent=None):
        super().__init__(parent)
        self.pm = process_manager
        self._build_ui()
        self._connect_signals()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Заголовок ────────────────────────────────────────────────────────
        title = QLabel("🚫 Заблокированные")
        title.setObjectName("section_title")
        layout.addWidget(title)

        subtitle = QLabel(
            "Процессы из этого списка будут автоматически завершаться при обнаружении."
        )
        subtitle.setStyleSheet("color: #8b949e; font-size: 13px;")
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #21262d; max-height: 1px; margin: 4px 0;")
        layout.addWidget(sep)

        # ── Панель управления ────────────────────────────────────────────────
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self._lbl_count = QLabel("Правил: 0")
        self._lbl_count.setStyleSheet("color: #8b949e; font-size: 13px;")

        controls_row.addWidget(self._lbl_count)
        controls_row.addStretch()

        self._btn_refresh = QPushButton("↻  Обновить")
        self._btn_refresh.setObjectName("refresh_btn")
        self._btn_refresh.clicked.connect(self._refresh)

        self._btn_toggle = QPushButton("⏸  Отключить")
        self._btn_toggle.setObjectName("action_btn")
        self._btn_toggle.setEnabled(False)
        self._btn_toggle.clicked.connect(self._toggle_selected)

        self._btn_remove = QPushButton("🗑  Удалить правило")
        self._btn_remove.setObjectName("kill_btn")
        self._btn_remove.setEnabled(False)
        self._btn_remove.clicked.connect(self._remove_selected)

        controls_row.addWidget(self._btn_refresh)
        controls_row.addWidget(self._btn_toggle)
        controls_row.addWidget(self._btn_remove)

        layout.addLayout(controls_row)

        # ── Таблица ──────────────────────────────────────────────────────────
        self._table = QTreeWidget()
        self._table.setColumnCount(3)
        self._table.setHeaderLabels(["Имя процесса", "Статус правила", "Завершено раз"])
        self._table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setRootIsDecorated(False)
        self._table.setStyleSheet("""
            QTreeWidget {
                gridline-color: rgba(139, 148, 158, 0.18);
            }
            QTreeWidget::item {
                border-bottom: 1px solid rgba(139, 148, 158, 0.14);
                padding: 6px 8px;
            }
            QHeaderView::section {
                border-right: 1px solid rgba(139, 148, 158, 0.16);
            }
        """)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self._table)

        # ── Пустое состояние ─────────────────────────────────────────────────
        self._empty_label = QLabel("Список заблокированных процессов пуст.\nДобавьте процессы через панель «Процессы».")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #484f58; font-size: 14px; padding: 40px;")
        layout.addWidget(self._empty_label)

    def _connect_signals(self):
        self.pm.stats_updated.connect(lambda _: self._refresh())

    def _refresh(self):
        rules = list(self.pm.block_rules.values())
        self._table.clear()

        if not rules:
            self._table.setVisible(False)
            self._empty_label.setVisible(True)
            self._lbl_count.setText("Правил: 0")
            return

        self._table.setVisible(True)
        self._empty_label.setVisible(False)
        self._lbl_count.setText(f"Правил: {len(rules)}")

        for rule in sorted(rules, key=lambda r: r.name.lower()):
            status_text = "✅ Активно" if rule.enabled else "⏸ Отключено"
            item = QTreeWidgetItem([
                rule.name,
                status_text,
                str(rule.kill_count),
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, rule.name)

            if not rule.enabled:
                for col in range(3):
                    item.setForeground(col, QColor("#484f58"))
            else:
                item.setForeground(1, QColor("#3fb950"))

            self._table.addTopLevelItem(item)

        self._on_selection_changed()

    def _on_selection_changed(self):
        has_sel = bool(self._table.selectedItems())
        self._btn_remove.setEnabled(has_sel)
        self._btn_toggle.setEnabled(has_sel)

        if has_sel:
            name = self._table.selectedItems()[0].data(0, Qt.ItemDataRole.UserRole)
            rule = self.pm.block_rules.get((name or "").lower())
            if rule:
                if rule.enabled:
                    self._btn_toggle.setText("⏸  Отключить")
                else:
                    self._btn_toggle.setText("▶  Включить")

    def _get_selected_name(self) -> str | None:
        items = self._table.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)

    def _toggle_selected(self):
        name = self._get_selected_name()
        if name:
            self.pm.toggle_rule(name)
            self._refresh()

    def _remove_selected(self):
        name = self._get_selected_name()
        if name:
            self.pm.remove_rule(name)
            self._refresh()
