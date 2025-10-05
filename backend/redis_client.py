from __future__ import annotations

import json
from typing import Optional, Dict

import redis
from redis.exceptions import RedisError
import time


REDIS_URL = "redis://localhost:6379/0"
CHANNEL_PREFIX = "bus_count:"

# In-memory fallback if Redis is unavailable
_FALLBACK_COUNTS: Dict[str, int] = {}


def get_redis_client() -> Optional[redis.Redis]:
	try:
		client = redis.from_url(REDIS_URL, decode_responses=True)
		# ping to ensure connectivity
		client.ping()
		return client
	except Exception:
		return None


def _count_key(id_bus: str) -> str:
	return f"count:{id_bus}"


def _channel_name(id_bus: str) -> str:
	return f"{CHANNEL_PREFIX}{id_bus}"


def get_count(id_bus: str) -> int:
	r = get_redis_client()
	if r is None:
		return int(_FALLBACK_COUNTS.get(id_bus, 0))
	try:
		value = r.get(_count_key(id_bus))
		return int(value) if value is not None else 0
	except RedisError:
		return int(_FALLBACK_COUNTS.get(id_bus, 0))


def set_count(id_bus: str, value: int) -> None:
	r = get_redis_client()
	_FALLBACK_COUNTS[id_bus] = int(value)
	if r is None:
		return
	try:
		r.set(_count_key(id_bus), value)
		r.publish(_channel_name(id_bus), json.dumps({"id_bus": id_bus, "count": value}))
	except RedisError:
		pass


def incr_count(id_bus: str, by: int = 1) -> int:
	r = get_redis_client()
	if r is None:
		_FALLBACK_COUNTS[id_bus] = int(_FALLBACK_COUNTS.get(id_bus, 0)) + int(by)
		return int(_FALLBACK_COUNTS[id_bus])
	try:
		new_val = r.incrby(_count_key(id_bus), by)
		r.publish(_channel_name(id_bus), json.dumps({"id_bus": id_bus, "count": int(new_val)}))
		_FALLBACK_COUNTS[id_bus] = int(new_val)
		return int(new_val)
	except RedisError:
		_FALLBACK_COUNTS[id_bus] = int(_FALLBACK_COUNTS.get(id_bus, 0)) + int(by)
		return int(_FALLBACK_COUNTS[id_bus])


def decr_count(id_bus: str, by: int = 1) -> int:
	r = get_redis_client()
	if r is None:
		_FALLBACK_COUNTS[id_bus] = max(0, int(_FALLBACK_COUNTS.get(id_bus, 0)) - int(by))
		return int(_FALLBACK_COUNTS[id_bus])
	try:
		new_val = r.decrby(_count_key(id_bus), by)
		if new_val < 0:
			new_val = 0
			r.set(_count_key(id_bus), 0)
		r.publish(_channel_name(id_bus), json.dumps({"id_bus": id_bus, "count": int(new_val)}))
		_FALLBACK_COUNTS[id_bus] = int(new_val)
		return int(new_val)
	except RedisError:
		_FALLBACK_COUNTS[id_bus] = max(0, int(_FALLBACK_COUNTS.get(id_bus, 0)) - int(by))
		return int(_FALLBACK_COUNTS[id_bus])


def reset_count(id_bus: str) -> None:
	r = get_redis_client()
	_FALLBACK_COUNTS[id_bus] = 0
	if r is None:
		return
	try:
		r.delete(_count_key(id_bus))
		r.publish(_channel_name(id_bus), json.dumps({"id_bus": id_bus, "count": 0}))
	except RedisError:
		pass


def subscribe_count(id_bus: str):
	"""Return a pubsub-like object with get_message(timeout) and close().
	If Redis is not available, returns a dummy compatible object.
	"""
	r = get_redis_client()
	if r is None:
		class _Dummy:
			def __init__(self, bus_id: str):
				self._bus_id = bus_id
			def get_message(self, ignore_subscribe_messages: bool = True, timeout: float = 1.0):
				# Sleep for timeout to mimic blocking poll
				time.sleep(timeout or 0)
				return {"type": "message", "data": json.dumps({"id_bus": self._bus_id, "count": int(_FALLBACK_COUNTS.get(self._bus_id, 0))})}
			def close(self):
				return None
		return _Dummy(id_bus)
	pubsub = r.pubsub()
	pubsub.subscribe(_channel_name(id_bus))
	return pubsub
