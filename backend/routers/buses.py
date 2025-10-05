from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bus
from ..redis_client import set_count, get_count


router = APIRouter(prefix="/buses", tags=["buses"])


class BusCreatePayload(BaseModel):
	id_bus: str
	initial_count: int | None = 0


@router.post("")
def create_bus(payload: BusCreatePayload, db: Session = Depends(get_db)):
	bus = db.get(Bus, payload.id_bus)
	if bus is not None:
		raise HTTPException(status_code=409, detail="Bus already exists")
	bus = Bus(
		id_bus=payload.id_bus,
		devices=[],
		id_devices=[],
		count=int(payload.initial_count or 0),
	)
	db.add(bus)
	db.commit()
	db.refresh(bus)
	set_count(payload.id_bus, int(payload.initial_count or 0))
	return {"status": "ok", "id_bus": payload.id_bus, "count": get_count(payload.id_bus)}


@router.delete("/{id_bus}")
def delete_bus(id_bus: str, db: Session = Depends(get_db)):
	bus = db.get(Bus, id_bus)
	if bus is None:
		raise HTTPException(status_code=404, detail="Bus not found")
	db.delete(bus)
	db.commit()
	# reset Redis count to 0 when bus is deleted
	set_count(id_bus, 0)
	return {"status": "ok", "id_bus": id_bus}


