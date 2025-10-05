#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Одноразовый цикл классического сканирования (IOBluetoothDeviceInquiry).
Запускается отдельным процессом, живёт ~BT_CL_INQ_SEC секунд, печатает [FOUND] события и завершает работу.
"""

import os, sys, time, json, traceback
import objc
from Foundation import NSObject, NSRunLoop
from IOBluetooth import IOBluetoothDeviceInquiry
import logging

def setup_log():
    try:
        log_path = os.environ.get("BT_LOG")
        if log_path:
            logging.basicConfig(filename=log_path, level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
    except Exception:
        pass


CL_SEC = int(os.environ.get("BT_CL_INQ_SEC", "15"))


def jprint(payload):
    try:
        print("[FOUND] " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        print("[FOUND]", payload)


class ClassicOnce(NSObject):
    def init(self):
        self = objc.super(ClassicOnce, self).init()
        if self is None:
            return None
        self.inq = IOBluetoothDeviceInquiry.inquiryWithDelegate_(self)
        try:
            self.inq.setUpdateNewDeviceNames_(True)
            self.inq.setInquiryLength_(CL_SEC)
        except Exception:
            pass
        return self

    def start(self):
        try:
            self.inq.start()
        except Exception:
            pass

    # Полностью повторяем сигнатуры из рабочего сканера, чтобы не ловить PyObjC TypeError
    def deviceInquiryDeviceFound_device_(self, sender, device):
        try:
            payload = {"type": "Classic", "ts": time.time()}
            try:
                payload["name"] = device.name()
            except Exception:
                pass
            try:
                payload["address"] = device.addressString()
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
            jprint(payload)
        except Exception:
            pass

    def deviceInquiryComplete_error_aborted_(self, sender, error, aborted):
        try:
            # Завершаем одноразовый процесс сразу
            os._exit(0)
        except Exception:
            os._exit(0)


def main():
    setup_log()
    c = ClassicOnce.alloc().init()
    c.start()
    NSRunLoop.currentRunLoop().run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()


