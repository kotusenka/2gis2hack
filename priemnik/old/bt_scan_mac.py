#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Реалтайм-сканер Bluetooth для macOS (BLE + Classic) на PyObjC
# Все комментарии на русском, как просили

import sys
import os
import json
import time
import logging
import traceback
from typing import Any, Dict, Optional
import threading
import asyncio

# Глобальные настройки троттлинга вывода для GUI-пайпа
_PER_DEVICE_RATE_MS = int(os.environ.get("BT_RATE_MS", "400"))  # мс между выводами по одному устройству
_GLOBAL_RATE_MAX_PER_SEC = int(os.environ.get("BT_RATE_MAX_PER_SEC", "200"))  # общий лимит строк/сек
_last_emit_ts: Dict[str, float] = {}
_global_counter = {"sec": 0.0, "count": 0}
_GATT_APPEARANCE = os.environ.get("BT_GATT_APPEARANCE", "0") == "1"
_CLASSIC_INQ_LEN_SEC = int(os.environ.get("BT_CL_INQ_SEC", "15"))
_DISABLE_CLASSIC = os.environ.get("BT_DISABLE_CLASSIC", "0") == "1"


def _should_emit_for_key(key: str) -> bool:
    """Решаем, можно ли сейчас печатать событие для конкретного устройства и в целом."""
    now = time.time()
    # Глобальный лимит в секунду
    sec = int(now)
    if _global_counter["sec"] != sec:
        _global_counter["sec"] = sec
        _global_counter["count"] = 0
    if _global_counter["count"] >= _GLOBAL_RATE_MAX_PER_SEC:
        return False

    # Пер-устройственный лимит
    last = _last_emit_ts.get(key, 0.0)
    if (now - last) * 1000.0 < _PER_DEVICE_RATE_MS:
        return False

    _last_emit_ts[key] = now
    _global_counter["count"] += 1
    return True

import objc
from Foundation import NSObject, NSRunLoop

# CoreBluetooth (BLE)
try:
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
    # Appearance ключ может отсутствовать в старых версиях фреймворка — обработаем мягко
    try:
        from CoreBluetooth import CBAdvertisementDataAppearanceKey  # type: ignore
    except Exception:
        CBAdvertisementDataAppearanceKey = None  # type: ignore
except Exception as e:
    print("[!] Не удалось импортировать CoreBluetooth: ", e)
    print("    Убедись, что установлены pyobjc-core и pyobjc-framework-CoreBluetooth")
    raise

# IOBluetooth (Classic)
try:
    from IOBluetooth import IOBluetoothDeviceInquiry
except Exception as e:
    print("[!] Не удалось импортировать IOBluetooth: ", e)
    print("    Убедись, что установлен pyobjc-framework-IOBluetooth")
    raise


def _nsdata_to_hex(value: Any) -> Optional[str]:
    """Перевод NSData/bytes в hex-строку."""
    try:
        if value is None:
            return None
        if hasattr(value, "bytes") and hasattr(value, "length"):
            # NSData
            return bytes(value).hex()
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).hex()
    except Exception:
        return None
    return None


def _cbuuid_to_str(u: Any) -> Optional[str]:
    """Строковое представление CBUUID."""
    try:
        # В PyObjC у CBUUID есть метод UUIDString()
        if hasattr(u, "UUIDString"):
            return str(u.UUIDString())
        return str(u)
    except Exception:
        return None


