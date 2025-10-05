#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Минимальный GUI-счётчик iPhone по BLE для macOS (PyQt6 + PyObjC)
# - Сканируем только BLE (CoreBluetooth)
# - Фильтруем по имени: содержит "iPhone" (регистр неважен)
# - Считаем только устройства с оценочной дистанцией ≤ RADIUS_M (по умолчанию 5 м)
# - Показываем таблицу всех iPhone (секунды с последнего пинга + рассчитанная дистанция)
# - Логируем старт сканирования, каждое найденное устройство, TTL‑очистку и TTL‑watch каждые 3с

import os
import sys
import time
import threading
import logging
import json
import urllib.request
import urllib.error
import socket
from dataclasses import dataclass
from typing import Any, Dict, Optional

from PyQt6 import QtCore, QtWidgets

import objc
from Foundation import NSObject, NSRunLoop
from CoreBluetooth import (
    CBCentralManager,
    CBPeripheral,
    CBAdvertisementDataLocalNameKey,
    CBAdvertisementDataTxPowerLevelKey,
    CBCentralManagerScanOptionAllowDuplicatesKey,
)


# Параметры можно подкрутить через переменные окружения
RADIUS_M: float = float(os.environ.get("RADIUS_M", "1.0"))  # радиус в метрах
PATH_LOSS_N: float = float(os.environ.get("DIST_N", "2.0"))  # показатель затухания
TXPOWER_FALLBACK: int = int(os.environ.get("TXPOWER_FALLBACK", "-59"))  # если TxPower не пришёл
TTL_SEC: int = int(os.environ.get("TTL_SEC", "8"))  # сколько секунд держим устройство «живым» без апдейтов
NAME_SUBSTR: str = os.environ.get("NAME_SUBSTR", "iphone")  # подстрока в имени, регистр неважен
TTL_GRACE_SEC: float = float(os.environ.get("TTL_GRACE_SEC", "0.5"))  # запас против гонок
RSSI_EMA_ALPHA: float = max(0.05, min(0.95, float(os.environ.get("RSSI_EMA_ALPHA", "0.35"))))
RSSI_OUTLIER_DB: int = int(os.environ.get("RSSI_OUTLIER_DB", "12"))  # порог отсечения скачков RSSI (дБ)
# Настройки стабилизации (EMA/выбросы оставляем), но без динамических лимитеров

# Конфиг API для событий автобуса (зашиваем в файл)
API_BASE_URL: str = "http://192.168.195.57:8000"
ID_BUS: str = "aaa"
API_TIMEOUT_S: float = float(os.environ.get("API_TIMEOUT_S", "5.0"))


@dataclass
class BleSeen:
    """Храним последнее наблюдение для устройства BLE."""

    identifier: str
    name: Optional[str]
    rssi: Optional[int]
    tx_power: Optional[int]
    last_seen_ts: float
    last_distance_m: Optional[float]
    smoothed_rssi: Optional[float] = None
    last_within_radius: Optional[bool] = None
    last2_within_radius: Optional[bool] = None
    reported_in_bus: Optional[bool] = None


def _post_device_event_async(id_bus: str, id_device: str, flag: bool, data: dict) -> None:
    """Отправляем событие в API в отдельном потоке, чтобы не блокировать GUI."""
    def _worker():
        try:
            url = f"{API_BASE_URL.rstrip('/')}/devices/event"
            body = {
                "id_bus": id_bus,
                "id_device": id_device,
                "data": data,
                "flag": bool(flag),
            }
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=API_TIMEOUT_S) as resp:
                _ = resp.read()
            try:
                logging.getLogger("ble-ui").info("API_EVENT ok id_device=%s flag=%s", id_device, flag)
                # Человечный лог
                action = "1 чел зашел" if flag else "1 чел вышел"
                try:
                    dist = data.get("distance") if isinstance(data, dict) else None
                except Exception:
                    dist = None
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                logging.getLogger("ble-ui").info("%s | %s (bus=%s, device=%s, dist=%s)", ts, action, id_bus, id_device, dist)
                try:
                    print(f"[BUS] {ts} {action}: bus={id_bus} device={id_device} dist={dist}")
                except Exception:
                    pass
            except Exception:
                pass
        except urllib.error.HTTPError as e:
            try:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                logging.getLogger("ble-ui").error("%s | API_EVENT http %s: %s", ts, e.code, e.read().decode("utf-8", errors="replace"))
            except Exception:
                pass
        except urllib.error.URLError as e:
            # Таймауты сюда тоже попадают (reason=socket.timeout)
            try:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(e.reason, socket.timeout):
                    logging.getLogger("ble-ui").error("%s | API_EVENT TIMEOUT %.1fs (bus=%s device=%s)", ts, API_TIMEOUT_S, id_bus, id_device)
                    try:
                        print(f"[BUS][ERROR] {ts} TIMEOUT {API_TIMEOUT_S:.1f}s bus={id_bus} device={id_device}")
                    except Exception:
                        pass
                else:
                    logging.getLogger("ble-ui").error("%s | API_EVENT urlerror: %s", ts, e)
            except Exception:
                pass
        except Exception as e:
            try:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                logging.getLogger("ble-ui").error("%s | API_EVENT fail: %s", ts, e)
            except Exception:
                pass
    try:
        threading.Thread(target=_worker, name="api-event", daemon=True).start()
    except Exception:
        pass


