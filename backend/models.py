from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .db import Base


class Bus(Base):
	__tablename__ = "bus"

	id_bus: Mapped[str] = mapped_column(String, primary_key=True)
	devices: Mapped[list] = mapped_column(JSON, default=list)
	id_devices: Mapped[list] = mapped_column(JSON, default=list)
	count: Mapped[int] = mapped_column(Integer, default=0)


