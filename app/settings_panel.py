"""
Kristina Helper — панель настроек.
"""

import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QFrame, QLineEdit,
    QSpinBox, QGroupBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.settings import SettingsManager
from app.autostart import AutostartManager


class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet("color: #21262d; background-color: #21262d; border: none; max-height: 1px;")


class SettingRow(QWidget):
    """Строка настройки: заголовок + описание слева, контрол справа."""

    def __init__(self, title: str, description: str, control: QWidget, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(16)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        t = QLabel(title)
        t.setStyleSheet("color: #e6edf3; font-size: 13px; font-weight: 600;")

        d = QLabel(description)
        d.setStyleSheet("color: #8b949e; font-size: 12px;")
        d.setWordWrap(True)

        text_col.addWidget(t)
        text_col.addWidget(d)

        layout.addLayout(text_col, stretch=1)
        layout.addWidget(control, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class SectionCard(QWidget):
    """Карточка секции настроек."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 16)
        self._layout.setSpacing(0)

        lbl = QLabel(title)
        lbl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; padding-bottom: 12px;")
        self._layout.addWidget(lbl)

    def add_row(self, row: QWidget, add_divider: bool = True):
        if add_divider and self._layout.count() > 1:
            self._layout.addWidget(Divider())
        self._layout.addWidget(row)


class ToggleSwitch(QCheckBox):
    """Переключатель в стиле iOS toggle."""

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setChecked(checked)
        self._update_style()
        self.toggled.connect(lambda: self._update_style())

    def _update_style(self):
        if self.isChecked():
            self.setStyleSheet("""
                QCheckBox::indicator {
                    width: 44px; height: 24px;
                    border-radius: 12px;
                    background-color: #238636;
                    border: none;
                    image: url();
                }
            """)
        else:
            self.setStyleSheet("""
                QCheckBox::indicator {
                    width: 44px; height: 24px;
                    border-radius: 12px;
                    background-color: #21262d;
                    border: 1px solid #30363d;
                }
            """)
        self.setText("")


class SettingsPanel(QWidget):
    """Панель настроек приложения."""

    autostart_changed = pyqtSignal(bool)
    scan_interval_changed = pyqtSignal(int)

    def __init__(self, settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("⚙️ Настройки")
        title.setObjectName("section_title")
        layout.addWidget(title)

        subtitle = QLabel("Управление поведением Kristina Helper")
        subtitle.setObjectName("section_subtitle")
        layout.addWidget(subtitle)

        # ── Секция: Запуск ────────────────────────────────────────────────────
        startup_card = SectionCard("Запуск и работа в фоне")

        # Автозапуск
        self._autostart_toggle = ToggleSwitch(AutostartManager.is_enabled())
        self._autostart_toggle.toggled.connect(self._on_autostart_toggled)
        startup_card.add_row(SettingRow(
            "Автозапуск с Windows",
            "Kristina Helper запускается автоматически при входе в систему",
            self._autostart_toggle
        ))

        # Сворачивать в трей
        self._tray_toggle = ToggleSwitch(self.settings.get("minimize_to_tray"))
        self._tray_toggle.toggled.connect(lambda v: self.settings.set("minimize_to_tray", v))
        startup_card.add_row(SettingRow(
            "Сворачивать в трей",
            "При закрытии окна приложение остаётся работать в системном трее",
            self._tray_toggle
        ))

        layout.addWidget(startup_card)

        # ── Секция: Мониторинг ────────────────────────────────────────────────
        monitor_card = SectionCard("Мониторинг процессов")

        # Интервал сканирования
        self._interval_spin = QSpinBox()
        self._interval_spin.setMinimum(1)
        self._interval_spin.setMaximum(60)
        # Блокируем сигналы перед установкой начального значения из настроек
        self._interval_spin.blockSignals(True)
        initial_value = self.settings.get("scan_interval_sec", 5)
        self._interval_spin.setValue(initial_value)
        self._interval_spin.blockSignals(False)
        self._interval_spin.setSuffix(" сек")
        self._interval_spin.setFixedWidth(100)
        self._interval_spin.setStyleSheet("""
            QSpinBox {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 6px 10px;
                color: #e6edf3;
                font-size: 13px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #21262d;
                border: none;
                border-radius: 4px;
                width: 18px;
            }
        """)
        self._interval_spin.valueChanged.connect(self._on_scan_interval_changed)
        monitor_card.add_row(SettingRow(
            "Интервал проверки",
            "Как часто сканировать запущенные процессы",
            self._interval_spin
        ))

        # Уведомления
        self._notif_toggle = ToggleSwitch(self.settings.get("show_notifications"))
        self._notif_toggle.toggled.connect(lambda v: self.settings.set("show_notifications", v))
        monitor_card.add_row(SettingRow(
            "Уведомления",
            "Показывать всплывающее уведомление при завершении процесса",
            self._notif_toggle
        ))

        layout.addWidget(monitor_card)

        # ── Секция: AI ────────────────────────────────────────────────────────
        ai_card = SectionCard("AI")

        key_widget = QWidget()
        key_layout = QHBoxLayout(key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(8)

        self._api_key_input = QLineEdit()
        self._api_key_input.setPlaceholderText("Вставь API ключ...")
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setText(self.settings.get("gemini_api_key", ""))
        self._api_key_input.setFixedWidth(280)
        self._api_key_input.textChanged.connect(
            lambda t: self.settings.set("gemini_api_key", t)
        )

        show_btn = QPushButton("👁")
        show_btn.setFixedSize(32, 32)
        show_btn.setCheckable(True)
        show_btn.setStyleSheet("""
            QPushButton { background: #21262d; border: 1px solid #30363d; border-radius: 8px; }
            QPushButton:checked { background: #1f3a5f; }
        """)
        show_btn.toggled.connect(lambda v: self._api_key_input.setEchoMode(
            QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
        ))

        key_layout.addWidget(self._api_key_input)
        key_layout.addWidget(show_btn)


        # Выбор LLM
        self._llm_selector = QComboBox()
        self._llm_selector.addItem("Стандартная модель (Gemini)", "default")
        self._llm_selector.addItem("Groq: llama-3.3-70b-versatile", "groq")
        current_model = self.settings.get("llm_model", "default")
        model_index = self._llm_selector.findData(current_model)
        if model_index >= 0:
            self._llm_selector.setCurrentIndex(model_index)
        self._llm_selector.currentIndexChanged.connect(self._on_model_changed)
        ai_card.add_row(SettingRow(
            "Модель LLM",
            "Выбери провайдера AI для чата",
            self._llm_selector
        ))

        ai_card.add_row(SettingRow(
            "Gemini API ключ",
            "Бесплатный ключ: aistudio.google.com → Get API key",
            key_widget
        ))

        groq_key_widget = QWidget()
        groq_key_layout = QHBoxLayout(groq_key_widget)
        groq_key_layout.setContentsMargins(0, 0, 0, 0)
        groq_key_layout.setSpacing(8)

        self._groq_api_input = QLineEdit()
        self._groq_api_input.setPlaceholderText("Вставь Groq API ключ...")
        self._groq_api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._groq_api_input.setText(self.settings.get("groq_api_key", ""))
        self._groq_api_input.setFixedWidth(280)
        self._groq_api_input.textChanged.connect(lambda t: self.settings.set("groq_api_key", t))

        self._groq_show_btn = QPushButton("👁")
        self._groq_show_btn.setFixedSize(32, 32)
        self._groq_show_btn.setCheckable(True)
        self._groq_show_btn.setStyleSheet("""
            QPushButton { background: #21262d; border: 1px solid #30363d; border-radius: 8px; }
            QPushButton:checked { background: #1f3a5f; }
        """)
        self._groq_show_btn.toggled.connect(lambda v: self._groq_api_input.setEchoMode(
            QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
        ))

        groq_key_layout.addWidget(self._groq_api_input)
        groq_key_layout.addWidget(self._groq_show_btn)

        self._groq_row = SettingRow(
            "Groq API ключ",
            "Нужен для llama-3.3-70b-versatile через Groq",
            groq_key_widget
        )
        ai_card.add_row(self._groq_row, add_divider=False)

        self._update_api_key_visibility()
        layout.addWidget(ai_card)

        # ── Секция: О приложении ──────────────────────────────────────────────
        about_card = SectionCard("О приложении")

        about_widget = QWidget()
        about_layout = QVBoxLayout(about_widget)
        about_layout.setContentsMargins(0, 4, 0, 4)
        about_layout.setSpacing(4)

        lines = [
            ("Kristina Helper", "#e6edf3", "14px", "700"),
            ("Версия 1.2.0", "#8b949e", "12px", "400"),
            ("Мониторинг и блокировка процессов Windows + AI-чат", "#8b949e", "12px", "400"),
        ]
        for text, color, size, weight in lines:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; font-size: {size}; font-weight: {weight};")
            about_layout.addWidget(lbl)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(0, 8, 0, 0)

        for text, url in [
            ("🔑 Получить API ключ", "https://aistudio.google.com/apikey"),
            ("📦 Зависимости", None),
        ]:
            btn = QPushButton(text)
            btn.setObjectName("refresh_btn")
            if url:
                import webbrowser
                btn.clicked.connect(lambda _, u=url: webbrowser.open(u))
            btn_row.addWidget(btn)
        btn_row.addStretch()
        about_layout.addLayout(btn_row)

        # Зависимости
        deps_label = QLabel("Требуется: PyQt6, psutil")
        deps_label.setStyleSheet("color: #484f58; font-size: 11px; padding-top: 4px;")
        about_layout.addWidget(deps_label)

        about_card.add_row(SettingRow("", "", about_widget), add_divider=False)
        layout.addWidget(about_card)

        layout.addStretch()

    # ── Обработчики ───────────────────────────────────────────────────────────

    def _on_model_changed(self):
        self.settings.set("llm_model", self._llm_selector.currentData())
        self._update_api_key_visibility()

    def _update_api_key_visibility(self):
        is_groq = self._llm_selector.currentData() == "groq"
        self._groq_row.setVisible(is_groq)


    def _on_autostart_toggled(self, checked: bool):
        if sys.platform == "win32":
            if checked:
                ok = AutostartManager.enable()
            else:
                ok = AutostartManager.disable()
            if not ok:
                # Откатываем тоггл и показываем ошибку
                self._autostart_toggle.blockSignals(True)
                self._autostart_toggle.setChecked(not checked)
                self._autostart_toggle.blockSignals(False)
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "Автозапуск",
                    "Не удалось изменить параметр автозапуска.\n"
                    "Проверьте права доступа или запустите приложение от имени администратора."
                )
                return
        self.settings.set("autostart", checked)
        self.autostart_changed.emit(checked)


    def _on_scan_interval_changed(self, value: int):
        self.settings.set("scan_interval_sec", value)
        self.scan_interval_changed.emit(value)

    def set_scan_interval(self, value: int):
        self._interval_spin.blockSignals(True)
        self._interval_spin.setValue(value)
        self._interval_spin.blockSignals(False)