class EventBridge(QtCore.QObject):
    """Мост: события из делегата CoreBluetooth → сигналы Qt."""

    discovered = QtCore.pyqtSignal(dict)


def _estimate_distance_m(rssi: Optional[int], tx_power: Optional[int]) -> Optional[float]:
    """Оцениваем расстояние по простейшей формуле затухания.

    d = 10^((TxPower - RSSI)/(10*n))
    Возвращаем None, если посчитать нельзя.
    """
    try:
        if rssi is None:
            return None
        # ВАЖНО: CBAdvertisementDataTxPowerLevelKey — это мощность передатчика, а не «RSSI на 1 м».
        # Для нашей формулы годится только калиброванное «Measured Power» (обычно -59..-65)
        # Поэтому используем tx_power ТОЛЬКО если он выглядит реалистично (-80..-30), иначе фоллбек.
        tp = TXPOWER_FALLBACK
        try:
            if tx_power is not None:
                txi = int(tx_power)
                if -80 <= txi <= -30:
                    tp = txi
        except Exception:
            pass
        n = PATH_LOSS_N
        d = 10 ** ((tp - int(rssi)) / (10.0 * n))
        # Немного ограничим адовые выбросы
        return max(0.1, min(float(d), 100.0))
    except Exception:
        return None


class BLEDelegate(NSObject):
    """Делегат CoreBluetooth: на каждое обнаружение шлём payload в Qt."""

    def initWithBridge_(self, bridge: EventBridge):
        self = objc.super(BLEDelegate, self).init()
        if self is None:
            return None
        self.bridge = bridge
        self.manager = CBCentralManager.alloc().initWithDelegate_queue_(self, None)
        return self

    def centralManagerDidUpdateState_(self, central):
        try:
            state = central.state()
        except Exception:
            state = getattr(central, "state", lambda: None)()
        # 5 == poweredOn
        if state == 5:
            try:
                logging.getLogger("ble-ui").info("BLE_SCAN_START poweredOn")
            except Exception:
                pass
            try:
                # AllowDuplicates=True, чтобы чаще обновлялся RSSI/дистанция
                self.manager.scanForPeripheralsWithServices_options_(
                    None, {CBCentralManagerScanOptionAllowDuplicatesKey: True}
                )
            except Exception:
                self.manager.scanForPeripheralsWithServices_options_(None, None)

    def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(
        self, central, peripheral: CBPeripheral, advertisementData, RSSI
    ):
        try:
            per_id = str(peripheral.identifier()) if hasattr(peripheral, "identifier") else None
            name = None
            try:
                name = peripheral.name() if hasattr(peripheral, "name") else None
            except Exception:
                name = None
            # Фоллбек: чтение имени из рекламы, если отдали локальное имя
            if not name and advertisementData is not None and CBAdvertisementDataLocalNameKey in advertisementData:
                try:
                    name = advertisementData.get(CBAdvertisementDataLocalNameKey)
                except Exception:
                    pass

            # TxPower из рекламы, если отдали
            txp = None
            try:
                if advertisementData is not None and CBAdvertisementDataTxPowerLevelKey in advertisementData:
                    txp = int(advertisementData.get(CBAdvertisementDataTxPowerLevelKey))
            except Exception:
                txp = None

            payload = {
                "identifier": per_id,
                "name": name,
                "rssi": int(RSSI) if RSSI is not None else None,
                "tx_power": txp,
                "ts": time.time(),
            }
            try:
                logging.getLogger("ble-ui").info(
                    "FOUND name=%s id=%s rssi=%s tx=%s ts=%s",
                    payload.get("name"), payload.get("identifier"), payload.get("rssi"), payload.get("tx_power"), payload.get("ts"),
                )
            except Exception:
                pass
            self.bridge.discovered.emit(payload)
        except Exception:
            pass


