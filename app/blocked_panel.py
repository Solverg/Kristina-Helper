"""
Kristina Helper — панель заблокированных процессов.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QSizePolicy
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
        self._table.setColumnCount(4)
        self._table.setHeaderLabels(["Имя процесса", "Статус", "Завершено раз", "Описание"])
        self._table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._table.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self._table.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self._table.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.header().setStretchLastSection(True)
        self._table.setColumnWidth(0, 220)
        self._table.setColumnWidth(1, 130)
        self._table.setColumnWidth(2, 120)

        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setRootIsDecorated(False)
        self._table.setUniformRowHeights(False)
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
            description, security_status = self._get_description_and_status(rule.name)
            process_icon = self._get_status_icon(security_status)
            item = QTreeWidgetItem([
                f"{process_icon}{rule.name}",
                status_text,
                str(rule.kill_count),
                description,
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, rule.name)
            item.setToolTip(3, description)

            if not rule.enabled:
                for col in range(4):
                    item.setForeground(col, QColor("#484f58"))
            else:
                item.setForeground(1, QColor("#3fb950"))

            self._table.addTopLevelItem(item)
            self._table.setItemWidget(item, 3, self._build_description_cell(description))

        self._on_selection_changed()

    def _build_description_cell(self, text: str) -> QWidget:
        cell = QWidget()
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)

        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_label.setStyleSheet("color: #e6edf3; font-size: 12px;")
        text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout.addWidget(text_label)
        return cell

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

    @staticmethod
    def _get_status_icon(status: str) -> str:
        if status == "verified":
            return "🛡️ "
        if status == "dangerous":
            return "⚠️ "
        return "❔ "

    def _get_description_and_status(self, process_name: str) -> tuple[str, str]:
        data = self.pm.process_descriptions.get(process_name.lower(), {})
        if isinstance(data, dict):
            description = (data.get("description") or "Нет описания").strip()
            status = (data.get("status") or "unknown").strip().lower()
        else:
            description = str(data).strip() if data else "Нет описания"
            status = "unknown"

        if status not in {"verified", "dangerous", "unknown"}:
            status = "unknown"
        if not description:
            description = "Нет описания"
        return description, status
