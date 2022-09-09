import contextlib
import os
import sys

import redis
from rq import Worker, Queue, Connection
from sqlalchemy.orm import Session

sys.path.insert(0, ".")

from lib import db

listen = ["default"]

redis_host = os.environ.get("REDIS_HOST")


@contextlib.contextmanager
def get_redis() -> redis.Redis:
  # Not optimal to create a new connection for each job, but it does not really seem possible to
  # share a connection within the worker. https://github.com/rq/rq/issues/720
  # Perhaps we can use SimpleWorker, which, as mentioned in the thread, uses a single process.
  r = redis.StrictRedis(host=redis_host, port=6379, db=0, decode_responses=False)
  try:
    yield r
  finally:
    r.close()


@contextlib.contextmanager
def get_db_session() -> Session:
  # Not optimal to create a new connection for each job, but it does not really seem possible to
  # share a connection within the worker. https://github.com/rq/rq/issues/720
  # Perhaps we can use SimpleWorker or scoped_session.
  s = db.get_session()
  try:
    yield s
  finally:
    s.remove()


if __name__ == "__main__":
  redis_client = redis.StrictRedis(host=redis_host, port=6379, db=0, decode_responses=False)

  with Connection(redis_client):
    worker = Worker(list(map(Queue, listen)))
    worker.work()