def serialize_ble_advertisement(ad_data: Dict[Any, Any]) -> Dict[str, Any]:
    """Человеческое представление всех полей advertisementData."""
    out: Dict[str, Any] = {}

    try:
        if CBAdvertisementDataLocalNameKey in ad_data:
            out["local_name"] = ad_data.get(CBAdvertisementDataLocalNameKey)

        if CBAdvertisementDataIsConnectable in ad_data:
            out["is_connectable"] = bool(ad_data.get(CBAdvertisementDataIsConnectable))

        if CBAdvertisementDataTxPowerLevelKey in ad_data:
            out["tx_power"] = ad_data.get(CBAdvertisementDataTxPowerLevelKey)

        if CBAdvertisementDataManufacturerDataKey in ad_data:
            out["manufacturer_data_hex"] = _nsdata_to_hex(
                ad_data.get(CBAdvertisementDataManufacturerDataKey)
            )

        if CBAdvertisementDataServiceUUIDsKey in ad_data:
            uuids = ad_data.get(CBAdvertisementDataServiceUUIDsKey) or []
            out["service_uuids"] = [
                u for u in (_cbuuid_to_str(x) for x in uuids) if u is not None
            ]

        if CBAdvertisementDataOverflowServiceUUIDsKey in ad_data:
            uuids = ad_data.get(CBAdvertisementDataOverflowServiceUUIDsKey) or []
            out["overflow_service_uuids"] = [
                u for u in (_cbuuid_to_str(x) for x in uuids) if u is not None
            ]

        if CBAdvertisementDataSolicitedServiceUUIDsKey in ad_data:
            uuids = ad_data.get(CBAdvertisementDataSolicitedServiceUUIDsKey) or []
            out["solicited_service_uuids"] = [
                u for u in (_cbuuid_to_str(x) for x in uuids) if u is not None
            ]

        if CBAdvertisementDataServiceDataKey in ad_data:
            # Сервисные данные: { CBUUID: NSData }
            svc_data = ad_data.get(CBAdvertisementDataServiceDataKey) or {}
            nice = {}
            try:
                for k, v in svc_data.items():
                    key_str = _cbuuid_to_str(k) or str(k)
                    nice[key_str] = _nsdata_to_hex(v)
            except Exception:
                pass
            out["service_data_hex"] = nice
        # Попробуем вытащить Appearance, если CoreBluetooth его отдаёт
        try:
            from CoreBluetooth import CBAdvertisementDataAppearanceKey  # type: ignore
            if CBAdvertisementDataAppearanceKey in ad_data:
                out["appearance"] = int(ad_data.get(CBAdvertisementDataAppearanceKey))
        except Exception:
            pass
    except Exception:
        # Пофиг, продолжаем с тем, что есть
        pass

    return out


def jprint(prefix: str, payload: Dict[str, Any]) -> None:
    """Красивый JSON-лог одной строкой."""
    try:
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        line = f"{prefix} {serialized}"
        print(line)
        logging.getLogger("bt").debug(line)
    except Exception as e:
        print(prefix, payload)
        logging.getLogger("bt").exception("Ошибка jprint: %s", e)


class _GattAppearanceReader:
    """Фоновый asyncio-воркер на bleak для чтения Appearance по GATT.
    Сделан отдельным классом, чтобы не лезть в CoreBluetooth из посторонних потоков.
    """

    def __init__(self, concurrency: int = 3, timeout: float = 5.0):
        self.concurrency = concurrency
        self.timeout = timeout
        self._queue: "asyncio.Queue[str]" = asyncio.Queue()
        self._seen: set[str] = set()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        def runner():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run())
        self._thread = threading.Thread(target=runner, name="gatt_appearance", daemon=True)
        self._thread.start()

    def submit(self, identifier: Optional[str]) -> None:
        try:
            if not identifier or identifier in self._seen:
                return
            self._seen.add(identifier)
            if self._loop is not None:
                asyncio.run_coroutine_threadsafe(self._queue.put(identifier), self._loop)
        except Exception:
            pass

    async def _run(self) -> None:
        try:
            import bleak  # noqa: F401
            from bleak import BleakClient
        except Exception:
            # bleak не установлен — тихо выходим
            return
        sem = asyncio.Semaphore(self.concurrency)

        async def worker() -> None:
            while True:
                identifier = await self._queue.get()
                try:
                    async with sem:
                        try:
                            client = BleakClient(identifier, timeout=self.timeout)
                            try:
                                await client.__aenter__()
                            except Exception:
                                continue
                            try:
                                # Попробуем прочитать имя устройства (Device Name, 0x2A00)
                                # Это полезно, когда имя не приходит в рекламе
                                data_name = await client.read_gatt_char("00002a00-0000-1000-8000-00805f9b34fb")
                                if data_name is not None:
                                    try:
                                        name_str = bytes(data_name).decode("utf-8", errors="replace").strip()
                                    except Exception:
                                        name_str = None
                                    if name_str:
                                        jprint("[FOUND]", {
                                            "type": "BLE",
                                            "ts": time.time(),
                                            "name": name_str,
                                            "name_source": "gatt",
                                            "identifier": identifier,
                                            "rssi": None,
                                            "advertisement": {},
                                        })
                            except Exception:
                                pass
                            try:
                                data = await client.read_gatt_char("00002a01-0000-1000-8000-00805f9b34fb")
                                if data is not None:
                                    app = int.from_bytes(bytes(data), byteorder="little")
                                    jprint("[FOUND]", {
                                        "type": "BLE",
                                        "ts": time.time(),
                                        "name": None,
                                        "identifier": identifier,
                                        "rssi": None,
                                        "advertisement": {"appearance": app},
                                    })
                            except Exception:
                                pass
                            try:
                                await client.__aexit__(None, None, None)
                            except Exception:
                                pass
                        except Exception:
                            pass
                finally:
                    self._queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(self.concurrency)]
        await asyncio.gather(*workers)

