#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Простой GUI на PyQt6 для BLE-сканера (без Tkinter)
# - Список устройств без дублей, автообновление
# - Клик по устройству: детальная инфа
# - Оценка расстояния по RSSI/TxPower

import asyncio
import os
import sys
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

from PyQt6 import QtCore, QtWidgets

# PyObjC фреймворки для совпадения логики с bt_scan_mac.py
import objc
from Foundation import NSObject, NSRunLoop
from CoreBluetooth import (
    CBCentralManager,
    CBPeripheral,
    CBUUID,
    CBAdvertisementDataLocalNameKey,
    CBAdvertisementDataManufacturerDataKey,
    CBAdvertisementDataServiceUUIDsKey,
    CBAdvertisementDataServiceDataKey,
    CBAdvertisementDataOverflowServiceUUIDsKey,
    CBAdvertisementDataTxPowerLevelKey,
    CBAdvertisementDataIsConnectable,
    CBAdvertisementDataSolicitedServiceUUIDsKey,
    CBCentralManagerScanOptionAllowDuplicatesKey,
)
try:
    from CoreBluetooth import CBAdvertisementDataAppearanceKey  # type: ignore
except Exception:
    CBAdvertisementDataAppearanceKey = None  # type: ignore
from IOBluetooth import IOBluetoothDeviceInquiry


@dataclass
class DeviceRecord:
    """Все известные данные об устройстве."""

    address: str
    name: Optional[str] = None
    rssi: Optional[int] = None
    tx_power: Optional[int] = None
    bt_type: Optional[str] = None  # BLE или Classic
    manufacturer_data_hex: Dict[int, str] = field(default_factory=dict)
    service_uuids: List[str] = field(default_factory=list)
    service_data_hex: Dict[str, str] = field(default_factory=dict)
    last_seen_ts: float = field(default_factory=lambda: time.time())
    raw_advertisement: Dict[str, Any] = field(default_factory=dict)
    # Для Classic Bluetooth — битовая маска Class of Device
    class_of_device: Optional[int] = None
    # Единая категория для отображения (Телефон/Ноутбук/ПК/Наушники/ТВ/Неизвестно)
    category: Optional[str] = None
    # BLE Appearance (если устройство его отдало)
    appearance: Optional[int] = None


def _decode_class_of_device(cod: Optional[int]) -> Optional[str]:
    """Декодируем 24-битный Class of Device в человекочитаемый тип.

    Формат CoD:
    - биты 8..12: Major Device Class
    - биты 2..7:  Minor Device Class (зависит от Major)
    - биты 13..23: Major Service Classes (нам тут редко нужны)
    Возвращаем короткую строку, например: "Ноутбук", "Смартфон", "Наушники".
    """
    if cod is None:
        return None
    try:
        major = (cod >> 8) & 0x1F
        minor = (cod >> 2) & 0x3F

        major_names = {
            0x01: "Компьютер",
            0x02: "Телефон",
            0x03: "LAN/Сеть",
            0x04: "Аудио/Видео",
            0x05: "Периферия",
            0x06: "Изображение",
            0x07: "Носимое",
            0x08: "Игрушка",
            0x09: "Здоровье",
        }

        if major == 0x01:  # Computer
            computer_minor = {
                0x01: "Стационарный ПК",
                0x02: "Сервер",
                0x03: "Ноутбук",
                0x04: "КПК/Handheld",
                0x05: "Палм/Органайзер",
                0x06: "Планшет",
            }
            return computer_minor.get(minor, major_names.get(major, "Компьютер"))

        if major == 0x02:  # Phone
            phone_minor = {
                0x01: "Сотовый",
                0x02: "Кнопочный",
                0x03: "Смартфон",
                0x04: "Модем/адаптер",
                0x05: "ISDN",
            }
            return phone_minor.get(minor, major_names.get(major, "Телефон"))

        if major == 0x04:  # Audio/Video
            av_minor = {
                0x01: "Наушники",
                0x02: "Громкая связь",
                0x04: "Микрофон",
                0x06: "Динамик",
                0x0B: "Наушники-гарнитура",
                0x0C: "Портативный аудио",
                0x10: "Видео дисплей/класс",
            }
            return av_minor.get(minor, major_names.get(major, "Аудио/Видео"))

        if major == 0x05:  # Peripheral
            per_minor = {
                0x01: "Клавиатура",
                0x02: "Мышь",
                0x03: "Клава+Мышь",
            }
            # Верхние биты minor у периферии кодируют подтипы; упростим
            base = minor & 0x0F
            return per_minor.get(base, major_names.get(major, "Периферия"))

        if major == 0x07:  # Wearable
            wearable_minor = {
                0x01: "Наручное",
                0x02: "Пейджер",
                0x03: "Куртка",
                0x04: "Шлем",
                0x05: "Очки",
            }
            return wearable_minor.get(minor, major_names.get(major, "Носимое"))

        # Всё остальное — вернём название major-категории
        return major_names.get(major, None)
    except Exception:
        return None


