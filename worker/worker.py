import os
import sys

import redis
from rq import Worker, Queue, Connection

sys.path.insert(0, ".")

listen = ['default']

redis_host = os.environ.get("REDIS_HOST")
redis_client = redis.StrictRedis(host=redis_host, port=6379, db=0, decode_responses=False)

if __name__ == '__main__':
  with Connection(redis_client):
    worker = Worker(list(map(Queue, listen)))
    worker.work()
