"""
Kristina Helper — стили (Windows 11 dark glassmorphism).
"""

STYLESHEET = """
/* ─── Глобальные переменные через классы ─── */

QWidget {
    background-color: #0d1117;
    color: #e6edf3;
    font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    font-size: 13px;
}

/* ─── Главное окно ─── */
QMainWindow {
    background-color: #0d1117;
}

/* ─── Боковая панель ─── */
#sidebar {
    background-color: #161b22;
    border-right: 1px solid #21262d;
    min-width: 220px;
    max-width: 220px;
}

#logo_label {
    font-size: 15px;
    font-weight: 600;
    color: #58a6ff;
    padding: 4px 0;
}

#subtitle_label {
    font-size: 11px;
    color: #8b949e;
    padding-bottom: 8px;
}

/* ─── Кнопки навигации ─── */
#nav_btn {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: left;
    color: #8b949e;
    font-size: 13px;
}

#nav_btn:hover {
    background-color: #21262d;
    color: #e6edf3;
}

#nav_btn[active="true"] {
    background-color: #1f3a5f;
    color: #58a6ff;
    font-weight: 600;
}

/* ─── Стекловидная карточка ─── */
#card {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 16px;
}

/* ─── Таблица процессов ─── */
QTableWidget {
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    gridline-color: #21262d;
    selection-background-color: #1f3a5f;
    selection-color: #e6edf3;
    outline: none;
}

QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #21262d;
}

QTableWidget::item:hover {
    background-color: #1c2128;
}

QHeaderView::section {
    background-color: #0d1117;
    color: #8b949e;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid #21262d;
}

/* ─── Ползунок ─── */
QSlider::groove:horizontal {
    height: 4px;
    background: #21262d;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #58a6ff;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #79c0ff;
}

QSlider::sub-page:horizontal {
    background: #58a6ff;
    border-radius: 2px;
}

/* ─── Кнопки действий ─── */
QPushButton#kill_btn {
    background-color: #da3633;
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 600;
}

QPushButton#kill_btn:hover {
    background-color: #f85149;
}

QPushButton#kill_btn:disabled {
    background-color: #3d1f1e;
    color: #6e3130;
}

QPushButton#refresh_btn {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 20px;
}

QPushButton#refresh_btn:hover {
    background-color: #30363d;
    border-color: #8b949e;
}

QPushButton#action_btn {
    background-color: #238636;
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: 600;
}

QPushButton#action_btn:hover {
    background-color: #2ea043;
}

/* ─── Поиск / Input ─── */
QLineEdit {
    background-color: #0d1117;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e6edf3;
    selection-background-color: #1f3a5f;
}

QLineEdit:focus {
    border-color: #58a6ff;
}

QLineEdit::placeholder {
    color: #484f58;
}

/* ─── AI Чат ─── */
#chat_area {
    background-color: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
}

#chat_input {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    color: #e6edf3;
}

#chat_input:focus {
    border-color: #58a6ff;
}

#send_btn {
    background-color: #58a6ff;
    color: #0d1117;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-weight: 700;
}

#send_btn:hover {
    background-color: #79c0ff;
}

#send_btn:disabled {
    background-color: #1f3a5f;
    color: #484f58;
}

/* ─── Скроллбар ─── */
QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #484f58;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    height: 6px;
    background: transparent;
}

QScrollBar::handle:horizontal {
    background: #30363d;
    border-radius: 3px;
}

/* ─── Toggle Switch (чекбокс как тоггл) ─── */
QCheckBox {
    color: #e6edf3;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 40px;
    height: 22px;
    border-radius: 11px;
    background-color: #21262d;
    border: 1px solid #30363d;
}

QCheckBox::indicator:checked {
    background-color: #238636;
    border-color: #2ea043;
}

/* ─── Комбобокс ─── */
QComboBox {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 6px 12px;
    color: #e6edf3;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #8b949e;
}

QComboBox QAbstractItemView {
    background-color: #161b22;
    border: 1px solid #30363d;
    selection-background-color: #1f3a5f;
}

/* ─── Статусная строка ─── */
QStatusBar {
    background-color: #161b22;
    border-top: 1px solid #21262d;
    color: #8b949e;
    font-size: 11px;
}

/* ─── Тултипы ─── */
QToolTip {
    background-color: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
    border-radius: 6px;
    padding: 4px 8px;
}

/* ─── Labels ─── */
#section_title {
    font-size: 16px;
    font-weight: 700;
    color: #e6edf3;
    padding-bottom: 4px;
}

#section_subtitle {
    font-size: 12px;
    color: #8b949e;
}

#stat_value {
    font-size: 28px;
    font-weight: 700;
    color: #58a6ff;
}

#stat_label {
    font-size: 11px;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

#badge_blocked {
    background-color: #3d1f1e;
    color: #f85149;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}

#badge_active {
    background-color: #1a3a20;
    color: #3fb950;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
"""