def _company_from_mfr_hex(mfr_hex: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    """Парсим manufacturer data и достаём Company Identifier (младший порядок байт).
    Возвращаем (company_id, vendor_name).
    """
    if not mfr_hex or len(mfr_hex) < 4:
        return None, None
    try:
        # первые 2 байта в little-endian → Company ID
        cid_le = int(mfr_hex[:4], 16)
        # развернём в big-endian для привычного вида
        cid = ((cid_le & 0xFF) << 8) | ((cid_le >> 8) & 0xFF)
    except Exception:
        return None, None
    vendor_map = {
        0x004C: "Apple",
        0x0006: "Microsoft",
        0x0002: "Intel",
        0x0059: "Nordic",
        0x0075: "Samsung",
        0x00E0: "Google",
    }
    return cid, vendor_map.get(cid)


def _guess_ble_category(service_uuids: List[str], mfr_hex: Optional[str], vendor: Optional[str]) -> Optional[str]:
    """Грубая эвристика для BLE: пытаемся понять, телефон это или нет.
    Без коннекта это почти невозможно определить на 100%, поэтому даём best-effort.
    Возвращаем одну из категорий или None.
    """
    try:
        uuids_lower = {u.lower() for u in (service_uuids or [])}
        # Некоторые признаки телефонов: Apple/Google/Samsung, сервисы смартфона/телеофонии редко явно светятся,
        # поэтому полагаемся на вендора.
        if vendor in ("Apple", "Google", "Samsung"):
            return "Телефон"  # чаще всего это смартфон; ноуты BLE светятся реже

        # Умные часы/браслеты часто имеют стандартные сервисы Heart Rate / Current Time
        known_wear = {"0000180d-0000-1000-8000-00805f9b34fb", "00001805-0000-1000-8000-00805f9b34fb"}
        if uuids_lower & known_wear:
            return "Носимое"

        # Аудио-устройства часто не connectable как центральный; тяжело отличить без CoD
        return None
    except Exception:
        return None


def _appearance_category(appearance: Optional[int]) -> Optional[str]:
    """Маппинг BLE Appearance (16-бит) → категория.
    Используем укрупнённые классы.
    """
    if appearance is None:
        return None
    try:
        # Высокие 10 бит — категория, младшие 6 — подтип. Нас интересует категория.
        category = (appearance >> 6) & 0x03FF
        # Из спецификации SIG (сокращённо)
        mapping = {
            0x0001: "Телефон",
            0x0002: "Компьютер",
            0x0003: "Часы",
            0x0004: "Дисплей",
            0x0005: "Пульт",
            0x0006: "Датчик",
            0x0007: "Спорт/Фитнес",
            0x0008: "Игрушка",
            0x0009: "Здоровье",
            0x000A: "Камера",
            0x000B: "Медиа-плеер",
            0x000C: "Домашняя техника",
            0x000D: "Устройство освещения",
            0x000E: "Плата/Beacon",
        }
        cat = mapping.get(category)
        # Нормализуем под наши ключевые классы
        if cat == "Телефон":
            return "Телефон"
        if cat == "Компьютер":
            return "ПК"
        if cat == "Часы":
            return "Носимое"
        return cat
    except Exception:
        return None


def _unified_category(rec: 'DeviceRecord', ble_heuristics: bool = False) -> str:
    """Единая категория для таблицы.
    Приоритет:
    1) Classic CoD → точная категория
    2) BLE: по вендору и сервисам
    3) Фоллбек по типу транспорта
    """
    # Classic: самый надёжный
    if rec.bt_type == "Classic" and rec.class_of_device is not None:
        dec = _decode_class_of_device(rec.class_of_device)
        if dec:
            # Нормализуем ПК/Ноутбук
            if dec in ("Стационарный ПК", "Сервер"):
                return "ПК"
            if dec == "Ноутбук":
                return "Ноутбук"
            if dec in ("Смартфон", "Сотовый", "Кнопочный"):
                return "Телефон"
            return dec

    # BLE: сначала Appearance, потом вендор/сервисы
    if rec.bt_type == "BLE":
        app_cat = _appearance_category(rec.appearance)
        if app_cat:
            return app_cat
    if rec.bt_type == "BLE" and ble_heuristics:
        mfr = rec.manufacturer_data_hex.get(0) if rec.manufacturer_data_hex else None
        cid, vendor = _company_from_mfr_hex(mfr)
        ble_guess = _guess_ble_category(rec.service_uuids, mfr, vendor)
        if ble_guess:
            return ble_guess

    # Фоллбеки
    if rec.bt_type == "Classic":
        return "Устройство BT"
    if rec.bt_type == "BLE":
        return "BLE устройство"
    return "Неизвестно"


class EventBridge(QtCore.QObject):
    """Мост из делегатов PyObjC в Qt."""
    discovered = QtCore.pyqtSignal(dict)


def _nsdata_to_hex(value: Any) -> Optional[str]:
    try:
        if value is None:
            return None
        if hasattr(value, "bytes") and hasattr(value, "length"):
            return bytes(value).hex()
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).hex()
    except Exception:
        return None
    return None


def _cbuuid_to_str(u: Any) -> Optional[str]:
    try:
        if hasattr(u, "UUIDString"):
            return str(u.UUIDString())
        return str(u)
    except Exception:
        return None