class BLEScanner(NSObject):
    """Делегат для BLE (CoreBluetooth)."""

    def init(self):
        self = objc.super(BLEScanner, self).init()
        if self is None:
            return None
        self.manager = CBCentralManager.alloc().initWithDelegate_queue_(self, None)
        self.pending_reads = {}
        self.reading_limit = 3
        # Фоновый воркер bleak для Appearance
        self.bleak_reader = _GattAppearanceReader(concurrency=3, timeout=5.0)
        if _GATT_APPEARANCE:
            self.bleak_reader.start()
        return self

    def centralManagerDidUpdateState_(self, central):
        # 5 == poweredOn. Константа CBCentralManagerStatePoweredOn депрекейтнута, но значение то же
        try:
            state = central.state()
        except Exception:
            state = getattr(central, "state", lambda: None)()

        if state == 5:
            print("[BLE] Bluetooth включен — начинаю сканировать (allow duplicates)")
            logging.getLogger("bt").info("BLE poweredOn → scan start (allow duplicates)")
            try:
                self.manager.scanForPeripheralsWithServices_options_(
                    None,
                    {CBCentralManagerScanOptionAllowDuplicatesKey: True},
                )
            except Exception:
                # Fallback: без опций
                self.manager.scanForPeripheralsWithServices_options_(None, None)
        else:
            print("[BLE] Bluetooth выключен/недоступен (state=", state, ")")
            logging.getLogger("bt").warning("BLE not available, state=%s", state)

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

            ad = serialize_ble_advertisement(advertisementData or {})
            # Фолбэк: если имени у peripheral нет — возьмём из рекламы (local_name)
            name_source = None
            if name:
                name_source = "peripheral"
            else:
                alt = ad.get("local_name")
                if alt:
                    name = alt
                    name_source = "ad_local"

            payload = {
                "type": "BLE",
                "ts": time.time(),
                "name": name,
                "name_source": name_source,
                "identifier": per_id,
                "rssi": int(RSSI) if RSSI is not None else None,
                "advertisement": ad,
            }
            # Активное чтение GATT (имя/Appearance), если включено. Считаем, что если поле is_connectable
            # отсутствует — устройство может быть коннектируемым, поэтому не блокируем.
            is_conn = ad.get("is_connectable")
            if _GATT_APPEARANCE and (is_conn is not False) and (ad.get("appearance") is None or not name):
                # Через bleak: безопаснее и проще
                try:
                    if per_id:
                        self.bleak_reader.submit(per_id)
                except Exception:
                    pass
            # Троттлинг вывода, чтобы не забивать stdout и не клинить GUI-пайп
            key = per_id or "unknown"
            if _should_emit_for_key(f"BLE:{key}"):
                jprint("[FOUND]", payload)
        except Exception:
            logging.getLogger("bt").exception("Ошибка обработки BLE discover")
            traceback.print_exc()

    def _read_gatt_appearance_async(self, peripheral: CBPeripheral, per_id: str):
        pass


