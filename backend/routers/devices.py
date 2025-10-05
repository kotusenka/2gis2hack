from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bus
from ..redis_client import get_count, incr_count, decr_count, set_count


router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceEventPayload(BaseModel):
	id_bus: str
	id_device: str
	data: Dict[str, Any]
	flag: bool


@router.post("/event")
def handle_device_event(payload: DeviceEventPayload, db: Session = Depends(get_db)):
	bus = db.get(Bus, payload.id_bus)
	if bus is None:
		bus = Bus(
			id_bus=payload.id_bus,
			devices=[],
			id_devices=[],
			count=0,
		)
		db.add(bus)
		db.commit()
		db.refresh(bus)

	id_in_list = payload.id_device in (bus.id_devices or [])

	if payload.flag is True:
		if id_in_list:
			print(f"already present {payload.id_device} in {payload.id_bus} \n count: {get_count(payload.id_bus)}")
			return {"status": "ok", "message": "already present", "count": get_count(payload.id_bus)}
			
		# add device and increment
		devices = list(bus.devices or [])
		devices.append(payload.data)
		bus.devices = devices
		id_devices = list(bus.id_devices or [])
		id_devices.append(payload.id_device)
		bus.id_devices = id_devices
		bus.count = (bus.count or 0) + 1
		db.add(bus)
		db.commit()
		new_val = incr_count(payload.id_bus, 1)
		print(f"added {payload.id_device} to {payload.id_bus} \n count: {new_val}")
		return {"status": "ok", "message": "added", "count": new_val}

	# flag is False -> remove if exists
	if not id_in_list:
		print(f"not present {payload.id_device} in {payload.id_bus} \n count: {get_count(payload.id_bus)}")
		return {"status": "ok", "message": "not present", "count": get_count(payload.id_bus)}

	# remove
	bus.id_devices = [d for d in (bus.id_devices or []) if d != payload.id_device]
	bus.devices = [d for d in (bus.devices or []) if d != payload.data]
	bus.count = max(0, (bus.count or 0) - 1)
	db.add(bus)
	db.commit()
	new_val = decr_count(payload.id_bus, 1)
	print(f"removed {payload.id_device} from {payload.id_bus} \n count: {new_val}")
	return {"status": "ok", "message": "removed", "count": new_val}


