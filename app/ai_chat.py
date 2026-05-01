"""
Kristina Helper — виджет AI-чата (Gemini Flash).
"""

import json
import urllib.request
import urllib.error
from groq import Groq
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton,
    QLabel, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

# ── Поток для запроса к Gemini ────────────────────────────────────────────────

class ChatWorker(QThread):
    """Отправляет запрос к выбранной LLM в фоновом потоке."""

    response_ready = pyqtSignal(str, str)
    error_occurred = pyqtSignal(str)

    DEFAULT_MODEL = "gemini-3.1-flash-preview"
    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, settings, history: list[dict], user_message: str, preferred_model: str | None = None):
        super().__init__()
        self.settings = settings
        self.history = history
        self.user_message = user_message
        self.preferred_model = (preferred_model or "").strip()

    def _extract_text(self, result: dict) -> str:
        candidates = result.get("candidates") or []
        if not candidates:
            return ""
        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        return (parts[0] or {}).get("text", "") if parts else ""

    def _extract_text(self, result: dict) -> str:
        candidates = result.get("candidates") or []
        if not candidates:
            return ""
        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        return (parts[0] or {}).get("text", "") if parts else ""

    def _extract_text(self, result: dict) -> str:
        candidates = result.get("candidates") or []
        if not candidates:
            return ""
        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        return (parts[0] or {}).get("text", "") if parts else ""

    def _extract_text(self, result: dict) -> str:
        candidates = result.get("candidates") or []
        if not candidates:
            return ""
        content = (candidates[0] or {}).get("content") or {}
        parts = content.get("parts") or []
        return (parts[0] or {}).get("text", "") if parts else ""

    def run(self):
        try:
            llm_model = self.settings.get("llm_model", "default")
            if llm_model == "groq":
                self._run_groq()
                return

            # Формируем contents из истории
            contents = []
            for msg in self.history:
                contents.append({
                    "role": msg["role"],
                    "parts": [{"text": msg["text"]}]
                })
            # Добавляем текущее сообщение
            contents.append({
                "role": "user",
                "parts": [{"text": self.user_message}]
            })

            payload = {
                "contents": contents,
                "systemInstruction": {
                    "parts": [{"text": (
                        "Ты Кристина — умный помощник приложения Kristina Helper. "
                        "Ты помогаешь пользователю управлять процессами Windows, "
                        "объясняешь что делает тот или иной процесс, "
                        "советуешь какие процессы стоит заблокировать. "
                        "Отвечай кратко и по делу, на том языке, на котором пишет пользователь."
                    )}]
                },
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048,
                }
            }

            model = self.preferred_model or self.DEFAULT_MODEL
            api_key = self.settings.get("gemini_api_key", "").strip()
            if not api_key:
                self.error_occurred.emit("Не указан Gemini API ключ в настройках.")
                return
            url = f"{self.API_BASE}/{model}:generateContent?key={api_key}"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            text = self._extract_text(result).strip()
            if text:
                self.response_ready.emit(text, model)
                return
            self.error_occurred.emit("Пустой ответ модели. Попробуй переформулировать вопрос.")

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            self.error_occurred.emit(f"HTTP {e.code}: {body[:200]}")
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _run_groq(self):
        api_key = self.settings.get("groq_api_key", "").strip()
        if not api_key:
            self.error_occurred.emit("Не указан API-ключ Groq в настройках.")
            return
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": self.user_message}],
            temperature=0.7,
        )
        text = (completion.choices[0].message.content or "").strip()
        if not text:
            self.error_occurred.emit("Пустой ответ от Groq.")
            return
        self.response_ready.emit(text, "llama-3.3-70b-versatile")


# ── Виджет одного сообщения ───────────────────────────────────────────────────

