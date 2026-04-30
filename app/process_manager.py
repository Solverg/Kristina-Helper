"""
Kristina Helper — менеджер процессов.
Отслеживает запущенные процессы и завершает заблокированные.
"""

import psutil
import json
import os
import logging
from dataclasses import dataclass, asdict
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".kristina_helper", "blocked.json")
DESCRIPTIONS_PATH = os.path.join(os.path.expanduser("~"), ".kristina_helper", "descriptions.json")


@dataclass
class ProcessEntry:
    """Информация об одном процессе."""
    pid: int
    name: str
    exe: str
    status: str
    cpu_percent: float
    memory_mb: float
    is_blocked: bool = False
    description: str = ""
    security_status: str = "unknown"
    is_running: bool = True


@dataclass
class BlockRule:
    """Правило блокировки процесса."""
    name: str            # Имя exe (например, 'telegram.exe')
    enabled: bool = True
    kill_count: int = 0  # Сколько раз был убит


class ProcessManager(QObject):
    """
    Ядро логики:
    - сканирует процессы
    - завершает заблокированные
    - сохраняет/загружает список правил
    """

    processes_updated = pyqtSignal(list)      # список ProcessEntry
    process_killed = pyqtSignal(str, int)     # (name, pid) — процесс убит
    stats_updated = pyqtSignal(dict)          # статистика

    def __init__(self, parent=None):
        super().__init__(parent)

        self.block_rules: dict[str, BlockRule] = {}  # name -> BlockRule
        self.process_descriptions: dict[str, dict | str] = {}
        self._last_processes: list[ProcessEntry] = []
        self._total_killed = 0

        # Таймер авто-сканирования (каждые 5 секунд)
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self.scan_and_enforce)
        self._scan_interval_ms = 5000

        self._load_rules()
        self._load_descriptions()

    # ── Конфигурация ────────────────────────────────────────────────────────

    def _ensure_config_dir(self):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

    def _load_rules(self):
        """Загрузка правил блокировки из JSON."""
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    rule = BlockRule(**item)
                    self.block_rules[rule.name.lower()] = rule
                logger.info(f"Загружено {len(self.block_rules)} правил")
        except Exception as e:
            logger.error(f"Ошибка загрузки правил: {e}")

    def _load_descriptions(self):
        """Загрузка описаний процессов из JSON."""
        try:
            if os.path.exists(DESCRIPTIONS_PATH):
                with open(DESCRIPTIONS_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.process_descriptions = {}
                    for name, data in loaded.items():
                        # Поддержка старого формата кэша (если там были просто строки)
                        if isinstance(data, str):
                            self.process_descriptions[str(name).lower()] = {
                                "description": data,
                                "status": "unknown"
                            }
                        else:
                            self.process_descriptions[str(name).lower()] = data
                    logger.info(f"Загружено описаний процессов: {len(self.process_descriptions)}")
        except Exception as e:
            logger.error(f"Ошибка загрузки описаний: {e}")

    def save_description(self, process_name: str, description: str, status: str = "unknown"):
        """Сохранить описание процесса в кэш и JSON."""
        key = process_name.lower()
        self.process_descriptions[key] = {
            "description": description,
            "status": status
        }
        try:
            self._ensure_config_dir()
            with open(DESCRIPTIONS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.process_descriptions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения описаний: {e}")

    def save_rules(self):
        """Сохранение правил в JSON."""
        try:
            self._ensure_config_dir()
            data = [asdict(r) for r in self.block_rules.values()]
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения правил: {e}")

    # ── Управление правилами ─────────────────────────────────────────────────

    def add_rule(self, process_name: str) -> bool:
        """Добавить процесс в список блокировки."""
        key = process_name.lower()
        if key not in self.block_rules:
            self.block_rules[key] = BlockRule(name=process_name)
            self.save_rules()
            logger.info(f"Добавлено правило: {process_name}")
            return True
        return False

    def remove_rule(self, process_name: str) -> bool:
        """Удалить правило блокировки."""
        key = process_name.lower()
        if key in self.block_rules:
            del self.block_rules[key]
            self.save_rules()
            return True
        return False

    def toggle_rule(self, process_name: str):
        """Включить/выключить правило."""
        key = process_name.lower()
        if key in self.block_rules:
            self.block_rules[key].enabled = not self.block_rules[key].enabled
            self.save_rules()

    def is_blocked(self, process_name: str) -> bool:
        key = process_name.lower()
        rule = self.block_rules.get(key)
        return rule is not None and rule.enabled

    # ── Сканирование ─────────────────────────────────────────────────────────

    def get_processes(self) -> list[ProcessEntry]:
        """Получить список всех запущенных процессов."""
        entries = []
        running_names: set[str] = set()
        for proc in psutil.process_iter(
            ["pid", "name", "exe", "status", "cpu_percent", "memory_info"]
        ):
            try:
                info = proc.info
                mem_mb = (info["memory_info"].rss / 1024 / 1024) if info["memory_info"] else 0
                proc_name = info["name"] or ""
                key = proc_name.lower()
                running_names.add(key)
                desc_data = self.process_descriptions.get(key, {})

                if isinstance(desc_data, dict):
                    desc_text = desc_data.get("description", "")
                    sec_status = desc_data.get("status", "unknown")
                else:
                    desc_text = desc_data if isinstance(desc_data, str) else ""
                    sec_status = "unknown"

                entries.append(ProcessEntry(
                    pid=info["pid"],
                    name=proc_name,
                    exe=info["exe"] or "",
                    status=info["status"] or "",
                    cpu_percent=round(info["cpu_percent"] or 0, 1),
                    memory_mb=round(mem_mb, 1),
                    is_blocked=self.is_blocked(proc_name),
                    description=desc_text,
                    security_status=sec_status,
                    is_running=True,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Добавляем заблокированные, но неактивные процессы
        for key, rule in self.block_rules.items():
            if not rule.enabled or key in running_names:
                continue
            desc_data = self.process_descriptions.get(key, {})
            if isinstance(desc_data, dict):
                desc_text = desc_data.get("description", "")
                sec_status = desc_data.get("status", "unknown")
            else:
                desc_text = desc_data if isinstance(desc_data, str) else ""
                sec_status = "unknown"

            entries.append(ProcessEntry(
                pid=0,
                name=rule.name,
                exe="",
                status="Не запущен",
                cpu_percent=0.0,
                memory_mb=0.0,
                is_blocked=True,
                description=desc_text,
                security_status=sec_status,
                is_running=False,
            ))
        return sorted(entries, key=lambda e: e.name.lower())

    def kill_process(self, pid: int, name: str = "") -> bool:
        """Принудительно завершить процесс по PID."""
        if pid <= 0:
            return False
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            self._total_killed += 1
            # Увеличиваем счётчик в правиле
            key = name.lower()
            if key in self.block_rules:
                self.block_rules[key].kill_count += 1
                self.save_rules()
            self.process_killed.emit(name, pid)
            logger.info(f"Завершён процесс: {name} (PID {pid})")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
            logger.warning(f"Не удалось завершить {pid}: {e}")
            return False

    def scan_and_enforce(self):
        """
        Основной цикл:
        1. Получить список процессов
        2. Убить заблокированные
        3. Эмитить сигналы обновления
        """
        processes = self.get_processes()
        self._last_processes = processes

        # Убиваем заблокированные
        for p in processes:
            if p.is_blocked and p.is_running and p.pid > 0:
                self.kill_process(p.pid, p.name)

        # Обновляем UI
        self.processes_updated.emit(processes)
        self._emit_stats(processes)

    def _emit_stats(self, processes: list[ProcessEntry]):
        blocked_running = sum(1 for p in processes if p.is_blocked and p.is_running and p.pid > 0)
        self.stats_updated.emit({
            "total_processes": len(processes),
            "blocked_rules": len(self.block_rules),
            "blocked_running": blocked_running,
            "total_killed": self._total_killed,
        })

    # ── Таймер ───────────────────────────────────────────────────────────────

    def start_monitoring(self, interval_ms: int = 5000):
        self._scan_interval_ms = interval_ms
        self._scan_timer.start(interval_ms)
        logger.info(f"Мониторинг запущен (интервал {interval_ms}ms)")

    def stop_monitoring(self):
        self._scan_timer.stop()
        logger.info("Мониторинг остановлен")

    def set_interval(self, interval_ms: int):
        self._scan_interval_ms = interval_ms
        if self._scan_timer.isActive():
            self._scan_timer.setInterval(interval_ms)