class AppleBLEThread(threading.Thread):
    """Фоновый поток: держим runloop macOS и BLE-делегат."""

    def __init__(self, bridge: EventBridge):
        super().__init__(name="AppleBLE", daemon=True)
        self.bridge = bridge

    def run(self) -> None:
        try:
            self.ble = BLEDelegate.alloc().initWithBridge_(self.bridge)
            NSRunLoop.currentRunLoop().run()
        except Exception:
            pass


class MainWindow(QtWidgets.QMainWindow):
    """Окно с одной крупной цифрой — сколько iPhone в радиусе RADIUS_M."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"iPhone в {RADIUS_M:.0f} м (BLE)")
        self.resize(420, 220)

        # Логирование в файл рядом со скриптом
        try:
            log_path = os.path.join(os.path.dirname(__file__), "bt_debug.log")
            if not logging.getLogger().handlers:
                logging.basicConfig(
                    level=logging.DEBUG,
                    format="%(asctime)s [%(levelname)s] %(process)d %(threadName)s %(name)s: %(message)s",
                    handlers=[logging.FileHandler(log_path, encoding="utf-8")],
                )
            logging.getLogger("ble-ui").info("=== START ble_iphone_counter_qt pid=%s ===", os.getpid())
        except Exception:
            pass

        # Модель наблюдений BLE (ключ — identifier)
        self._seen: Dict[str, BleSeen] = {}
        self._all: Dict[str, BleSeen] = {}
        self._lock = threading.RLock()
        # Персистентное состояние «что мы уже репортили» по каждому устройству
        self._reported_flags: Dict[str, bool] = {}

        # UI: одна большая надпись по центру
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

        # Служебная мелкая строка состояния
        self.sub = QtWidgets.QLabel("сканирую BLE…", self)
        self.sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(self.sub)

        # Таблица всех iPhone: Имя | ID | RSSI | Дистанция (м) | Сек. назад
        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Имя", "ID", "RSSI", "Дистанция (м)", "Сек. назад"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        try:
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
            for col in (1, 2, 3, 4):
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        except Exception:
            pass
        vbox.addWidget(self.table, 2)

        # Панель деталей: показываем, что именно шлём в API для выбранного устройства
        self.details = QtWidgets.QPlainTextEdit(self)
        self.details.setReadOnly(True)
        vbox.addWidget(self.details, 1)
        try:
            self.table.itemSelectionChanged.connect(self._update_details)
        except Exception:
            pass

        # Мост сигналов и фоновый поток BLE
        self.bridge = EventBridge()
        self.bridge.discovered.connect(self.on_ble_discovered)
        self.worker = AppleBLEThread(self.bridge)
        self.worker.start()

        # Таймер обновления счётчика и зачистки устаревших
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        # TTL watch лог раз в 3 сек
        self.timer_ttl = QtCore.QTimer(self)
        self.timer_ttl.setInterval(3000)
        self.timer_ttl.timeout.connect(self._log_ttl_watch)
        self.timer_ttl.start()

    @QtCore.pyqtSlot(dict)
    def on_ble_discovered(self, payload: Dict[str, Any]) -> None:
        """Получили событие от делегата — обновим запись при совпадении фильтра имени."""
        try:
            per_id: Optional[str] = payload.get("identifier")
            if not per_id:
                return
            name: Optional[str] = payload.get("name")
            rssi: Optional[int] = payload.get("rssi")
            txp: Optional[int] = payload.get("tx_power")
            ts: float = float(payload.get("ts") or time.time())

            # Фильтр по имени (только те, где в имени есть подстрока)
            if not name:
                return
            if NAME_SUBSTR not in str(name).lower():
                return

            # Сглаживание RSSI: EMA + отсечение выбросов
            with self._lock:
                prev: Optional[BleSeen] = self._seen.get(str(per_id))
            raw_rssi = int(rssi) if rssi is not None else None
            smoothed_rssi = None
            if raw_rssi is not None:
                if prev and prev.smoothed_rssi is not None:
                    # Отсечём внезапные скачки
                    r_eff = raw_rssi
                    try:
                        if abs(raw_rssi - prev.smoothed_rssi) > RSSI_OUTLIER_DB:
                            sign = 1 if (raw_rssi - prev.smoothed_rssi) > 0 else -1
                            r_eff = int(prev.smoothed_rssi + sign * RSSI_OUTLIER_DB)
                    except Exception:
                        pass
                    smoothed_rssi = RSSI_EMA_ALPHA * r_eff + (1.0 - RSSI_EMA_ALPHA) * float(prev.smoothed_rssi)
                else:
                    smoothed_rssi = float(raw_rssi)

            # Дистанция из сглаженного RSSI
            dist_new = _estimate_distance_m(int(smoothed_rssi) if smoothed_rssi is not None else raw_rssi, txp)

            # Двойная проверка на выход за радиус: выкидываем только если два последних пинга вне радиуса
            within = (dist_new is not None and dist_new <= RADIUS_M)
            last_within = None
            last2_within = None
            if prev is not None:
                last_within = within
                # last2 — предыдущее значение last_within_radius
                last2_within = prev.last_within_radius
            else:
                last_within = within
                last2_within = None

            # Предыдущее состояние репорта берём из персистентного словаря (не зависящего от TTL очистки)
            prev_reported = None
            try:
                prev_reported = self._reported_flags.get(str(per_id))
            except Exception:
                prev_reported = None

            rec = BleSeen(
                identifier=str(per_id),
                name=str(name) if name is not None else None,
                rssi=raw_rssi,
                tx_power=int(txp) if txp is not None else None,
                last_seen_ts=ts,
                last_distance_m=dist_new,
                smoothed_rssi=smoothed_rssi,
                last_within_radius=last_within,
                last2_within_radius=last2_within,
                reported_in_bus=prev_reported,
            )
            with self._lock:
                self._seen[rec.identifier] = rec
                self._all[rec.identifier] = rec
        except Exception:
            pass

    def _tick(self) -> None:
        """Раз в секунду чистим устаревшие и считаем тех, кто в радиусе."""
        try:
            now = time.time()
            count = 0
            stale: list[str] = []
            with self._lock:
                for key, rec in self._seen.items():
                    # зачистка старых записей
                    if now - rec.last_seen_ts > (TTL_SEC + TTL_GRACE_SEC):
                        stale.append(key)
                        continue
                    # Логика «двух последних пингов»: выкидываем только если два последних были вне радиуса
                    inside_now = None
                    if rec.last_within_radius is not None:
                        inside_now = bool(rec.last_within_radius or (rec.last2_within_radius is True))
                    else:
                        inside_now = (rec.last_distance_m is not None and rec.last_distance_m <= RADIUS_M)
                    if inside_now:
                        count += 1

                    # Репортим для всех iPhone динамически по их identifier
                    try:
                        prev_flag = rec.reported_in_bus
                        cur_flag = bool(inside_now)
                        # Посылаем ТОЛЬКО при переходе состояния
                        if prev_flag is None:
                            # Инициализация: только вход репортим, выход — нет
                            if cur_flag is True:
                                _post_device_event_async(
                                    ID_BUS,
                                    key,
                                    True,
                                    {
                                        "distance": rec.last_distance_m,
                                        "rssi": rec.rssi,
                                        "smoothed_rssi": rec.smoothed_rssi,
                                        "radius_m": RADIUS_M,
                                        "ts": rec.last_seen_ts,
                                        "name": rec.name,
                                    },
                                )
                                rec.reported_in_bus = True
                                try:
                                    self._reported_flags[key] = True
                                except Exception:
                                    pass
                            else:
                                # Зафиксируем базовое состояние как "снаружи"
                                rec.reported_in_bus = False
                                try:
                                    self._reported_flags[key] = False
                                except Exception:
                                    pass
                        elif prev_flag != cur_flag:
                            # Переход True->False или False->True — репортим
                            _post_device_event_async(
                                ID_BUS,
                                key,
                                cur_flag,
                                {
                                    "distance": rec.last_distance_m,
                                    "rssi": rec.rssi,
                                    "smoothed_rssi": rec.smoothed_rssi,
                                    "radius_m": RADIUS_M,
                                    "ts": rec.last_seen_ts,
                                    "name": rec.name,
                                },
                            )
                            rec.reported_in_bus = cur_flag
                            try:
                                self._reported_flags[key] = cur_flag
                            except Exception:
                                pass
                        else:
                            # Состояние не поменялось — молчим
                            pass
                    except Exception:
                        pass
                for key in stale:
                    rec = self._seen.pop(key, None)
                    try:
                        if rec is not None:
                            logging.getLogger("ble-ui").info(
                                "TTL_PRUNE id=%s name=%s secs_since=%s",
                                rec.identifier, rec.name, int(now - rec.last_seen_ts),
                            )
                    except Exception:
                        pass
            # Обновим надписи
            self.lbl.setText(str(count))
            self.sub.setText(f"имя содержит 'iPhone', ≤ {RADIUS_M:.0f} м | TTL {TTL_SEC}s")

            # Обновим таблицу всех iPhone
            rows = sorted(self._all.values(), key=lambda r: r.last_seen_ts, reverse=True)
            self.table.setRowCount(len(rows))
            for row_idx, rec in enumerate(rows):
                name = rec.name or "Без имени"
                ident = rec.identifier
                rssi_val = rec.rssi if rec.rssi is not None else None
                dist_val = rec.last_distance_m
                secs_ago = max(0, int(now - rec.last_seen_ts))

                # Имя
                item0 = self.table.item(row_idx, 0) or QtWidgets.QTableWidgetItem()
                item0.setText(name)
                if self.table.item(row_idx, 0) is None:
                    self.table.setItem(row_idx, 0, item0)
                # ID
                item1 = self.table.item(row_idx, 1) or QtWidgets.QTableWidgetItem()
                item1.setText(ident)
                try:
                    item1.setData(QtCore.Qt.ItemDataRole.UserRole, ident)
                except Exception:
                    pass
                if self.table.item(row_idx, 1) is None:
                    self.table.setItem(row_idx, 1, item1)
                # RSSI
                item2 = self.table.item(row_idx, 2) or QtWidgets.QTableWidgetItem()
                item2.setData(QtCore.Qt.ItemDataRole.DisplayRole, int(rssi_val) if rssi_val is not None else 0)
                item2.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if self.table.item(row_idx, 2) is None:
                    self.table.setItem(row_idx, 2, item2)
                # Дистанция
                item3 = self.table.item(row_idx, 3) or QtWidgets.QTableWidgetItem()
                item3.setData(QtCore.Qt.ItemDataRole.DisplayRole, float(f"{(dist_val if dist_val is not None else 0.0):.2f}"))
                item3.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if self.table.item(row_idx, 3) is None:
                    self.table.setItem(row_idx, 3, item3)
                # Сек. назад
                item4 = self.table.item(row_idx, 4) or QtWidgets.QTableWidgetItem()
                item4.setData(QtCore.Qt.ItemDataRole.DisplayRole, int(secs_ago))
                item4.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                if self.table.item(row_idx, 4) is None:
                    self.table.setItem(row_idx, 4, item4)
        except Exception:
            pass

    def _update_details(self) -> None:
        """Показываем детальную инфу по выбранному устройству (что уходит в API)."""
        try:
            sel = self.table.selectionModel()
            if not sel:
                return
            rows = sel.selectedRows()
            if not rows:
                return
            row = rows[0].row()
            id_item = self.table.item(row, 1)
            ident = None
            if id_item is not None:
                ident = id_item.data(QtCore.Qt.ItemDataRole.UserRole) or id_item.text()
            if not ident:
                return
            with self._lock:
                rec = self._all.get(str(ident))
            if not rec:
                return
            now = time.time()
            inside_now = None
            if rec.last_within_radius is not None:
                inside_now = bool(rec.last_within_radius or (rec.last2_within_radius is True))
            else:
                inside_now = (rec.last_distance_m is not None and rec.last_distance_m <= RADIUS_M)
            preview = {
                "id_bus": ID_BUS,
                "id_device": str(ident),
                "flag": bool(inside_now),
                "data": {
                    "distance": rec.last_distance_m,
                    "rssi": rec.rssi,
                    "smoothed_rssi": rec.smoothed_rssi,
                    "radius_m": RADIUS_M,
                    "ts": rec.last_seen_ts,
                    "name": rec.name,
                    "secs_ago": int(max(0, now - rec.last_seen_ts)),
                },
            }
            try:
                self.details.setPlainText(json.dumps(preview, ensure_ascii=False, indent=2))
            except Exception:
                self.details.setPlainText(str(preview))
        except Exception:
            pass

    def _log_ttl_watch(self) -> None:
        """Каждые 3 секунды — логируем кого ждём по TTL."""
        try:
            now = time.time()
            with self._lock:
                if not self._seen:
                    try:
                        logging.getLogger("ble-ui").info("TTL_WATCH none")
                    except Exception:
                        pass
                    return
                for rec in sorted(self._seen.values(), key=lambda r: r.last_seen_ts, reverse=True):
                    secs_since = max(0, int(now - rec.last_seen_ts))
                    secs_left = max(0, int((TTL_SEC + TTL_GRACE_SEC) - (now - rec.last_seen_ts)))
                    try:
                        logging.getLogger("ble-ui").info(
                            "TTL_WATCH id=%s name=%s secs_since=%s secs_left=%s",
                            rec.identifier, rec.name, secs_since, secs_left,
                        )
                    except Exception:
                        pass
        except Exception:
            pass


def main() -> None:
    app = QtWidgets.QApplication([])
    win = MainWindow()
    win.show()
    app.exec()


if __name__ == "__main__":
    main()