def serialize_ble_advertisement(ad_data: Dict[Any, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        if CBAdvertisementDataLocalNameKey in ad_data:
            out["local_name"] = ad_data.get(CBAdvertisementDataLocalNameKey)
        if CBAdvertisementDataIsConnectable in ad_data:
            out["is_connectable"] = bool(ad_data.get(CBAdvertisementDataIsConnectable))
        if CBAdvertisementDataTxPowerLevelKey in ad_data:
            out["tx_power"] = ad_data.get(CBAdvertisementDataTxPowerLevelKey)
        if CBAdvertisementDataManufacturerDataKey in ad_data:
            out["manufacturer_data_hex"] = _nsdata_to_hex(ad_data.get(CBAdvertisementDataManufacturerDataKey))
        if CBAdvertisementDataServiceUUIDsKey in ad_data:
            uuids = ad_data.get(CBAdvertisementDataServiceUUIDsKey) or []
            out["service_uuids"] = [u for u in (_cbuuid_to_str(x) for x in uuids) if u is not None]
        if CBAdvertisementDataOverflowServiceUUIDsKey in ad_data:
            uuids = ad_data.get(CBAdvertisementDataOverflowServiceUUIDsKey) or []
            out["overflow_service_uuids"] = [u for u in (_cbuuid_to_str(x) for x in uuids) if u is not None]
        if CBAdvertisementDataSolicitedServiceUUIDsKey in ad_data:
            uuids = ad_data.get(CBAdvertisementDataSolicitedServiceUUIDsKey) or []
            out["solicited_service_uuids"] = [u for u in (_cbuuid_to_str(x) for x in uuids) if u is not None]
        if CBAdvertisementDataServiceDataKey in ad_data:
            svc_data = ad_data.get(CBAdvertisementDataServiceDataKey) or {}
            nice = {}
            try:
                for k, v in svc_data.items():
                    key_str = _cbuuid_to_str(k) or str(k)
                    nice[key_str] = _nsdata_to_hex(v)
            except Exception:
                pass
            out["service_data_hex"] = nice
        # Appearance, если доступен у CoreBluetooth
        try:
            if CBAdvertisementDataAppearanceKey and CBAdvertisementDataAppearanceKey in ad_data:
                out["appearance"] = int(ad_data.get(CBAdvertisementDataAppearanceKey))
        except Exception:
            pass
    except Exception:
        pass
    return out


class BLEDelegate(NSObject):
    """Делегат CoreBluetooth → шлёт события в Qt."""

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
        if state == 5:
            try:
                # Без AllowDuplicates — меньше событий → меньше лагов в GUI
                self.manager.scanForPeripheralsWithServices_options_(None, None)
            except Exception:
                self.manager.scanForPeripheralsWithServices_options_(None, None)

    def centralManager_didDiscoverPeripheral_advertisementData_RSSI_(
        self, central, peripheral: CBPeripheral, advertisementData, RSSI
    ):
        try:
            per_id = str(peripheral.identifier()) if hasattr(peripheral, "identifier") else None
            try:
                name = peripheral.name() if hasattr(peripheral, "name") else None
            except Exception:
                name = None
            ad = serialize_ble_advertisement(advertisementData or {})
            payload = {
                "type": "BLE",
                "ts": time.time(),
                "name": name,
                "identifier": per_id,
                "rssi": int(RSSI) if RSSI is not None else None,
                "advertisement": ad,
            }
            self.bridge.discovered.emit(payload)
        except Exception:
            pass


class ClassicDelegate(NSObject):
    """Делегат IOBluetooth → шлёт события в Qt."""

    def initWithBridge_(self, bridge: EventBridge):
        self = objc.super(ClassicDelegate, self).init()
        if self is None:
            return None
        self.bridge = bridge
        self.inquiry = IOBluetoothDeviceInquiry.inquiryWithDelegate_(self)
        try:
            self.inquiry.setUpdateNewDeviceNames_(True)
            self.inquiry.setInquiryLength_(10)
        except Exception:
            pass
        return self

    def start(self):
        try:
            self.inquiry.start()
        except Exception:
            pass

    def deviceInquiryStarted_(self, sender):
        # можно показать статус, но сейчас не надо
        pass

    def deviceInquiryDeviceFound_device_(self, sender, device):
        try:
            payload: Dict[str, Any] = {"type": "Classic", "ts": time.time()}
            try:
                payload["name"] = device.name()
            except Exception:
                pass
            try:
                payload["address"] = device.addressString()
            except Exception:
                pass
            for attr in ("isPaired", "isConnected", "isFavorite"):
                try:
                    payload[attr] = bool(getattr(device, attr)())
                except Exception:
                    pass
            try:
                cod = device.classOfDevice()
                payload["class_of_device"] = int(cod) if cod is not None else None
            except Exception:
                pass
            for rssi_attr in ("RSSI", "rawRSSI"):
                try:
                    rssi_val = getattr(device, rssi_attr)()
                    if rssi_val is not None:
                        payload["rssi"] = int(rssi_val)
                        break
                except Exception:
                    pass
            self.bridge.discovered.emit(payload)
        except Exception:
            pass

    def deviceInquiryComplete_error_aborted_(self, sender, error, aborted):
        try:
            self.start()
        except Exception:
            pass


class AppleBTThread(threading.Thread):
    """Запускает делегаты BLE и Classic в собственном runloop и шлёт события в Qt."""

    def __init__(self, bridge: EventBridge):
        super().__init__(name="AppleBTThread", daemon=True)
        self.bridge = bridge

    def run(self):
        # Создаём делегаты и запускаем inquiry; BLE сам стартанёт при poweredOn
        self.ble = BLEDelegate.alloc().initWithBridge_(self.bridge)
        self.cl = ClassicDelegate.alloc().initWithBridge_(self.bridge)
        try:
            self.cl.start()
        except Exception:
            pass
        try:
            NSRunLoop.currentRunLoop().run()
        except Exception:
            pass


class MainWindow(QtWidgets.QMainWindow):
    """Главное окно с разделением: слева список, справа детали."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("BLE Scanner (PyQt6)")
        self.resize(980, 600)

        self.devices: Dict[str, DeviceRecord] = {}
        # RLock, чтобы избежать самодедлока при вложенных сигналах в одном потоке GUI
        self.devices_lock = threading.RLock()
        self.seen_all: set[str] = set()
        self.total_seen: int = 0

        # Параметры расстояния
        self.path_loss_n = 2.0
        self.tx_power_fallback = -59
        # Раздельные TTL (будут подстраиваться под авто‑рестарт)
        self.prune_ble_seconds = 8
        self.prune_classic_seconds = 8
        # Длина цикла Classic-инквайри (сек) — должна совпадать с BT_CL_INQ_SEC
        self.classic_cycle_seconds = 15

        # UI
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)

        left_panel = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_panel)

        controls = QtWidgets.QHBoxLayout()
        self.btn_toggle = QtWidgets.QPushButton("Стоп")
        self.btn_toggle.clicked.connect(self.on_toggle_scan)
        controls.addWidget(self.btn_toggle)

        controls.addWidget(QtWidgets.QLabel("n:"))
        self.spin_n = QtWidgets.QDoubleSpinBox()
        self.spin_n.setRange(1.5, 4.0)
        self.spin_n.setSingleStep(0.1)
        self.spin_n.setValue(self.path_loss_n)
        self.spin_n.valueChanged.connect(self.on_n_changed)
        controls.addWidget(self.spin_n)

        controls.addWidget(QtWidgets.QLabel("TxPower:"))
        self.spin_tx = QtWidgets.QSpinBox()
        self.spin_tx.setRange(-100, -30)
        self.spin_tx.setValue(self.tx_power_fallback)
        self.spin_tx.valueChanged.connect(self.on_tx_changed)
        controls.addWidget(self.spin_tx)

        controls.addWidget(QtWidgets.QLabel("TTL, c:"))
        self.spin_ttl = QtWidgets.QSpinBox()
        self.spin_ttl.setRange(2, 300)
        self.spin_ttl.setValue(self.prune_ble_seconds)
        self.spin_ttl.valueChanged.connect(self.on_ttl_changed)
        controls.addWidget(self.spin_ttl)

        controls.addWidget(QtWidgets.QLabel("Classic TTL, c:"))
        self.spin_ttl_cl = QtWidgets.QSpinBox()
        self.spin_ttl_cl.setRange(10, 1800)
        self.spin_ttl_cl.setValue(self.prune_classic_seconds)
        self.spin_ttl_cl.valueChanged.connect(lambda v: setattr(self, 'prune_classic_seconds', int(v)))
        controls.addWidget(self.spin_ttl_cl)

        # Переключатель BLE-эвристики (по умолчанию выкл — учитываем только Appearance)
        self.ble_heuristics_enabled: bool = False
        self.chk_ble_heur = QtWidgets.QCheckBox("BLE эвристика")
        self.chk_ble_heur.setChecked(self.ble_heuristics_enabled)
        self.chk_ble_heur.toggled.connect(self.on_ble_heur_toggled)
        controls.addWidget(self.chk_ble_heur)

        # Включение активного чтения Appearance/Name через GATT (подключение)
        self.gatt_app_enabled: bool = True
        self.chk_gatt_app = QtWidgets.QCheckBox("GATT Appearance/Name")
        self.chk_gatt_app.setToolTip("Активно подключаться и читать 0x1800/0x2A01. Требует рестарт подпроцесса.")
        self.chk_gatt_app.setChecked(self.gatt_app_enabled)
        self.chk_gatt_app.toggled.connect(self.on_gatt_app_toggled)
        controls.addWidget(self.chk_gatt_app)

        controls.addStretch(1)
        self.lbl_count = QtWidgets.QLabel("Устройств: 0 / всего: 0")
        self.lbl_app = QtWidgets.QLabel("Appearance: 0")
        controls.addWidget(self.lbl_count)
        controls.addWidget(self.lbl_app)
        left_layout.addLayout(controls)

        # Таблица устройств с колонками и сортировкой
        # Колонки: Имя | Адрес/ID | BT | Тип | RSSI | Дистанция (м)
        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Имя", "Адрес/ID", "BT", "Тип", "RSSI", "Дистанция (м)"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        # Сделаем так, чтобы колонка с именем растягивалась, а остальные подстраивались под содержимое
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        try:
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
            for col in (1, 2, 3, 4, 5):
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        except Exception:
            pass
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.table, 1)

        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)

        layout.addWidget(left_panel, 2)
        layout.addWidget(self.details, 3)

        # Запускаем рабочий сканер как подпроцесс и парсим его stdout (надёжно, без конфликтов лупов)
        self.proc = QtCore.QProcess(self)
        self.proc.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.on_proc_stdout)
        self.proc.errorOccurred.connect(self.on_proc_error)
        self.proc.finished.connect(self.on_proc_finished)
        self.stdout_buf = ""
        self._pending_events: deque[Dict[str, Any]] = deque()

        script_path = os.path.join(os.path.dirname(__file__), "bt_scan_mac.py")
        # Пробрасываем путь к лог-файлу, чтобы понимать, что пишет подпроцесс
        env = QtCore.QProcessEnvironment.systemEnvironment()
        env.insert("BT_LOG", os.path.join(os.path.dirname(__file__), "bt_debug.log"))
        env.insert("BT_RATE_MS", "400")
        env.insert("BT_RATE_MAX_PER_SEC", "200")
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("BT_CL_INQ_SEC", str(self.classic_cycle_seconds))
        env.insert("BT_GATT_APPEARANCE", "1" if self.gatt_app_enabled else "0")
        self.proc.setProcessEnvironment(env)
        self.proc.start(sys.executable, [script_path])

        # Таймер батч-обработки событий из подпроцесса
        self.timer_events = QtCore.QTimer(self)
        self.timer_events.setInterval(150)
        self.timer_events.timeout.connect(self.drain_events)
        self.timer_events.start()

        # Отдельный таймер для классика: каждые classic_cycle_seconds запускаем одноразовый подпроцесс,
        # чтобы быть «новым клиентом» для bluetoothd и гарантированно получить пачку found
        self.timer_classic = QtCore.QTimer(self)
        self.timer_classic.setInterval(max(5, self.classic_cycle_seconds) * 1000)
        self.timer_classic.timeout.connect(self.kick_classic_once)
        self.timer_classic.start()
        # Процесс для одноразового классик‑скана с подключённым stdout
        self.proc_classic = QtCore.QProcess(self)
        self.proc_classic.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
        self.proc_classic.readyReadStandardOutput.connect(self.on_proc_classic_stdout)
        self.stdout_buf_classic = ""

        # Watchdog тишины stdout подпроцесса: если 3 сек ничего — перезапуск
        self._last_stdout_ts = time.time()
        self.timer_watchdog = QtCore.QTimer(self)
        self.timer_watchdog.setInterval(1000)
        self.timer_watchdog.timeout.connect(self.watchdog_tick)
        self.timer_watchdog.start()

        # Опция: авто‑перезапуск подпроцесса (как ручной Стоп/Старт), чтобы «с нуля» обновлялся Classic
        self.auto_restart_enabled: bool = True
        self.chk_autorst = QtWidgets.QCheckBox("Авто рестарт")
        self.chk_autorst.setChecked(self.auto_restart_enabled)
        self.chk_autorst.toggled.connect(lambda v: setattr(self, 'auto_restart_enabled', bool(v)))
        controls.addWidget(self.chk_autorst)
        self.spin_autorst = QtWidgets.QSpinBox()
        self.spin_autorst.setRange(2, 300)
        self.spin_autorst.setValue(2)
        controls.addWidget(self.spin_autorst)
        self.timer_autorst = QtCore.QTimer(self)
        self.timer_autorst.setInterval(1000)
        self.timer_autorst.timeout.connect(self.autorst_tick)
        self.timer_autorst.start()
        # Подстроим TTL под интервал авто‑рестарта
        self.spin_autorst.valueChanged.connect(self.recalc_ttls)
        self.recalc_ttls()

        # Набор «грязных» адресов для точечных обновлений строк таблицы
        self._dirty_addrs: set[str] = set()

        # Рейт-лимит для обновлений строк (адрес -> последний апдейт ts)
        self._row_update_ts: Dict[str, float] = {}
        self._row_update_min_interval = 0.4

        # Троттлинг панели деталей
        self._details_last_addr: Optional[str] = None
        self._details_last_seen_ts: float = 0.0
        self._details_last_update_ts: float = 0.0
        self._details_min_interval: float = 0.5

        self.timer_refresh = QtCore.QTimer(self)
        self.timer_refresh.setInterval(300)
        self.timer_refresh.timeout.connect(self.refresh_list)
        self.timer_refresh.start()

        self.timer_prune = QtCore.QTimer(self)
        self.timer_prune.setInterval(1200)
        self.timer_prune.timeout.connect(self.prune_stale)
        self.timer_prune.start()

    # Приходят payload'ы 1-в-1 как в bt_scan_mac.py
    @QtCore.pyqtSlot(dict)
    def on_apple_event(self, payload: Dict[str, Any]) -> None:
        bt_type = payload.get("type")
        now = payload.get("ts", time.time())
        # Ключ устройства
        if bt_type == "BLE":
            addr_key = payload.get("identifier") or "unknown"
            name = payload.get("name")
            rssi = payload.get("rssi")
            txp = None
            ad = payload.get("advertisement") or {}
            txp = ad.get("tx_power")
            service_uuids = ad.get("service_uuids") or []
            mfr_hex = {}
            if ad.get("manufacturer_data_hex"):
                # это строка; оставим пустым словарь для унификации
                mfr_hex = {0: ad.get("manufacturer_data_hex")}
            svc_hex = ad.get("service_data_hex") or {}
            appearance = ad.get("appearance")
            rec = DeviceRecord(
                address=str(addr_key),
                name=name,
                rssi=rssi,
                tx_power=txp,
                bt_type="BLE",
                manufacturer_data_hex=mfr_hex,
                service_uuids=service_uuids,
                service_data_hex=svc_hex,
                last_seen_ts=now,
                raw_advertisement=payload,
                class_of_device=None,
                appearance=appearance,
            )
        else:
            addr_key = payload.get("address") or "unknown"
            name = payload.get("name")
            rssi = payload.get("rssi")
            cod_val = payload.get("class_of_device")
            rec = DeviceRecord(
                address=str(addr_key),
                name=name,
                rssi=rssi,
                tx_power=None,
                bt_type="Classic",
                manufacturer_data_hex={},
                service_uuids=[],
                service_data_hex={},
                last_seen_ts=now,
                raw_advertisement=payload,
                class_of_device=cod_val,
            )
        with self.devices_lock:
            cur = self.devices.get(rec.address)
            if cur:
                if rec.name:
                    cur.name = rec.name
                cur.rssi = rec.rssi
                cur.tx_power = rec.tx_power if rec.tx_power is not None else cur.tx_power
                cur.manufacturer_data_hex = rec.manufacturer_data_hex or cur.manufacturer_data_hex
                cur.service_uuids = rec.service_uuids or cur.service_uuids
                cur.service_data_hex = rec.service_data_hex or cur.service_data_hex
                cur.last_seen_ts = rec.last_seen_ts
                cur.raw_advertisement = rec.raw_advertisement or cur.raw_advertisement
            else:
                self.devices[rec.address] = rec
                # учтём в total, если впервые видим
                if rec.address not in self.seen_all:
                    self.seen_all.add(rec.address)
                    self.total_seen += 1
        # пометим адрес как изменённый — обновим строку точечно в drain_events
        try:
            self._dirty_addrs.add(rec.address)
        except Exception:
            pass

    def closeEvent(self, event) -> None:  # noqa: N802 (имя Qt-метода)
        try:
            if self.proc and self.proc.state() != QtCore.QProcess.ProcessState.NotRunning:
                self.proc.terminate()
                self.proc.waitForFinished(1500)
        except Exception:
            pass
        super().closeEvent(event)

    def on_toggle_scan(self) -> None:
        if self.btn_toggle.text() == "Стоп":
            try:
                if self.proc and self.proc.state() != QtCore.QProcess.ProcessState.NotRunning:
                    self.proc.terminate()
                    self.proc.waitForFinished(1500)
            except Exception:
                pass
            self.btn_toggle.setText("Старт")
        else:
            try:
                script_path = os.path.join(os.path.dirname(__file__), "bt_scan_mac.py")
                env = QtCore.QProcessEnvironment.systemEnvironment()
                env.insert("BT_LOG", os.path.join(os.path.dirname(__file__), "bt_debug.log"))
                env.insert("BT_RATE_MS", "400")
                env.insert("BT_RATE_MAX_PER_SEC", "200")
                env.insert("PYTHONUNBUFFERED", "1")
                env.insert("BT_CL_INQ_SEC", str(self.classic_cycle_seconds))
                env.insert("BT_GATT_APPEARANCE", "1" if self.gatt_app_enabled else "0")
                self.proc.setProcessEnvironment(env)
                self.proc.start(sys.executable, [script_path])
            except Exception:
                pass
            self.btn_toggle.setText("Стоп")

    @QtCore.pyqtSlot()
    def on_proc_stdout(self) -> None:
        try:
            data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        except Exception:
            return
        self.stdout_buf += data
        self._last_stdout_ts = time.time()
        if len(self.stdout_buf) > 1_000_000:
            self.stdout_buf = self.stdout_buf[-500_000:]
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
                    json_part = text[len("[FOUND] "):]
                    payload = json.loads(json_part)
                    self._pending_events.append(payload)
                except Exception:
                    pass
            elif text.startswith("[HEARTBEAT] "):
                # Просто обновим таймер живости
                self._last_stdout_ts = time.time()
        self.stdout_buf = keep_tail

    @QtCore.pyqtSlot()
    def on_proc_classic_stdout(self) -> None:
        # Парсим вывод одноразового классик‑процесса и кладём события в общую очередь
        try:
            data = bytes(self.proc_classic.readAllStandardOutput()).decode("utf-8", errors="replace")
        except Exception:
            return
        self.stdout_buf_classic += data
        if len(self.stdout_buf_classic) > 500_000:
            self.stdout_buf_classic = self.stdout_buf_classic[-250_000:]
        lines = self.stdout_buf_classic.splitlines(keepends=True)
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
                    self._pending_events.append(payload)
                except Exception:
                    pass
        self.stdout_buf_classic = keep_tail

    def on_proc_error(self, err) -> None:
        try:
            self.lbl_count.setText(f"Подпроцесс ошибка: {err}")
        except Exception:
            pass

    @QtCore.pyqtSlot(int, QtCore.QProcess.ExitStatus)
    def on_proc_finished(self, code: int, status: QtCore.QProcess.ExitStatus) -> None:
        try:
            self.lbl_count.setText(f"Подпроцесс завершился: code={code} status={int(status)}")
        except Exception:
            pass

    @QtCore.pyqtSlot()
    def drain_events(self) -> None:
        max_per_tick = 120
        processed = 0
        while self._pending_events and processed < max_per_tick:
            payload = self._pending_events.popleft()
            self.on_apple_event(payload)
            processed += 1
        # Точечно обновим «грязные» строки
        self._update_dirty_rows(max_rows_per_tick=80)

    @QtCore.pyqtSlot()
    def watchdog_tick(self) -> None:
        now = time.time()
        if now - getattr(self, "_last_stdout_ts", 0) > 3.0:
            # Перезапуск подпроцесса
            try:
                if self.proc and self.proc.state() != QtCore.QProcess.ProcessState.NotRunning:
                    self.proc.kill()
                    self.proc.waitForFinished(1500)
            except Exception:
                pass
            # Старт заново
            try:
                script_path = os.path.join(os.path.dirname(__file__), "bt_scan_mac.py")
                env = QtCore.QProcessEnvironment.systemEnvironment()
                env.insert("BT_LOG", os.path.join(os.path.dirname(__file__), "bt_debug.log"))
                env.insert("BT_RATE_MS", "400")
                env.insert("BT_RATE_MAX_PER_SEC", "200")
                env.insert("PYTHONUNBUFFERED", "1")
                env.insert("BT_GATT_APPEARANCE", "1" if self.gatt_app_enabled else "0")
                self.proc.setProcessEnvironment(env)
                self.proc.start(sys.executable, [script_path])
                self._last_stdout_ts = time.time()
                self.lbl_count.setText("Перезапуск подпроцесса (watchdog)")
            except Exception:
                pass

    def autorst_tick(self) -> None:
        # Если включен авто‑рестарт, перезапускаем подпроцесс каждые N секунд — как ручной Стоп/Старт
        if not self.auto_restart_enabled:
            return
        try:
            if not hasattr(self, "_autorst_last"):
                self._autorst_last = time.time()
            if time.time() - self._autorst_last >= int(self.spin_autorst.value()):
                self._autorst_last = time.time()
                # Restart
                try:
                    if self.proc and self.proc.state() != QtCore.QProcess.ProcessState.NotRunning:
                        self.proc.kill()
                        self.proc.waitForFinished(1500)
                except Exception:
                    pass
                try:
                    script_path = os.path.join(os.path.dirname(__file__), "bt_scan_mac.py")
                    env = QtCore.QProcessEnvironment.systemEnvironment()
                    env.insert("BT_LOG", os.path.join(os.path.dirname(__file__), "bt_debug.log"))
                    env.insert("BT_RATE_MS", "400")
                    env.insert("BT_RATE_MAX_PER_SEC", "200")
                    env.insert("PYTHONUNBUFFERED", "1")
                    self.proc.setProcessEnvironment(env)
                    self.proc.start(sys.executable, [script_path])
                    self._last_stdout_ts = time.time()
                except Exception:
                    pass
        except Exception:
            pass

    def on_n_changed(self, val: float) -> None:
        self.path_loss_n = float(val)

    def on_tx_changed(self, val: int) -> None:
        self.tx_power_fallback = int(val)

    def on_ttl_changed(self, val: int) -> None:
        # Этот контрол управляет только BLE TTL, для Classic свой более длинный TTL
        self.prune_ble_seconds = int(val)

    def recalc_ttls(self) -> None:
        try:
            interval = max(2, int(self.spin_autorst.value()))
            ttl = max(6, interval * 4)
            self.prune_ble_seconds = ttl
            self.prune_classic_seconds = ttl
            # Обновим контролы без лишнего шума
            self.spin_ttl.blockSignals(True)
            self.spin_ttl.setValue(self.prune_ble_seconds)
            self.spin_ttl.blockSignals(False)
            self.spin_ttl_cl.blockSignals(True)
            self.spin_ttl_cl.setValue(self.prune_classic_seconds)
            self.spin_ttl_cl.blockSignals(False)
        except Exception:
            pass

    def kick_classic_once(self) -> None:
        try:
            # Если предыдущий цикл ещё жив — аккуратно грохнем
            try:
                if self.proc_classic.state() != QtCore.QProcess.ProcessState.NotRunning:
                    self.proc_classic.kill()
                    self.proc_classic.waitForFinished(500)
            except Exception:
                pass
            env = QtCore.QProcessEnvironment.systemEnvironment()
            env.insert("BT_LOG", os.path.join(os.path.dirname(__file__), "bt_debug.log"))
            env.insert("BT_CL_INQ_SEC", str(self.classic_cycle_seconds))
            env.insert("PYTHONUNBUFFERED", "1")
            env.insert("BT_DISABLE_CLASSIC", "1")  # основной подпроцесс игнорит классик
            self.proc_classic.setProcessEnvironment(env)
            script = os.path.join(os.path.dirname(__file__), "bt_classic_scan.py")
            self.proc_classic.start(sys.executable, [script])
        except Exception:
            pass

    def on_ble_heur_toggled(self, checked: bool) -> None:
        # Включает/выключает эвристику для BLE (вендор/сервисы). Когда выкл — используем только Appearance
        self.ble_heuristics_enabled = bool(checked)

    def on_gatt_app_toggled(self, checked: bool) -> None:
        # Включает/выключает активное чтение Appearance через GATT. Требуется перезапуск подпроцесса
        self.gatt_app_enabled = bool(checked)
        # Мягко перезапустим подпроцесс, если он бежит
        try:
            if self.proc and self.proc.state() != QtCore.QProcess.ProcessState.NotRunning:
                self.proc.kill()
                self.proc.waitForFinished(1500)
        except Exception:
            pass
        # Старт заново с новым env
        try:
            script_path = os.path.join(os.path.dirname(__file__), "bt_scan_mac.py")
            env = QtCore.QProcessEnvironment.systemEnvironment()
            env.insert("BT_LOG", os.path.join(os.path.dirname(__file__), "bt_debug.log"))
            env.insert("BT_RATE_MS", "400")
            env.insert("BT_RATE_MAX_PER_SEC", "200")
            env.insert("PYTHONUNBUFFERED", "1")
            env.insert("BT_CL_INQ_SEC", str(self.classic_cycle_seconds))
            env.insert("BT_GATT_APPEARANCE", "1" if self.gatt_app_enabled else "0")
            self.proc.setProcessEnvironment(env)
            self.proc.start(sys.executable, [script_path])
            self._last_stdout_ts = time.time()
        except Exception:
            pass

    def estimate_distance(self, rssi: Optional[int], tx_power: Optional[int]) -> Optional[float]:
        # d = 10^((TxPower - RSSI)/(10*n)) — грубо, шумно, но ок для прикидки
        try:
            if rssi is None:
                return None
            tp = tx_power if tx_power is not None else self.tx_power_fallback
            n = self.path_loss_n
            d = 10 ** ((tp - int(rssi)) / (10.0 * n))
            return max(0.1, min(d, 100.0))
        except Exception:
            return None

    def prune_stale(self) -> None:
        now = time.time()
        with self.devices_lock:
            stale = []
            for addr, rec in self.devices.items():
                ttl = self.prune_classic_seconds if rec.bt_type == "Classic" else self.prune_ble_seconds
                if now - rec.last_seen_ts > ttl:
                    stale.append(addr)
            for addr in stale:
                self.devices.pop(addr, None)
                row = self._find_row_by_addr(addr)
                if row is not None:
                    self.table.removeRow(row)

    def refresh_list(self) -> None:
        # Лёгкая операция: только счётчик и детали
        try:
            current_count = self.table.rowCount()
            self.lbl_count.setText(f"Устройств: {current_count} / всего: {self.total_seen}")
            # посчитаем сколько устройств с Appearance видим сейчас
            with self.devices_lock:
                now = time.time()
                appear_cnt = 0
                for r in self.devices.values():
                    ttl = self.prune_classic_seconds if r.bt_type == "Classic" else self.prune_ble_seconds
                    if r.appearance is not None and (now - r.last_seen_ts) <= ttl:
                        appear_cnt += 1
            self.lbl_app.setText(f"Appearance: {appear_cnt}")
        except Exception:
            pass
        self.update_details()

    def _update_dirty_rows(self, max_rows_per_tick: int = 200) -> None:
        if not self._dirty_addrs or max_rows_per_tick <= 0:
            return
        current_addr = self._current_selected_addr()
        sorting = self.table.isSortingEnabled()
        if sorting:
            self.table.setSortingEnabled(False)

        dirty = []
        # Возьмём ограниченное число адресов
        while self._dirty_addrs and len(dirty) < max_rows_per_tick:
            dirty.append(self._dirty_addrs.pop())
        # Остальные адреса останутся на следующий тик

        now_ts = time.time()
        for addr in dirty:
            with self.devices_lock:
                rec = self.devices.get(addr)
            if not rec:
                row_del = self._find_row_by_addr(addr)
                if row_del is not None:
                    self.table.removeRow(row_del)
                continue
            name = rec.name or "Без имени"
            # Единая категория
            category = _unified_category(rec, self.ble_heuristics_enabled)
            rssi_val = rec.rssi if rec.rssi is not None else -9999
            dist = self.estimate_distance(rec.rssi, rec.tx_power)
            dist_val = float(dist) if dist is not None else 1e12

            row = self._find_row_by_addr(addr)
            if row is None:
                row = self.table.rowCount()
                self.table.insertRow(row)
                item_name = QtWidgets.QTableWidgetItem(name)
                self.table.setItem(row, 0, item_name)
                item_addr = QtWidgets.QTableWidgetItem(addr)
                item_addr.setData(QtCore.Qt.ItemDataRole.UserRole, addr)
                self.table.setItem(row, 1, item_addr)
                item_bt = QtWidgets.QTableWidgetItem(rec.bt_type or "?")
                self.table.setItem(row, 2, item_bt)
                item_type = QtWidgets.QTableWidgetItem(category)
                self.table.setItem(row, 3, item_type)
                item_rssi = QtWidgets.QTableWidgetItem()
                item_rssi.setData(QtCore.Qt.ItemDataRole.DisplayRole, int(rssi_val))
                item_rssi.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 4, item_rssi)
                item_dist = QtWidgets.QTableWidgetItem()
                item_dist.setData(QtCore.Qt.ItemDataRole.DisplayRole, float(f"{dist_val:.2f}"))
                item_dist.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, 5, item_dist)
                self._row_update_ts[addr] = now_ts
            else:
                last_ts = self._row_update_ts.get(addr, 0)
                if now_ts - last_ts >= self._row_update_min_interval:
                    self.table.item(row, 0).setText(name)
                    self.table.item(row, 1).setText(addr)
                    # BT тип
                    bt_text = rec.bt_type or "?"
                    if self.table.item(row, 2) is None:
                        self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(bt_text))
                    else:
                        self.table.item(row, 2).setText(bt_text)
                    # Категория
                    self.table.item(row, 3).setText(category)
                    self.table.item(row, 4).setData(QtCore.Qt.ItemDataRole.DisplayRole, int(rssi_val))
                    self.table.item(row, 5).setData(QtCore.Qt.ItemDataRole.DisplayRole, float(f"{dist_val:.2f}"))
                    self._row_update_ts[addr] = now_ts

        if sorting:
            self.table.setSortingEnabled(True)
        if current_addr is not None:
            sel_row = self._find_row_by_addr(current_addr)
            if sel_row is not None:
                self.table.selectRow(sel_row)
        # обновим счётчик и детали легко
        self.refresh_list()

    def on_selection_changed(self) -> None:
        self.update_details()

    def update_details(self) -> None:
        row = self._current_selected_row()
        if row is None:
            self.details.setPlainText("Выбери устройство слева")
            self._details_last_addr = None
            return
        addr_item = self.table.item(row, 1)
        addr = addr_item.data(QtCore.Qt.ItemDataRole.UserRole) if addr_item else None
        rec: Optional[DeviceRecord]
        with self.devices_lock:
            rec = self.devices.get(addr)
        if not rec:
            self.details.setPlainText("Устройство пропало из списка")
            return

        # Троттлинг: не чаще, чем раз в _details_min_interval для того же устройства,
        # и если last_seen_ts не поменялся
        now_ts = time.time()
        if (
            self._details_last_addr == rec.address
            and self._details_last_seen_ts == rec.last_seen_ts
            and (now_ts - self._details_last_update_ts) < self._details_min_interval
        ):
            return

        # Добавим вычисленные поля для удобства анализа
        mfr_hex = None
        vendor = None
        cid = None
        if rec.bt_type == "BLE":
            mfr_hex = rec.manufacturer_data_hex.get(0)
            cid, vendor = _company_from_mfr_hex(mfr_hex)
        decoded_cod = _decode_class_of_device(rec.class_of_device) if rec.bt_type == "Classic" else None
        category = _unified_category(rec, self.ble_heuristics_enabled)

        details = {
            "address": rec.address,
            "name": rec.name,
            "rssi": rec.rssi,
            "tx_power": rec.tx_power,
            "estimated_distance_m": self.estimate_distance(rec.rssi, rec.tx_power),
            "service_uuids": rec.service_uuids,
            "manufacturer_data_hex": rec.manufacturer_data_hex,
            "service_data_hex": rec.service_data_hex,
            "last_seen_ts": rec.last_seen_ts,
            "raw_advertisement": rec.raw_advertisement,
            "class_of_device": rec.class_of_device,
            "decoded_class": decoded_cod,
            "company_id": cid,
            "vendor": vendor,
            "category": category,
        }
        text = json.dumps(details, ensure_ascii=False, indent=2)
        self.details.setPlainText(text)
        self._details_last_addr = rec.address
        self._details_last_seen_ts = rec.last_seen_ts
        self._details_last_update_ts = now_ts

    def _find_row_by_addr(self, addr: str) -> Optional[int]:
        rc = self.table.rowCount()
        for row in range(rc):
            item = self.table.item(row, 1)
            if not item:
                continue
            if item.data(QtCore.Qt.ItemDataRole.UserRole) == addr:
                return row
        return None

    def _current_selected_row(self) -> Optional[int]:
        sel = self.table.selectionModel()
        if not sel:
            return None
        rows = sel.selectedRows()
        if not rows:
            return None
        return rows[0].row()

    def _current_selected_addr(self) -> Optional[str]:
        row = self._current_selected_row()
        if row is None:
            return None
        item = self.table.item(row, 1)
        if not item:
            return None
        return item.data(QtCore.Qt.ItemDataRole.UserRole)


def main() -> None:
    app = QtWidgets.QApplication([])
    win = MainWindow()
    win.show()
    app.exec()


if __name__ == "__main__":
    main()