class ClassicScanner(NSObject):
    """Делегат для классического Bluetooth (IOBluetooth)."""

    def init(self):
        self = objc.super(ClassicScanner, self).init()
        if self is None:
            return None
        self.inquiry = None
        self._create_new_inquiry()
        return self

    def start(self):
        try:
            ret = self.inquiry.start()
            if ret != 0:
                print(f"[Classic] start() вернул код {ret}")
                logging.getLogger("bt").warning("Classic start() code=%s", ret)
        except Exception as e:
            print("[Classic] Не удалось запустить inquiry:", e)
            logging.getLogger("bt").exception("Classic inquiry start failed")

    def _create_new_inquiry(self):
        try:
            self.inquiry = IOBluetoothDeviceInquiry.inquiryWithDelegate_(self)
            self.inquiry.setUpdateNewDeviceNames_(True)
            self.inquiry.setInquiryLength_(_CLASSIC_INQ_LEN_SEC)
        except Exception:
            pass

    # Делегат: поиск начался
    def deviceInquiryStarted_(self, sender):
        print("[Classic] Сканирование началось")

    # Делегат: устройство найдено
    def deviceInquiryDeviceFound_device_(self, sender, device):
        try:
            # Максимум инфы, что можем быстро достать без коннекта
            payload: Dict[str, Any] = {
                "type": "Classic",
                "ts": time.time(),
            }
            # Имя
            try:
                payload["name"] = device.name()
            except Exception:
                pass
            # Адрес (MAC)
            try:
                payload["address"] = device.addressString()
            except Exception:
                pass
            # Состояния
            for attr in ("isPaired", "isConnected", "isFavorite"):
                try:
                    payload[attr] = bool(getattr(device, attr)())
                except Exception:
                    pass
            # Класс устройства (битовая маска)
            try:
                cod = device.classOfDevice()
                payload["class_of_device"] = int(cod) if cod is not None else None
            except Exception:
                pass
            # RSSI если доступен
            for rssi_attr in ("RSSI", "rawRSSI"):
                try:
                    rssi_val = getattr(device, rssi_attr)()
                    if rssi_val is not None:
                        payload["rssi"] = int(rssi_val)
                        break
                except Exception:
                    pass

            key = payload.get("address") or "unknown"
            if _should_emit_for_key(f"CL:{key}"):
                jprint("[FOUND]", payload)
        except Exception:
            traceback.print_exc()

    # Делегат: завершение цикла
    def deviceInquiryComplete_error_aborted_(self, sender, error, aborted):
        try:
            print(f"[Classic] Завершено. error={error} aborted={bool(aborted)} → новый цикл через 0.3с")
            # Создаём НОВЫЙ объект inquiry перед каждым циклом — скан «с нуля»
            def _restart():
                try:
                    time.sleep(0.3)
                    self._create_new_inquiry()
                    self.start()
                except Exception:
                    pass
            threading.Thread(target=_restart, name="classic-restart", daemon=True).start()
        except Exception:
            traceback.print_exc()

    # Необязательный делегат: обновилось имя
    def deviceInquiryDeviceNameUpdated_device_devicesRemaining_(self, sender, device, devicesRemaining):
        try:
            jprint("[Classic] name_update", {
                "name": getattr(device, "name", lambda: None)(),
                "address": getattr(device, "addressString", lambda: None)(),
                "devices_remaining": int(devicesRemaining) if devicesRemaining is not None else None,
            })
        except Exception:
            pass


def main():
    # Логирование в файл рядом со скриптом
    try:
        log_path = os.environ.get("BT_LOG", os.path.join(os.path.dirname(__file__), "bt_debug.log"))
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(process)d %(threadName)s %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(log_path, encoding="utf-8"),
            ],
        )
        logging.getLogger("bt").info("=== START bt_scan_mac.py pid=%s ===", os.getpid())
    except Exception:
        pass

    print("\n=== Bluetooth сканер для macOS (BLE + Classic) ===")
    print("- Запускаю параллельно CoreBluetooth (BLE) и IOBluetooth (Classic)")
    print("- Первый запуск может запросить разрешение на Bluetooth для твоего терминала")
    print("- Жми Ctrl+C для выхода\n")

    ble = BLEScanner.alloc().init()
    classic = None
    if not _DISABLE_CLASSIC:
        classic = ClassicScanner.alloc().init()
        classic.start()

    # Heartbeat в отдельном потоке, чтобы видеть «жив ли процесс» даже без событий
    def _heartbeat():
        while True:
            try:
                logging.getLogger("bt").debug("heartbeat alive pid=%s", os.getpid())
                # Пишем в stdout, чтобы GUI видел активность и не считал нас зависшими
                print(f"[HEARTBEAT] {time.time():.3f}")
                try:
                    sys.stdout.flush()
                except Exception:
                    pass
            except Exception:
                pass
            time.sleep(2.0)

    try:
        threading.Thread(target=_heartbeat, name="heartbeat", daemon=True).start()
    except Exception:
        pass

    try:
        logging.getLogger("bt").info("NSRunLoop start")
        NSRunLoop.currentRunLoop().run()
    except KeyboardInterrupt:
        print("\n[+] Выходим по Ctrl+C — пока!")
        logging.getLogger("bt").info("KeyboardInterrupt, exiting")
    except Exception:
        logging.getLogger("bt").exception("Критическая ошибка в main()")
        traceback.print_exc()


if __name__ == "__main__":
    main()


