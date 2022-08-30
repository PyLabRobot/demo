import json
import subprocess
import time
from typing import Optional

from app import PRODUCTION, redis_client
from app.lib.events import (
  CONTAINER_STARTED
)

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

def container_running(uid):
  name = get_host_for_user(uid)
  out = subprocess.run("docker container inspect -f '{{.State.Running}}' %s" % name,
    shell=True, universal_newlines=True, capture_output=True)
  return out.stdout.strip() == "true"

def create_volume(uid):
  volume_name = get_volume_name_for_user(uid)

  # Create user directory if it doesn't exist
  cmd = f"docker volume create {volume_name}"
  print("creating volume", cmd)
  out = subprocess.run(cmd, shell=True, universal_newlines=True, capture_output=True)
  if out.returncode != 0:
    raise Exception(json.dumps({"msg": "error creating volume", "err": out.stderr, "out": out.stdout}))
  out = [out.stderr, out.stdout]
  print("created volume", out)
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
      raise Exception(json.dumps({"msg": "error creating container", "err": out.stderr, "out": out.stdout}))

  return None #["created volume", p.stderr, p.stdout, out]

def run_pod(uid) -> Optional[str]:
  """ Run a pod that exists. Returns error message if there is an error. """

  assert volume_exists_for_user(uid), f"volume doesn't exist for {uid} (run_pod)"
  assert container_exists(get_host_for_user(uid)), f"container doesn't exist for {uid} (run_pod)"

  cmd = f"docker start {get_host_for_user(uid)} --attach"
  print(cmd)
  p = subprocess.Popen(cmd,
    shell=True, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  while True:
    line = p.stderr.readline()
    if line is not None and "is running at:" in line:
      channel = get_pubsub_channel_name(uid)
      redis_client.publish(channel, json.dumps({"event": CONTAINER_STARTED}))
      break

    time.sleep(0.01)
    print("line:", line)
    if "error" in line.lower():
      # TODO: proper error handling, but a little is better than nothing.
      return line

  return None


# pubsub

def get_pubsub_channel_name(uid):
  return f"user-{uid}"
