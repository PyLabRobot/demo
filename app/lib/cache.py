""" thread safe cache (in redis) """

from uuid import UUID

from redis import StrictRedis

class keys:
  container_running = "container_running"
  notebook_running = "notebook_running"
  simulator_running = "simulator_running"

def _redis_key(key: str, uid: UUID): return f"demo.{uid}.{key}"
def set(r: StrictRedis, key: str, value, uid: UUID): r.set(_redis_key(key, uid), value)
def get(r: StrictRedis, key: str, uid: UUID): return r.get(_redis_key(key, uid))
def has(r: StrictRedis, key: str, uid: UUID): return r.exists(_redis_key(key, uid))
def del_(r: StrictRedis, key: str, uid: UUID): return r.delete(_redis_key(key, uid))
def clear(r: StrictRedis, uid: UUID):
  for k in r.scan_iter(f"demo.{uid}"): r.delete(k)
