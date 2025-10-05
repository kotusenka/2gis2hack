#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Минимальный GUI-счётчик iPhone по Classic Bluetooth (IOBluetooth) для macOS
# - Только Classic (никакого BLE)
# - Каждую секунду запускаем ОТДЕЛЬНЫЙ подпроцесс-сканер (новый «клиент» для bluetoothd)
#   через `bt_classic_scan.py`, чтобы телефоны стабильно отвечали на запросы
# - Фильтр по имени: содержит "iPhone" (без учёта регистра)
# - Считаем только те, чья оценочная дистанция ≤ RADIUS_M (по умолчанию 5 м)
# - В окне: одна цифра без лишнего UI

import os
import sys
import time
import threading
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from PyQt6 import QtCore, QtWidgets


# Настройки через env
RADIUS_M: float = float(os.environ.get("RADIUS_M", "2.0"))
PATH_LOSS_N: float = float(os.environ.get("DIST_N", "2.0"))
TXPOWER_FALLBACK: int = int(os.environ.get("TXPOWER_FALLBACK", "-59"))
TTL_SEC: int = int(os.environ.get("TTL_SEC", "3"))  # классик обновляется часто — держим короткий TTL
NAME_SUBSTR: str = os.environ.get("NAME_SUBSTR", "iphone")
INQUIRY_LEN_SEC: int = int(os.environ.get("CLASSIC_INQ_SEC", "2"))  # длина одного цикла инквайри
TTL_GRACE_SEC: float = float(os.environ.get("TTL_GRACE_SEC", str(max(0.5, int(os.environ.get("CLASSIC_INQ_SEC", "1"))))))


@dataclass
class ClassicSeen:
    """Последнее наблюдение Classic-устройства."""

    address: str
    name: Optional[str]
    rssi: Optional[int]
    last_seen_ts: float
    last_distance_m: Optional[float]


class EventBridge(QtCore.QObject):
    """Заглушка (раньше мост для делегата). Оставлен на случай будущих расширений."""
    discovered = QtCore.pyqtSignal(dict)


def _estimate_distance_m(rssi: Optional[int]) -> Optional[float]:
    """Грубая оценка дистанции из RSSI для классика (как и с BLE — шумно).

    d = 10^((TxPower - RSSI)/(10*n))
    """
    try:
        if rssi is None:
            return None
        tp = TXPOWER_FALLBACK
        n = PATH_LOSS_N
        d = 10 ** ((tp - int(rssi)) / (10.0 * n))
        return max(0.1, min(float(d), 100.0))
    except Exception:
        return None


# ВАЖНО: вместо делегата в этом процессе мы запускаем подпроцесс
# /bt_classic_scan.py на каждый цикл — это даёт «нового клиента» bluetoothd.