class MessageBubble(QFrame):
    """Пузырёк сообщения в чате."""

    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self._build_ui(text)

    def _build_ui(self, text: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setMaximumWidth(500)

        if self.is_user:
            label.setStyleSheet("""
                background-color: #1f3a5f;
                color: #e6edf3;
                border-radius: 12px 12px 4px 12px;
                padding: 10px 14px;
                font-size: 13px;
            """)
            layout.addStretch()
            layout.addWidget(label)
        else:
            label.setStyleSheet("""
                background-color: #161b22;
                color: #e6edf3;
                border: 1px solid #21262d;
                border-radius: 12px 12px 12px 4px;
                padding: 10px 14px;
                font-size: 13px;
            """)
            layout.addWidget(label)
            layout.addStretch()


# ── Основной виджет чата ─────────────────────────────────────────────────────

class AIChatWidget(QWidget):
    """
    Панель AI-чата с Gemini.
    Требует API ключ (вводится в настройках).
    """

    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings = settings_manager
        self._history: list[dict] = []  # {role: "user"|"model", text: str}
        self._worker: ChatWorker | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Заголовок
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("✨ AI-чат — Кристина")
        title.setObjectName("section_title")
        self._model_subtitle = QLabel("gemini-2.5-flash-lite")
        self._model_subtitle.setObjectName("section_subtitle")

        self._status_badge = QLabel("● Готова")
        self._status_badge.setStyleSheet("color: #3fb950; font-size: 12px;")

        header_layout.addWidget(title)
        header_layout.addSpacing(8)
        header_layout.addWidget(self._model_subtitle)
        header_layout.addStretch()
        header_layout.addWidget(self._status_badge)
        layout.addWidget(header)

        # Область сообщений
        self._scroll = QScrollArea()
        self._scroll.setObjectName("chat_area")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._messages_container = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_container)
        self._messages_layout.setContentsMargins(8, 8, 8, 8)
        self._messages_layout.setSpacing(4)
        self._messages_layout.addStretch()

        self._scroll.setWidget(self._messages_container)
        layout.addWidget(self._scroll)

        # Начальное приветствие
        self._add_bot_message(
            "Привет! Я Кристина 👋 Помогу разобраться с процессами Windows. "
            "Можешь спросить меня, что делает тот или иной процесс, "
            "или стоит ли его заблокировать."
        )

        # Ввод сообщения
        input_row = QWidget()
        input_layout = QHBoxLayout(input_row)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self._input = QLineEdit()
        self._input.setObjectName("chat_input")
        self._input.setPlaceholderText("Спроси меня что-нибудь про процессы...")
        self._input.returnPressed.connect(self._send_message)

        self._send_btn = QPushButton("Отправить")
        self._send_btn.setObjectName("send_btn")
        self._send_btn.setFixedWidth(110)
        self._send_btn.clicked.connect(self._send_message)

        input_layout.addWidget(self._input)
        input_layout.addWidget(self._send_btn)
        layout.addWidget(input_row)

        # Строка с API ключом
        key_row = QWidget()
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(8)

        key_label = QLabel("API ключ:")
        key_label.setStyleSheet("color: #8b949e; font-size: 12px;")
        key_label.setFixedWidth(65)

        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("Вставь Gemini API key (бесплатно на aistudio.google.com)")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setStyleSheet("font-size: 12px; padding: 6px 10px;")
        self._key_input.setText(self.settings.get("gemini_api_key", ""))
        self._key_input.textChanged.connect(
            lambda t: self.settings.set("gemini_api_key", t)
        )

        key_layout.addWidget(key_label)
        key_layout.addWidget(self._key_input)
        layout.addWidget(key_row)

    # ── Отправка ──────────────────────────────────────────────────────────────

    def _send_message(self):
        text = self._input.text().strip()
        if not text:
            return

        llm_model = self.settings.get("llm_model", "default")
        if llm_model == "groq" and not self.settings.get("groq_api_key", "").strip():
            self._add_bot_message("⚠️ Укажи Groq API ключ в настройках.")
            return
        if llm_model != "groq" and not self.settings.get("gemini_api_key", "").strip():
            self._add_bot_message("⚠️ Введи Gemini API ключ внизу. Его можно получить бесплатно на aistudio.google.com")
            return

        self._input.clear()
        self._add_user_message(text)
        self._set_loading(True)

        preferred_model = self.settings.get("gemini_model", "gemini-3-flash-preview")
        self._worker = ChatWorker(self.settings, self._history.copy(), text, preferred_model=preferred_model)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

        # Добавляем в историю
        self._history.append({"role": "user", "text": text})

    def _on_response(self, text: str, model: str):
        self._set_loading(False)
        self.settings.set("gemini_model", model)
        self._history.append({"role": "model", "text": text})
        self._model_subtitle.setText(model)
        self._add_bot_message(text)

    def _on_error(self, error: str):
        self._set_loading(False)
        self._add_bot_message(f"❌ Ошибка: {error}")

    def _on_worker_finished(self):
        self._worker = None

    # ── Вспомогательные ───────────────────────────────────────────────────────

    def _add_user_message(self, text: str):
        bubble = MessageBubble(text, is_user=True)
        # Вставляем перед stretch
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, bubble)
        self._scroll_to_bottom()

    def _add_bot_message(self, text: str):
        bubble = MessageBubble(text, is_user=False)
        count = self._messages_layout.count()
        self._messages_layout.insertWidget(count - 1, bubble)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _set_loading(self, loading: bool):
        self._send_btn.setEnabled(not loading)
        self._input.setEnabled(not loading)
        if loading:
            self._status_badge.setText("● Думает...")
            self._status_badge.setStyleSheet("color: #f0883e; font-size: 12px;")
        else:
            self._status_badge.setText("● Готова")
            self._status_badge.setStyleSheet("color: #3fb950; font-size: 12px;")

    def inject_process_context(self, process_name: str):
        """Вставить имя процесса в поле ввода для быстрого вопроса."""
        self._input.setText(f"Что делает процесс {process_name}? Стоит ли его заблокировать?")
        self._input.setFocus()
