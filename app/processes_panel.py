"""
Kristina Helper — панель управления процессами.
"""

import json
import urllib.error
import urllib.request

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QLineEdit, QHeaderView, QAbstractItemView,
    QSlider, QFrame, QCheckBox, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont, QAction

from app.process_manager import ProcessManager, ProcessEntry


class ProcessDescriberWorker(QThread):
    """Фоновый запрос к Gemini для описания процесса."""

    description_ready = pyqtSignal(str, str)  # process_name, description
    error_occurred = pyqtSignal(str, str)     # process_name, error

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: str, process_name: str):
        super().__init__()
        self.api_key = api_key
        self.process_name = process_name

    def run(self):
        prompt = (
            "Ты системный эксперт Windows. Объясни человеческим, понятным языком "
            f"в 1 короткое предложение: для чего нужен процесс '{self.process_name}'? "
            "Не используй слишком сложные термины."
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 100},
        }
        url = f"{self.API_BASE}/{self.MODEL}:generateContent?key={self.api_key}"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            text = (
                result.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            self.description_ready.emit(self.process_name, text.strip())
        except Exception as e:
            self.error_occurred.emit(self.process_name, str(e))


class StatsCard(QWidget):
    """Карточка с одной статистикой."""

    def __init__(self, label: str, value: str = "0", color: str = "#58a6ff", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self._value_label = QLabel(value)
        self._value_label.setObjectName("stat_value")
        self._value_label.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: 700;")

        lbl = QLabel(label)
        lbl.setObjectName("stat_label")

        layout.addWidget(self._value_label)
        layout.addWidget(lbl)

    def set_value(self, v):
        self._value_label.setText(str(v))


class ProcessesPanel(QWidget):
    """
    Основная панель:
    - статистика (карточки)
    - ползунок интервала сканирования
    - таблица процессов с поиском
    - кнопки Kill / Добавить в блок-лист
    """

    ask_ai_about = pyqtSignal(str)   # Запросить AI про этот процесс

    def __init__(self, process_manager: ProcessManager, settings_manager, parent=None):
        super().__init__(parent)
        self.pm = process_manager
        self.settings = settings_manager
        self._all_processes: list[ProcessEntry] = []
        self._fetching_descriptions: set[str] = set()
        self._active_workers: list[ProcessDescriberWorker] = []
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Заголовок ────────────────────────────────────────────────────────
        title = QLabel("🖥 Процессы")
        title.setObjectName("section_title")
        layout.addWidget(title)

        # ── Статистика ───────────────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self._card_total = StatsCard("Всего процессов", "0", "#58a6ff")
        self._card_blocked = StatsCard("Правил блокировки", "0", "#f85149")
        self._card_killed = StatsCard("Завершено сегодня", "0", "#3fb950")
        self._card_running = StatsCard("Блокированных активно", "0", "#f0883e")

        for card in [self._card_total, self._card_blocked, self._card_killed, self._card_running]:
            stats_row.addWidget(card)

        layout.addLayout(stats_row)

        # ── Ползунок интервала ───────────────────────────────────────────────
        interval_card = QWidget()
        interval_card.setObjectName("card")
        interval_layout = QHBoxLayout(interval_card)
        interval_layout.setContentsMargins(16, 12, 16, 12)

        interval_label = QLabel("⏱ Интервал сканирования:")
        interval_label.setStyleSheet("color: #e6edf3;")

        self._interval_slider = QSlider(Qt.Orientation.Horizontal)
        self._interval_slider.setMinimum(1)   # 1 секунда
        self._interval_slider.setMaximum(60)  # 60 секунд
        self._interval_slider.setValue(5)
        self._interval_slider.setFixedWidth(200)

        self._interval_value_label = QLabel("5 сек")
        self._interval_value_label.setStyleSheet("color: #58a6ff; font-weight: 600; min-width: 50px;")

        self._interval_slider.valueChanged.connect(self._on_interval_changed)

        # Тоггл мониторинга
        self._monitor_toggle = QCheckBox("Мониторинг включён")
        self._monitor_toggle.setChecked(True)
        self._monitor_toggle.toggled.connect(self._on_monitor_toggled)
        self._monitor_toggle.setStyleSheet("""
            QCheckBox { color: #3fb950; font-weight: 600; }
            QCheckBox::indicator { width: 44px; height: 24px; }
        """)

        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self._interval_slider)
        interval_layout.addWidget(self._interval_value_label)
        interval_layout.addStretch()
        interval_layout.addWidget(self._monitor_toggle)

        layout.addWidget(interval_card)

        # ── Панель управления таблицей ───────────────────────────────────────
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍  Поиск процесса...")
        self._search_input.textChanged.connect(self._filter_table)
        self._search_input.setMaximumWidth(300)

        self._show_blocked_only = QCheckBox("Только заблокированные")
        self._show_blocked_only.toggled.connect(self._filter_table)
        self._show_blocked_only.setStyleSheet("color: #8b949e;")

        controls_row.addWidget(self._search_input)
        controls_row.addWidget(self._show_blocked_only)
        controls_row.addStretch()

        self._btn_refresh = QPushButton("↻  Обновить")
        self._btn_refresh.setObjectName("refresh_btn")
        self._btn_refresh.clicked.connect(self._manual_refresh)

        self._btn_kill = QPushButton("⛔  Завершить")
        self._btn_kill.setObjectName("kill_btn")
        self._btn_kill.setEnabled(False)
        self._btn_kill.clicked.connect(self._kill_selected)

        self._btn_add_block = QPushButton("+ Блокировать")
        self._btn_add_block.setObjectName("action_btn")
        self._btn_add_block.setEnabled(False)
        self._btn_add_block.clicked.connect(self._toggle_block_selected)

        self._btn_ask_ai = QPushButton("✨ Спросить AI")
        self._btn_ask_ai.setObjectName("refresh_btn")
        self._btn_ask_ai.setEnabled(False)
        self._btn_ask_ai.clicked.connect(self._ask_ai_selected)

        controls_row.addWidget(self._btn_refresh)
        controls_row.addWidget(self._btn_kill)
        controls_row.addWidget(self._btn_add_block)
        controls_row.addWidget(self._btn_ask_ai)

        layout.addLayout(controls_row)

        # ── Таблица процессов ─────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["Имя", "PID", "Статус", "CPU %", "Память МБ", "Блокировка", "Описание"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 220)
        self._table.setWordWrap(True)

        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(42)
        self._table.verticalHeader().setMinimumSectionSize(38)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self._table)

    def _connect_signals(self):
        self.pm.processes_updated.connect(self._on_processes_updated)
        self.pm.stats_updated.connect(self._on_stats_updated)

    # ── Слоты ────────────────────────────────────────────────────────────────

    def _on_processes_updated(self, processes: list[ProcessEntry]):
        self._all_processes = processes
        self._filter_table()

    def _on_stats_updated(self, stats: dict):
        self._card_total.set_value(stats.get("total_processes", 0))
        self._card_blocked.set_value(stats.get("blocked_rules", 0))
        self._card_killed.set_value(stats.get("total_killed", 0))
        self._card_running.set_value(stats.get("blocked_running", 0))

    def _filter_table(self):
        query = self._search_input.text().lower()
        only_blocked = self._show_blocked_only.isChecked()

        filtered = [
            p for p in self._all_processes
            if (not query or query in p.name.lower())
            and (not only_blocked or p.is_blocked)
        ]
        self._populate_table(filtered)

    def _populate_table(self, processes: list[ProcessEntry]):
        self._table.setRowCount(len(processes))
        for row, p in enumerate(processes):
            items = [
                QTableWidgetItem(p.name),
                QTableWidgetItem(str(p.pid)),
                QTableWidgetItem(p.status),
                QTableWidgetItem(f"{p.cpu_percent:.1f}"),
                QTableWidgetItem(f"{p.memory_mb:.1f}"),
                QTableWidgetItem("🚫 Заблокирован" if p.is_blocked else ""),
            ]
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(row, col, item)

            if p.name in self._fetching_descriptions:
                loading_item = QTableWidgetItem("⏳ Думает...")
                loading_item.setForeground(QColor("#f0883e"))
                loading_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(row, 6, loading_item)
            elif p.description:
                desc_item = QTableWidgetItem(p.description)
                desc_item.setToolTip(p.description)
                desc_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                self._table.setItem(row, 6, desc_item)
            else:
                btn = QPushButton("✨ Узнать")
                btn.setObjectName("action_btn")
                btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
                btn.setMinimumHeight(30)
                btn.setMinimumWidth(96)
                btn.clicked.connect(lambda _checked, name=p.name: self._fetch_description(name))
                self._table.setCellWidget(row, 6, btn)

            if p.is_blocked:
                for col in range(7):
                    if self._table.item(row, col):
                        self._table.item(row, col).setForeground(QColor("#f85149"))

            self._table.resizeRowToContents(row)

    def _fetch_description(self, process_name: str):
        api_key = self.settings.get("gemini_api_key", "").strip()
        if not api_key or process_name in self._fetching_descriptions:
            return

        self._fetching_descriptions.add(process_name)
        self._filter_table()

        worker = ProcessDescriberWorker(api_key, process_name)
        worker.description_ready.connect(self._on_description_ready)
        worker.error_occurred.connect(self._on_description_error)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        worker.start()
        self._active_workers.append(worker)

    def _on_worker_finished(self, worker: ProcessDescriberWorker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        worker.deleteLater()

    def _on_description_ready(self, process_name: str, description: str):
        self._fetching_descriptions.discard(process_name)
        if description:
            self.pm.save_description(process_name, description)
        self._manual_refresh()

    def _on_description_error(self, process_name: str, _error: str):
        self._fetching_descriptions.discard(process_name)
        self._filter_table()

    def _on_selection_changed(self):
        has_selection = bool(self._table.selectedItems())
        self._btn_kill.setEnabled(has_selection)
        self._btn_add_block.setEnabled(has_selection)
        self._btn_ask_ai.setEnabled(has_selection)

        # Обновляем текст кнопки блокировки
        p = self._get_selected_process()
        if p:
            if p.is_blocked:
                self._btn_add_block.setText("− Разблокировать")
                self._btn_add_block.setStyleSheet("background-color: #4a1d1d; color: #f85149; border-radius: 8px; padding: 8px 20px;")
            else:
                self._btn_add_block.setText("+ Блокировать")
                self._btn_add_block.setStyleSheet("")

    def _kill_selected(self):
        p = self._get_selected_process()
        if p:
            self.pm.kill_process(p.pid, p.name)
            self._manual_refresh()

    def _toggle_block_selected(self):
        p = self._get_selected_process()
        if p:
            if p.is_blocked:
                self.pm.remove_rule(p.name)
            else:
                self.pm.add_rule(p.name)
            self._manual_refresh()

    def _ask_ai_selected(self):
        p = self._get_selected_process()
        if p:
            self.ask_ai_about.emit(p.name)

    def _manual_refresh(self):
        self.pm.scan_and_enforce()

    def _get_selected_process(self) -> ProcessEntry | None:
        selected = self._table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        query = self._search_input.text().lower()
        only_blocked = self._show_blocked_only.isChecked()
        filtered = [
            p for p in self._all_processes
            if (not query or query in p.name.lower())
            and (not only_blocked or p.is_blocked)
        ]
        if row < len(filtered):
            return filtered[row]
        return None

    def _show_context_menu(self, pos):
        p = self._get_selected_process()
        if not p:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 4px;
                color: #e6edf3;
                font-size: 13px;
            }
            QMenu::item { padding: 8px 16px; border-radius: 6px; }
            QMenu::item:selected { background-color: #1f3a5f; }
        """)

        kill_action = QAction(f"⛔  Завершить {p.name}", menu)
        kill_action.triggered.connect(self._kill_selected)

        block_text = "− Разблокировать" if p.is_blocked else "🚫 Заблокировать навсегда"
        block_action = QAction(block_text, menu)
        block_action.triggered.connect(self._toggle_block_selected)

        ai_action = QAction("✨ Спросить AI про этот процесс", menu)
        ai_action.triggered.connect(self._ask_ai_selected)

        menu.addAction(kill_action)
        menu.addAction(block_action)
        menu.addSeparator()
        menu.addAction(ai_action)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_interval_changed(self, value: int):
        self._interval_value_label.setText(f"{value} сек")
        self.pm.set_interval(value * 1000)

    def _on_monitor_toggled(self, checked: bool):
        if checked:
            self.pm.start_monitoring(self._interval_slider.value() * 1000)
            self._monitor_toggle.setText("Мониторинг включён")
            self._monitor_toggle.setStyleSheet("QCheckBox { color: #3fb950; font-weight: 600; }")
        else:
            self.pm.stop_monitoring()
            self._monitor_toggle.setText("Мониторинг выключен")
            self._monitor_toggle.setStyleSheet("QCheckBox { color: #8b949e; font-weight: 600; }")
