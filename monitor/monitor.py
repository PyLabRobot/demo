""" Use `docker events` to monitor for container events, and update things accordingly."""

import json
import os
import signal
import subprocess
import sys

import redis
from rq import Queue

sys.path.insert(0, ".")

import lib


def main():
  redis_host = os.environ.get("REDIS_HOST", "localhost")
  redis_client = redis.Redis(host=redis_host, port=6379, db=0)
  q = Queue(connection=redis_client)

  p = subprocess.Popen("docker events --format '{{json .}}' --filter 'type=container'",
    shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  session = lib.db.get_session()

  while True:
    line = p.stdout.readline()
    if not line:
      continue

    event = json.loads(line)
    print("M"*10, "event:", event)

    if event.get("Type") == "container":
      name = event.get("Actor", {}).get("Attributes", {}).get("name")
      if name is None or not name.startswith("nb-"):
        continue
      uid = name[3:] # nb-user-uuid, remove nb-. can be prettier (what if format changes?)

      if event.get("Action") == "start":
        print("M"*10, "container started:", uid)
        lib.handle_container_started(redis_client, session, uid, q)
      elif event.get("Action") == "stop" or event.get("Action") == "die":
        print("M"*10, "container stopped:", uid)
        lib.handle_container_stopped(redis_client, session, uid)
      elif event.get("Action") == "destroy":
        print("M"*10, "container destroyed:", uid)
        lib.handle_container_destroyed(redis_client, session, uid)


if __name__ == "__main__":
  signal.signal(signal.SIGTERM, lambda: sys.exit(0))
  main()
