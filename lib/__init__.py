import json
import subprocess
import time
from typing import Optional
import uuid
from lib.models.event import Event

from lib.conf import PRODUCTION, PRINT
import lib.cache as cache
from lib.events import (
  CONTAINER_STARTED,
  CONTAINER_STOPPED,
  NOTEBOOK_STARTED,
  NOTEBOOK_STOPPED,
  SIMULATION_FILE_SERVER_STARTED,
  SIMULATION_FILE_SERVER_STOPPED,
  CONTAINER_UPGRADE,
  CONTAINER_DESTROYED
)
import worker

# utilities for working with docker containers and docker volumes

def get_host_for_user(uid):
  return f"nb-{uid}"

def get_volume_name_for_user(uid):
  volume_name = f"user-{uid}-volume"
  return volume_name

def volume_exists_for_user(uid):
  cmd = "docker volume ls"
  out = subprocess.run(cmd, shell=True, universal_newlines=True, capture_output=True)
  name = get_volume_name_for_user(uid)
  return name in out.stdout

def container_exists(name):
  out = subprocess.run(f"docker top {name}",
    shell=True, universal_newlines=True, capture_output=True)
  return not ("No such container" in out.stderr)

def create_volume(uid):
  volume_name = get_volume_name_for_user(uid)

  # Create user directory if it doesn't exist
  cmd = f"docker volume create {volume_name}"
  print("creating volume", cmd)
  out = subprocess.run(cmd, shell=True, universal_newlines=True, capture_output=True)
  if out.returncode != 0:
    raise Exception(json.dumps({"msg": "error creating volume", "err": out.stderr, "out": out.stdout}))
  out = [out.stderr, out.stdout]
  return volume_name

def create_pod(uid):
  """ Create a pod and volume for the user, if they don't exist. """

  if not volume_exists_for_user(uid):
    volume_name = create_volume(uid)
  else:
    volume_name = get_volume_name_for_user(uid)

  # create container
  container_name = get_host_for_user(uid)
  if not container_exists(container_name):
    sandbox = ""
    resources = ""
    if PRODUCTION:
      ram = "768m"
      cpu = 1
      sandbox = "--runtime=runsc"
      resources = f"-m {ram} --cpus={cpu}"

    name = f"--name={container_name}"
    network = "--net=demo_nbs"
    hostname = f"--hostname={get_host_for_user(uid)}"
    volume = f"-v {volume_name}:/nb-docker/notebooks:rw"
    platform = "--platform linux/amd64"
    cmd = f"docker create {name} {platform} {resources} {sandbox} {network} {hostname} {volume} nb-simple"
    print(cmd)
    out = subprocess.run(cmd, universal_newlines=True, capture_output=True, shell=True)

    if out.returncode != 0:
      print(json.dumps({"msg": "error creating container", "err": out.stderr, "out": out.stdout}))
      return "error creating container"

  return None #["created volume", p.stderr, p.stdout, out]

def run_pod(uid: uuid.uuid4) -> Optional[str]:
  """ Run a pod that exists. Returns error message if there is an error. """

  assert volume_exists_for_user(uid), f"volume doesn't exist for {uid} (run_pod)"
  assert container_exists(get_host_for_user(uid)), f"container doesn't exist for {uid} (run_pod)"

  cmd = f"docker start {get_host_for_user(uid)}"
  print(cmd)
  subprocess.run(cmd, shell=True, universal_newlines=True)

# event handling
def get_pubsub_channel_name(uid):
  return f"user-{uid}"