class MainWindow(QtWidgets.QMainWindow):
    """Окно с одной цифрой — количество iPhone в радиусе RADIUS_M по Classic BT."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"iPhone в {RADIUS_M:.0f} м (Classic BT)")
        self.resize(420, 220)

        # Логирование в файл рядом со скриптом
        try:
            log_path = os.path.join(os.path.dirname(__file__), "bt_debug.log")
            # Базовая настройка логгера (не переинициализируем, если уже настроен)
            if not logging.getLogger().handlers:
                logging.basicConfig(
                    level=logging.DEBUG,
                    format="%(asctime)s [%(levelname)s] %(process)d %(threadName)s %(name)s: %(message)s",
                    handlers=[logging.FileHandler(log_path, encoding="utf-8")],
                )
            logging.getLogger("classic-ui").info("=== START classic_iphone_counter_qt pid=%s ===", os.getpid())
        except Exception:
            pass

        self._seen: Dict[str, ClassicSeen] = {}
        # Реестр всех айфонов (для таблицы «все», без зачистки по TTL)
        self._all: Dict[str, ClassicSeen] = {}
        self._lock = threading.RLock()

        # UI
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        vbox = QtWidgets.QVBoxLayout(central)

        self.lbl = QtWidgets.QLabel("0", self)
        self.lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        font = self.lbl.font()
        try:
            font.setPointSize(72)
        except Exception:
            pass
        self.lbl.setFont(font)
        vbox.addWidget(self.lbl, 1)

        self.sub = QtWidgets.QLabel("сканирую Classic…", self)
        self.sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self.sub)

        # Таблица со всеми айфонами (независимо от дистанции) и таймером «секунд назад»
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Имя", "Адрес", "Сек. назад"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        try:
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        except Exception:
            pass
        vbox.addWidget(self.table, 2)

        # Подпроцесс одноразового классик‑скана и таймер периодического рестарта
        self.proc = QtCore.QProcess(self)
        self.proc.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.on_proc_stdout)
        self.stdout_buf = ""

        self._start_once()
        self.timer_sp = QtCore.QTimer(self)
        self.timer_sp.setInterval(max(300, int(INQUIRY_LEN_SEC * 1000)))
        self.timer_sp.timeout.connect(self._start_once)
        self.timer_sp.start()

        # Раз в секунду — расчёт/зачистка и апдейт UI
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        # Периодический лог «кого ждём по TTL»
        self.timer_ttl = QtCore.QTimer(self)
        self.timer_ttl.setInterval(3000)
        self.timer_ttl.timeout.connect(self._log_ttl_watch)
        self.timer_ttl.start()

    @QtCore.pyqtSlot()
    def on_proc_stdout(self) -> None:
        """Парсим вывод подпроцесса bt_classic_scan.py и прокидываем события в обработчик."""
        try:
            data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        except Exception:
            return
        self.stdout_buf += data
        if len(self.stdout_buf) > 500_000:
            self.stdout_buf = self.stdout_buf[-250_000:]
        lines = self.stdout_buf.splitlines(keepends=True)
        keep_tail = ""
        for line in lines:
            if not line.endswith("\n"):
                keep_tail = line
                break
            text = line.strip()
            if not text:
                continue
            if text.startswith("[FOUND] "):
                try:
                    payload = json.loads(text[len("[FOUND] "):])
                    try:
                        logging.getLogger("classic-ui").info(
                            "FOUND name=%s addr=%s rssi=%s ts=%s",
                            payload.get("name"), payload.get("address"), payload.get("rssi"), payload.get("ts"),
                        )
                    except Exception:
                        pass
                    # подпроцесс уже отдаёт нужные поля: type/name/address/rssi/ts
                    self.on_classic_discovered(payload)
                except Exception:
                    pass
        self.stdout_buf = keep_tail

    def _start_once(self) -> None:
        """Стартуем одноразовый подпроцесс сканера — новый клиент для bluetoothd."""
        try:
            # Если прошлый ещё жив — аккуратно перезапустим
            if self.proc.state() != QtCore.QProcess.ProcessState.NotRunning:
                try:
                    self.proc.kill()
                    self.proc.waitForFinished(500)
                except Exception:
                    pass
            env = QtCore.QProcessEnvironment.systemEnvironment()
            # Лог рядом со скриптом, чтобы можно было дебажить при желании
            env.insert("BT_LOG", os.path.join(os.path.dirname(__file__), "bt_debug.log"))
            env.insert("PYTHONUNBUFFERED", "1")
            env.insert("BT_CL_INQ_SEC", str(int(INQUIRY_LEN_SEC)))
            self.proc.setProcessEnvironment(env)
            script = os.path.join(os.path.dirname(__file__), "bt_classic_scan.py")
            try:
                logging.getLogger("classic-ui").info("SCAN start spawning subprocess: %s", script)
            except Exception:
                pass
            self.proc.start(sys.executable, [script])
            # Немного подождём, чтобы получить pid, и залогируем
            try:
                self.proc.waitForStarted(250)
                pid = int(self.proc.processId()) if hasattr(self.proc, "processId") else None
                logging.getLogger("classic-ui").info("SCAN spawned pid=%s", pid)
            except Exception:
                pass
        except Exception:
            pass

    def _log_ttl_watch(self) -> None:
        """Каждые 3 секунды логируем список айфонов, которых «ждём» по TTL."""
        try:
            now = time.time()
            with self._lock:
                if not self._seen:
                    try:
                        logging.getLogger("classic-ui").info("TTL_WATCH none")
                    except Exception:
                        pass
                    return
                for rec in sorted(self._seen.values(), key=lambda r: r.last_seen_ts, reverse=True):
                    secs_since = max(0, int(now - rec.last_seen_ts))
                    secs_left = max(0, int((TTL_SEC + TTL_GRACE_SEC) - (now - rec.last_seen_ts)))
                    try:
                        logging.getLogger("classic-ui").info(
                            "TTL_WATCH addr=%s name=%s secs_since=%s secs_left=%s",
                            rec.address, rec.name, secs_since, secs_left,
                        )
                    except Exception:
                        pass
        except Exception:
            pass

    @QtCore.pyqtSlot(dict)
    def on_classic_discovered(self, payload: Dict[str, Any]) -> None:
        """Учитываем только устройства, где имя содержит NAME_SUBSTR."""
        try:
            addr: Optional[str] = payload.get("address")
            if not addr:
                return
            name: Optional[str] = payload.get("name")
            if not name:
                return
            if NAME_SUBSTR not in str(name).lower():
                return
            rssi: Optional[int] = payload.get("rssi")
            dist = _estimate_distance_m(rssi)
            rec = ClassicSeen(
                address=str(addr),
                name=str(name),
                rssi=int(rssi) if rssi is not None else None,
                last_seen_ts=float(payload.get("ts") or time.time()),
                last_distance_m=dist,
            )
            with self._lock:
                self._seen[rec.address] = rec
                self._all[rec.address] = rec
        except Exception:
            pass

    def _tick(self) -> None:
        try:
            # Прочитаем накопившийся stdout подпроцесса до прунинга, чтобы уменьшить гонку
            try:
                self.on_proc_stdout()
            except Exception:
                pass
            now = time.time()
            cnt = 0
            stale: list[str] = []
            with self._lock:
                for k, rec in self._seen.items():
                    # Грация, чтобы не выпиливать при небольших задержках между циклами
                    if now - rec.last_seen_ts > (TTL_SEC + TTL_GRACE_SEC):
                        stale.append(k)
                        continue
                    if rec.last_distance_m is not None and rec.last_distance_m <= RADIUS_M:
                        cnt += 1
                for k in stale:
                    rec = self._seen.pop(k, None)
                    try:
                        if rec is not None:
                            logging.getLogger("classic-ui").info(
                                "TTL_PRUNE addr=%s name=%s secs_since=%s",
                                rec.address, rec.name, int(now - rec.last_seen_ts),
                            )
                    except Exception:
                        pass
            self.lbl.setText(str(cnt))
            self.sub.setText(f"имя содержит 'iPhone', ≤ {RADIUS_M:.0f} м | TTL {TTL_SEC}s | inq {INQUIRY_LEN_SEC}s")

            # Обновим таблицу «все айфоны»: без учёта дистанции
            # Сортируем по времени последнего пинга (сначала самые свежие)
            rows = sorted(self._all.values(), key=lambda r: r.last_seen_ts, reverse=True)
            self.table.setRowCount(len(rows))
            for row_idx, rec in enumerate(rows):
                name = rec.name or "Без имени"
                addr = rec.address
                secs_ago = max(0, int(now - rec.last_seen_ts))

                item_name = self.table.item(row_idx, 0)
                if item_name is None:
                    item_name = QtWidgets.QTableWidgetItem()
                    self.table.setItem(row_idx, 0, item_name)
                item_name.setText(name)

                item_addr = self.table.item(row_idx, 1)
                if item_addr is None:
                    item_addr = QtWidgets.QTableWidgetItem()
                    self.table.setItem(row_idx, 1, item_addr)
                item_addr.setText(addr)

                item_sec = self.table.item(row_idx, 2)
                if item_sec is None:
                    item_sec = QtWidgets.QTableWidgetItem()
                    self.table.setItem(row_idx, 2, item_sec)
                item_sec.setData(QtCore.Qt.ItemDataRole.DisplayRole, int(secs_ago))
                item_sec.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        except Exception:
            pass


def main() -> None:
    app = QtWidgets.QApplication([])
    win = MainWindow()
    win.show()
    app.exec()


if __name__ == "__main__":
    main()


