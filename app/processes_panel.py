"""
Kristina Helper — панель управления процессами.
"""

import re
import time
import requests
from collections import defaultdict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QHeaderView, QAbstractItemView,
    QSlider, QFrame, QCheckBox, QMenu, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont, QAction

from app.process_manager import ProcessManager, ProcessEntry


class ProcessDescriberWorker(QThread):
    """Фоновый запрос к Gemini для описания процесса."""

    description_ready = pyqtSignal(str, str, str)
    error_occurred = pyqtSignal(str, str)     # process_name, error

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_MODEL = "gemini-2.5-flash-lite"

    def __init__(self, api_key: str, process_name: str, exe_path: str, preferred_model: str | None = None):
        super().__init__()
        self.api_key = api_key
        self.process_name = process_name
        self.exe_path = self._anonymize_path(exe_path)
        self.preferred_model = (preferred_model or "").strip()

    @staticmethod
    def _anonymize_path(path: str) -> str:
        """
        Заменяет реальное имя пользователя в путях вида C:\\Users\\<Name>\\... на 'User'.
        """
        if not path:
            return "Путь недоступен"
        return re.sub(
            r"(?i)([a-z]:\\users\\)[^\\]+(\\.*)?",
            r"\g<1>User\2",
            path
        )

    def _get_model_url(self) -> str:
        model = self.preferred_model or self.DEFAULT_MODEL
        return f"{self.API_BASE}/{model}:generateContent"

    @staticmethod
    def _extract_text(result: dict) -> str:
        candidates = result.get("candidates") or []
        if not candidates:
            return ""
        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        return (parts[0] or {}).get("text", "") if parts else ""

    def run(self):
        url = self._get_model_url()

        # --- ЗАПРОС 1: ОПИСАНИЕ ---
        prompt_desc = (
            f"Ты системный эксперт Windows. Расскажи коротко об этом процессе.\n"
            f"Имя: '{self.process_name}'\n"
            f"Путь: '{self.exe_path}'\n"
            "Напиши только одно короткое предложение на русском языке без кавычек и форматирования."
        )
        payload_desc = {
            "contents": [{"role": "user", "parts": [{"text": prompt_desc}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 100},
        }

        # --- ЗАПРОС 2: ВЕРИФИКАЦИЯ (СТАТУС) ---
        prompt_status = (
            f"Оцени безопасность процесса Windows.\n"
            f"Имя: '{self.process_name}'\n"
            f"Путь: '{self.exe_path}'\n"
            "Ответь СТРОГО одним словом: 'verified' (если процесс системный или от известного разработчика) "
            "или 'dangerous' (если путь подозрительный или это потенциально нежелательное ПО). Никаких других символов."
        )
        payload_status = {
            "contents": [{"role": "user", "parts": [{"text": prompt_status}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 10,
            },
        }

        try:
            # 1. Получаем описание
            resp_desc = requests.post(
                f"{url}?key={self.api_key}",
                json=payload_desc,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp_desc.raise_for_status()
            desc_text = self._extract_text(resp_desc.json()).strip()

            # Пауза в 1.5 секунды, чтобы избежать ошибки 429 (Too Many Requests) от API
            time.sleep(1.5)

            # 2. Получаем статус
            resp_status = requests.post(
                f"{url}?key={self.api_key}",
                json=payload_status,
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            resp_status.raise_for_status()
            status_text = self._extract_text(resp_status.json()).strip().lower()

            # --- ОБРАБОТКА И ЭМИТ СИГНАЛА ---
            final_desc = desc_text if desc_text else "Нет описания."

            # Безопасное извлечение статуса (даже если ИИ добавил точку в конце)
            final_status = "unknown"
            if "verified" in status_text:
                final_status = "verified"
            elif "dangerous" in status_text:
                final_status = "dangerous"

            self.description_ready.emit(self.process_name, final_desc, final_status)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                self.error_occurred.emit(self.process_name, "Превышен лимит запросов к ИИ. Попробуйте позже.")
            else:
                self.error_occurred.emit(self.process_name, f"Ошибка API: {e.response.status_code}")
        except Exception as e:
            self.error_occurred.emit(self.process_name, f"Внутренняя ошибка: {str(e)}")



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
    scan_interval_changed = pyqtSignal(int)  # сек

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
        self._interval_slider.setFixedWidth(200)

        # Блокируем сигналы перед установкой начального значения из настроек
        self._interval_slider.blockSignals(True)
        initial_value = self.settings.get("scan_interval_sec", 5)
        self._interval_slider.setValue(initial_value)
        self._interval_slider.blockSignals(False)

        self._interval_value_label = QLabel(f"{initial_value} сек")
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

        # ── Таблица процессов (Дерево) ────────────────────────────────────────
        self._table = QTreeWidget()
        self._table.setColumnCount(7)
        self._table.setHeaderLabels(
            ["Имя", "PID", "Статус", "CPU %", "Память МБ", "Блокировка", "Описание"]
        )
        self._table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._table.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.header().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.header().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.header().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 220)
        self._table.setWordWrap(True)
        self._table.setTextElideMode(Qt.TextElideMode.ElideNone)

        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.setStyleSheet("""
            QTreeWidget {
                gridline-color: rgba(139, 148, 158, 0.18);
            }
            QTreeWidget::item {
                border-bottom: 1px solid rgba(139, 148, 158, 0.14);
                border-right: 1px solid rgba(139, 148, 158, 0.10);
                padding: 0px 6px;
            }
            QHeaderView::section {
                border-right: 1px solid rgba(139, 148, 158, 0.16);
            }
        """)
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

    def _get_status_icon(self, status: str) -> str:
        """Возвращает эмодзи в зависимости от статуса безопасности."""
        if status == "verified":
            return "🛡️ "
        if status == "dangerous":
            return "⚠️ "
        return "❔ "

    def _populate_table(self, processes: list[ProcessEntry]):
        # Сохраняем состояние раскрытых узлов по ключу (имя, путь)
        expanded_groups = set()
        for i in range(self._table.topLevelItemCount()):
            item = self._table.topLevelItem(i)
            if item.isExpanded():
                proc_data = item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(proc_data, ProcessEntry):
                    expanded_groups.add((proc_data.name.lower(), (proc_data.exe or "").lower()))

        self._table.clear()

        # Группируем процессы по имени И пути к исполняемому файлу
        grouped = defaultdict(list)
        for p in processes:
            # Если процесс системный и путь недоступен, группируем по пустой строке
            exe_path = p.exe if p.exe else "Неизвестный путь"
            grouped[(p.name.lower(), exe_path.lower())].append(p)

        # Сортируем группы по имени
        for (_group_name, _group_exe), procs in sorted(grouped.items()):
            total_cpu = sum(p.cpu_percent for p in procs)
            total_mem = sum(p.memory_mb for p in procs)
            is_blocked = any(p.is_blocked for p in procs)

            rep = procs[0]
            icon = self._get_status_icon(rep.security_status)
            exe_display = rep.exe if rep.exe else "Путь недоступен"

            # Если процесс всего один с таким именем и путем
            if len(procs) == 1:
                parent_item = QTreeWidgetItem([
                    f"{icon}{rep.name}",
                    str(rep.pid),
                    rep.status,
                    f"{rep.cpu_percent:.1f}",
                    f"{rep.memory_mb:.1f}",
                    "🚫 Заблокирован" if rep.is_blocked else "",
                    ""
                ])
                parent_item.setToolTip(0, f"Путь: {exe_display}")
                parent_item.setData(0, Qt.ItemDataRole.UserRole, rep)
                self._table.addTopLevelItem(parent_item)
                self._setup_item_ui(parent_item, rep)

            # Если процессов несколько — стакаем
            else:
                parent_item = QTreeWidgetItem([
                    f"{icon}{rep.name} ({len(procs)})",
                    "---",
                    "Запущен",
                    f"{total_cpu:.1f}",
                    f"{total_mem:.1f}",
                    "🚫 Заблокирован" if is_blocked else "",
                    ""
                ])
                parent_item.setToolTip(0, f"Путь: {exe_display}")
                parent_item.setData(0, Qt.ItemDataRole.UserRole, rep)
                self._table.addTopLevelItem(parent_item)
                self._setup_item_ui(parent_item, rep)

                # Восстанавливаем раскрытие, если группа была открыта
                if (rep.name.lower(), (rep.exe or "").lower()) in expanded_groups:
                    parent_item.setExpanded(True)

                for p in sorted(procs, key=lambda x: x.memory_mb, reverse=True):
                    child_icon = self._get_status_icon(p.security_status)
                    child_item = QTreeWidgetItem([
                        f"   ↳ {child_icon}{p.name}",
                        str(p.pid),
                        p.status,
                        f"{p.cpu_percent:.1f}",
                        f"{p.memory_mb:.1f}",
                        "🚫" if p.is_blocked else "",
                        ""
                    ])
                    child_item.setToolTip(0, f"Путь: {exe_display}")
                    child_item.setData(0, Qt.ItemDataRole.UserRole, p)
                    parent_item.addChild(child_item)

                    if p.is_blocked:
                        for col in range(7):
                            child_item.setForeground(col, QColor("#f85149"))

    def _setup_item_ui(self, item: QTreeWidgetItem, p: ProcessEntry):
        """Устанавливает цвета и виджеты (описания, кнопки) для элемента дерева."""
        if p.is_blocked:
            for col in range(7):
                item.setForeground(col, QColor("#f85149"))

        process_key = p.name.lower()
        if process_key in self._fetching_descriptions:
            item.setText(6, "⏳ Думает...")
            item.setForeground(6, QColor("#f0883e"))
        elif p.description:
            self._table.setItemWidget(
                item, 6, self._build_description_cell(p.description, p.name, p.exe)
            )
        else:
            self._table.setItemWidget(item, 6, self._build_ask_button_cell(p.name, p.exe))

    def _build_ask_button_cell(self, process_name: str, exe_path: str) -> QWidget:
        from PyQt6.QtCore import Qt as _Qt
        cell = QWidget()
        cell.setAttribute(_Qt.WidgetAttribute.WA_TranslucentBackground)
        cell.setStyleSheet("background: transparent;")
        # Минимальная высота = sizeHint кнопки (34px) + вертикальные отступы (6px)
        cell.setMinimumHeight(36)
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)
        layout.setAlignment(_Qt.AlignmentFlag.AlignLeft | _Qt.AlignmentFlag.AlignVCenter)

        btn = QPushButton("✨ Узнать")
        btn.setObjectName("desc_btn")
        btn.setCursor(_Qt.CursorShape.PointingHandCursor)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet("""
            QPushButton#desc_btn {
                background-color: #238636; color: #ffffff;
                border: none; border-radius: 8px; padding: 4px 12px;
                text-align: center;
                font-size: 12px; font-weight: 600; min-height: 24px;
            }
            QPushButton#desc_btn:hover { background-color: #2ea043; }
        """)
        btn.clicked.connect(lambda _checked, n=process_name, e=exe_path: self._fetch_description(n, e))
        layout.addWidget(btn)
        return cell

    def _build_description_cell(self, text: str, process_name: str, exe_path: str) -> QWidget:
        cell = QWidget()
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)

        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_label.setStyleSheet("color: #e6edf3; font-size: 12px;")
        text_label.setToolTip(text)

        refresh_btn = QPushButton("↻ Обновить")
        refresh_btn.setObjectName("desc_refresh_btn")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        refresh_btn.setStyleSheet("""
            QPushButton#desc_refresh_btn {
                background-color: #30363d;
                color: #e6edf3;
                border: 1px solid #484f58;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                min-height: 24px;
            }
            QPushButton#desc_refresh_btn:hover {
                background-color: #3b434c;
            }
        """)
        refresh_btn.clicked.connect(lambda _checked, n=process_name, e=exe_path: self._fetch_description(n, e, force=True))

        layout.addWidget(text_label, stretch=1)
        layout.addWidget(refresh_btn, stretch=0, alignment=Qt.AlignmentFlag.AlignVCenter)
        return cell

    def _fetch_description(self, process_name: str, exe_path: str = "", force: bool = False):
        api_key = self.settings.get("gemini_api_key", "").strip()
        process_key = process_name.lower()
        if not api_key or process_key in self._fetching_descriptions:
            return

        if force:
            self.pm.save_description(process_name, "")

        self._fetching_descriptions.add(process_key)
        self._filter_table()

        preferred_model = self.settings.get("gemini_model", "gemini-3-flash-preview")
        worker = ProcessDescriberWorker(api_key, process_name, exe_path, preferred_model=preferred_model)
        worker.description_ready.connect(self._on_description_ready)
        worker.error_occurred.connect(self._on_description_error)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        worker.start()
        self._active_workers.append(worker)

    def _on_worker_finished(self, worker: ProcessDescriberWorker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        worker.deleteLater()

    def _on_description_ready(self, process_name: str, description: str, status: str):
        self._fetching_descriptions.discard(process_name.lower())
        if description:
            self.pm.save_description(process_name, description, status)
        self._manual_refresh()

    def _on_description_error(self, process_name: str, error: str):
        self._fetching_descriptions.discard(process_name.lower())
        self.pm.save_description(
            process_name,
            f"Не удалось получить описание автоматически ({error}). Нажми «✨ Спросить AI» для ручного уточнения."
        )
        self._filter_table()

    def _on_selection_changed(self):
        has_selection = bool(self._table.selectedItems())
        p = self._get_selected_process() if has_selection else None
        self._btn_kill.setEnabled(bool(p and p.is_running and p.pid > 0))
        self._btn_add_block.setEnabled(bool(p))
        self._btn_ask_ai.setEnabled(bool(p))

        # Обновляем текст кнопки блокировки
        if p:
            if p.is_blocked:
                self._btn_add_block.setText("− Разблокировать")
                self._btn_add_block.setStyleSheet("background-color: #4a1d1d; color: #f85149; border-radius: 8px; padding: 8px 20px;")
            else:
                self._btn_add_block.setText("+ Блокировать")
                self._btn_add_block.setStyleSheet("")

    def _kill_selected(self):
        p = self._get_selected_process()
        if p and p.is_running and p.pid > 0:
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

        item = selected[0]
        process_data = item.data(0, Qt.ItemDataRole.UserRole)

        if isinstance(process_data, ProcessEntry):
            return process_data

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
        self.settings.set("scan_interval_sec", value)
        self.pm.set_interval(value * 1000)
        self.scan_interval_changed.emit(value)

    def set_scan_interval(self, value: int):
        self._interval_slider.blockSignals(True)
        self._interval_slider.setValue(value)
        self._interval_slider.blockSignals(False)
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