def monitor_container(uid):
  print("monitoring container" * 10)
  container_name = get_host_for_user(uid)
  cmd = f"docker logs {container_name} --follow --since 5s"
  print(cmd)
  p = subprocess.Popen(cmd, shell=True, universal_newlines=True,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  while True:
    line = p.stderr.readline()

    if PRINT: print("line:", line, end="")
    if "error" in line.lower():
      return line

    if line is not None and "is running at:" in line:
      with worker.get_redis() as r, worker.get_db_session() as session:
        time.sleep(0.5) # give it a little time, should not be needed, but beyond our control
        handle_notebook_started(r, session, uid)
      break

    time.sleep(0.0001)

# event response handlers

def save_event_db(session, uid, event):
  # save event to db
  e = Event(code=event, uid=uid)
  try:
    session.add(e)
    session.commit()
  except Exception as e:
    print("error saving event to db", e)
    session.rollback()

def handle_container_started(r, session, uid, q):
  print("HANDLER: handle_container_started")
  channel = get_pubsub_channel_name(uid)

  # check if updates are available for this container.
  # TODO: this is not really supposed to be handled by the monitor. It should be handled by the
  # worker starting the container, but how do we get the data from the worker to the browser?
  # should it send a pubsub message?
  update_available, err = check_update_available(uid)
  if err is not None:
    # we don't really care if there is an error here, just log it
    print("error checking for update", err)

  r.publish(channel, json.dumps({"event": CONTAINER_STARTED, "update_available": update_available}))
  cache.set(r, cache.keys.container_running, 1, uid)

  # Start worker task to monitor container during startup to detect notebook startup
  q.enqueue_call(monitor_container, args=(uid,))

  save_event_db(session, uid, CONTAINER_STARTED)

def handle_notebook_started(r, session, uid):
  print("HANDLER: handle_notebook_started")
  channel = get_pubsub_channel_name(uid)
  cache.set(r, cache.keys.notebook_running, 1, uid)
  r.publish(channel, json.dumps({"event": NOTEBOOK_STARTED}))

  save_event_db(session, uid, NOTEBOOK_STARTED)

def handle_simulator_started(r, session, uid):
  print("HANDLER: handle_simulator_started")
  channel = get_pubsub_channel_name(uid)
  cache.set(r, cache.keys.simulator_running, 1, uid)
  r.publish(channel, json.dumps({"event": SIMULATION_FILE_SERVER_STARTED}))

  save_event_db(session, uid, SIMULATION_FILE_SERVER_STARTED)

def handle_container_stopped(r, session, uid):
  print("HANDLER: handle_container_stopped")
  channel = get_pubsub_channel_name(uid)
  handle_notebook_stopped(r, session, uid)
  handle_simulator_stopped(r, session, uid)
  cache.set(r, cache.keys.container_running, 0, uid)
  r.publish(channel, json.dumps({"event": CONTAINER_STOPPED}))

  save_event_db(session, uid, CONTAINER_STOPPED)

def handle_notebook_stopped(r, session, uid):
  print("HANDLER: handle_notebook_stopped")
  channel = get_pubsub_channel_name(uid)
  cache.set(r, cache.keys.notebook_running, 0, uid)
  r.publish(channel, json.dumps({"event": NOTEBOOK_STOPPED}))

  save_event_db(session, uid, NOTEBOOK_STOPPED)

def handle_simulator_stopped(r, session, uid):
  print("HANDLER: handle_simulator_stopped")
  channel = get_pubsub_channel_name(uid)
  r.publish(
    channel=channel,
    message=json.dumps({
      "event": SIMULATION_FILE_SERVER_STOPPED,
    }))
  cache.set(r, cache.keys.simulator_running, 0, uid)

  save_event_db(session, uid, SIMULATION_FILE_SERVER_STOPPED)

def handle_container_destroyed(r, session, uid):
  save_event_db(session, uid, CONTAINER_DESTROYED)

def check_update_available(uid): # -> Tuple[bool, Optional[str]]:
  """ Check if there is an update available. """

  IMAGE_NAME = "nb-simple"

  # Get the current image's hash
  cmd = f"docker image inspect {IMAGE_NAME}"
  print(cmd)
  out = subprocess.run(cmd, shell=True, universal_newlines=True, capture_output=True)
  if out.returncode != 0:
    print("error getting image info", out.stderr)
    return False, "error getting image info"
  current_image_hash = json.loads(out.stdout)[0]["Id"]

  # Get docker container image id hash
  container_name = get_host_for_user(uid)
  cmd = f"docker inspect {container_name}"
  print(cmd)
  out = subprocess.run(cmd, universal_newlines=True, capture_output=True, shell=True)

  if out.returncode != 0:
    print(json.dumps({"msg": "error inspecting container", "err": out.stderr, "out": out.stdout}))
    return False, "error creating container"

  data = json.loads(out.stdout)
  image_hash = data[0]["Image"]

  if current_image_hash != image_hash:
    return True, None

  return False, None

def update_container(uid):
  container_name = get_host_for_user(uid)

  with worker.get_db_session() as session:
    save_event_db(session, uid, CONTAINER_UPGRADE)

  # Stop the current container
  cmd = f"docker stop {container_name}"
  print(cmd)
  out = subprocess.run(cmd, shell=True, universal_newlines=True, capture_output=True)
  if out.returncode != 0:
    print("error stopping container", out.stderr)
    raise Exception("error stopping container")

  # Delete the current container
  cmd = f"docker rm {container_name}"
  print(cmd)
  out = subprocess.run(cmd, shell=True, universal_newlines=True, capture_output=True)
  if out.returncode != 0:
    print("error removing container", out.stderr)
    raise Exception("error removing container")

  # Create and start a new container
  # This will be picked up by the monitor, and then appropriate events will be sent to the client
  err = create_pod(uid)
  if err:
    raise Exception("upgrade: error creating pod" + str(err))

  err = run_pod(uid)
  if err:
    raise Exception("upgrade: error running pod" + str(err))
