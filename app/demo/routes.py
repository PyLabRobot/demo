import asyncio
import json
import functools
import re
import requests
import time
import threading
import urllib

from flask import request, jsonify, session, url_for, redirect, Response, Blueprint, render_template
from flask_login import current_user, login_required
from app.lib.events import (
  SIMULATION_FILE_SERVER_STARTED,
  SIMULATION_FILE_SERVER_STOPPED,
)
from simple_websocket import ConnectionClosed
import redis
import websockets

from app import (
  get_session_id,
  session_del,
  session_has,
  session_get,
  session_set,
  session_clear,
  sock,
  loop,
  redis_client,
  redis_pool,
  PRINT,
  SERVER_HOST,
  PRODUCTION
)
from app.lib import (
  create_pod,
  container_running,
  run_pod,
  get_pubsub_channel_name
)

demo = Blueprint("demo", __name__)

nb = 8888
sim = 2121
fs = 1337

def _get_nb_url_for_user(uid):
  host = session_get("container_host")
  return f"http://{host}:{nb}/"

def _get_sim_url_for_user(uid):
  host = session_get("container_host")
  return f"http://{host}:{sim}/"

def _get_fs_url_for_user(uid):
  host = session_get("container_host")
  return f"http://{host}:{fs}/"

def stop_simulator():
  """ Stop the simulator for the current_user. """
  channel = get_pubsub_channel_name(current_user.id)
  redis_client.publish(
    channel=channel,
    message=json.dumps({
      "event": SIMULATION_FILE_SERVER_STOPPED
    }))
  session_del("simulator_url")

@demo.route("/")
@login_required
def index():
  if PRODUCTION:
    protocol = "wss"
  else:
    protocol = "ws"
  server_host = SERVER_HOST.replace("http", protocol) # TODO: SERVER_HOST should not include http.
  master_web_socket_url = urllib.parse.urljoin(server_host, "/master")
  return render_template("index.html", master_web_socket_url=master_web_socket_url)


def demo_required(func):
  """ Decorator for routes that require demo access. """
  @functools.wraps(func)
  @login_required
  def wrapper(*args, **kwargs):
    if not current_user.can_demo:
      return "You don't have permission to access the demo."
    return func(*args, **kwargs)
  return wrapper


def demo_required_ws(func):
  """ Decorator for websockets that require demo access. """
  @functools.wraps(func)
  def wrapper(ws, *args, **kwargs):
    if not current_user.is_authenticated:
      ws.send(json.dumps({"error": "You must be logged in to access this resource.", "type": "error"}))
      ws.close()
      return
    if not current_user.can_demo:
      ws.send(json.dumps({"error": "You don't have permission to access the demo.", "type": "error"}))
      ws.close()
      return
    return func(ws, *args, **kwargs)
  return wrapper


@demo.route("/clean")
def clean(): # For debug
  session_clear()
  session.clear()
  return redirect(url_for("demo.index"))


@login_required
@demo.route("/get-session", methods=["GET"])
def get_session_id_api():
  return jsonify({"session_id": get_session_id()})

def get_session():
  """ Get or create a session for the current user. """

  # TODO: just return session id, have a ws action to actually request the start of the container,
  # and send the response there.
  # This is to save time on the request.

  sid = get_session_id()
  err = create_pod(sid) # Create_pod checks if pod exists, and if not, creates it.
  if err is not None:
    return {"error": err, "type": "error"}

  print("*"*10, "get_session", sid)
  if not container_running(sid):
    print("run pod")
    run_pod(sid)
  else:
    print("is running?", sid)

  session_set("container_host", get_host_for_user(current_user.id))

  iframe_url = f"/notebook/notebooks/notebook.ipynb"

  d = {"notebook_iframe_url": iframe_url, "session_id": sid}
  if session_has("file_server_url"): d["simulator_url"] = url_for("demo.simulator_index")
  return d

master_websocket_servers = {}

@sock.route("/master")
@demo_required_ws
def master(ws):
  """ Handle a websocket connection to the master server. """
  sid = None

  # Get new redis connection, because pubsub blocks the connection.
  r = redis.StrictRedis(connection_pool=redis_pool)
  p = r.pubsub()
  channel = get_pubsub_channel_name(current_user.id)
  p.subscribe(channel)

  while True:
    # read using timeout=0 for non-blocking, ...
    try:
      message = ws.receive(timeout=0)
    except ConnectionClosed:
      break

    # ..., which returns None if no message is available.
    if message is not None:
      # Try to decode the message as JSON.
      try: message = json.loads(message)
      except json.JSONDecodeError:
        ws.send("Invalid JSON")
        print("Invalid JSON")
        continue

      d = {"id": message.get("id"), "type": message.get("type")}

      # Handle the message.
      if message.get("type") == "set-session":
        sid = message.get("session_id")
        master_websocket_servers[sid] = ws
        print("set master", sid)
        session["id"] = sid # for `get_session`, which uses this
        d.update(get_session())
        ws.send(json.dumps(d))

    # Listen for messages on the pubsub channel.
    message = p.get_message() # also non-blocking
    if message is not None:
      if PRINT: print("!" * 10, "got pubsub message", message)

      if message.get("type") == "message":
        data = message.get("data")
        data = json.loads(data)
        event = data.get("event")

        if event == SIMULATION_FILE_SERVER_STARTED:
          ws.send(json.dumps({"type": "start-simulator", "url": data.get("simulator_url")}))
        elif event == SIMULATION_FILE_SERVER_STOPPED:
          ws.send(json.dumps({"type": "stop-simulator"}))

  try: ws.close()
  except: pass

  try: p.close()
  except: pass

ss = {}

def get_requests_session():
  """ Get or create a requests session for the current user. """
  sid = get_session_id()
  if sid not in ss:
    ss[sid] = requests.Session()
  return ss[sid]

all_methods = ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH", "CONNECT"]

def forward(url):
  """ Forward a request to {notebook, kernel gateway} server. """
  s = get_requests_session()
  requests.utils.add_dict_to_cookiejar(s.cookies, request.cookies) # needed? probably?
  headers = {key: value for key, value in request.headers}# if key != 'Host'}
  headers["X-Forwarded-Proto"] = "http"
  resp = s.request(
        method=request.method,
        url=url,
        headers={key: value for (key, value) in request.headers if key != 'Host'},
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False)

  # filter out headers that are not allowed to be sent to the client
  excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
  headers = [(k, v) for k, v in resp.headers.items() if k not in excluded_headers]
  response = Response(resp.content, resp.status_code, headers)
  if PRINT: print("*"*10, "forwarding", request.url, "->", url, f"({resp.status_code})", resp.content[:20])
  return response

def get_host_for_user(uid):
  return f"nb-{uid}"

@demo.route("/notebook", defaults={"path": "/"}, methods=all_methods)
@demo.route("/notebook/", defaults={"path": "/"}, methods=all_methods)
@demo.route("/notebook/<path:path>", methods=all_methods)
@demo_required
def notebook(path):
  forward_host = _get_nb_url_for_user(current_user.id)
  request_url = request.url.replace(request.host_url, forward_host)

  # Handle notebook events.
  if path.endswith("/restart") or \
    (path.startswith("api/sessions/") and request.method == "DELETE"):
    # On notebook restart/shutdown, the simulation server is stopped.
    stop_simulator()

  return forward(request_url)

websocket_clients = {}

def mirror(ws, url, on_message=None):
  async def send_websocket_message(message, client):
    await client.send(message)

  if PRINT: print("#"*10, "connecting ws to", url)

  # TODO: replace lock with client callback.
  async def start_websocket_client(url, lock, ws):
    print("@"*10, "connecting ws to", url)
    async with websockets.connect(url) as client:
      websocket_clients[get_session_id()] = client
      lock.release()
      print("@"*10, "connected ws to", url)

      while True:
        message = await client.recv()
        if PRINT: print("<"*10, message)
        ws.send(message)
        if on_message is not None:
          on_message(message, ws)

  client_started_lock = threading.Lock()
  client_started_lock.acquire()
  asyncio.run_coroutine_threadsafe(start_websocket_client(url, client_started_lock, ws), loop)
  while client_started_lock.locked():
    time.sleep(0.1)

  client = websocket_clients.get(get_session_id())
  while True:
    try:
      message = ws.receive()
      if PRINT: print(">"*10, message)
      asyncio.run_coroutine_threadsafe(send_websocket_message(message, client), loop)
    except ConnectionClosed:
      if PRINT: print("#"*10, "connection closed")
      break

  # close client too
  asyncio.run_coroutine_threadsafe(websocket_clients.get(get_session_id()).close(), loop)
  websocket_clients.pop(get_session_id())


def on_message(message, ws): # scan notebook output for simulation started command.
  try:
    data = json.loads(message)
  except:
    print("error parsing message", message)
    data = None

  try:
    if data.get("msg_type") == "execute_result":
      output = data["content"]["data"].get("text/plain")
    elif data.get("msg_type") == "stream":
      output = data["content"]["text"]
    else:
      output = None
  except (AttributeError, KeyError):
    pass

  # Parse notebook output to observe simulation start/stop events.
  if output is not None:
    # Store file server URL in the session
    matches = re.search(r"File server started at (?P<file_server_url>http://[a-zA-Z.0-9:/]+)", output)
    if matches is not None:
      # Store the file serfver URL in the session and send it to the browser
      # file_server_url = matches.group("file_server_url") + "/"
      file_server_url = _get_fs_url_for_user(current_user.id)
      session_set("file_server_url", file_server_url)
      print("did find fsu", file_server_url)

      # Send data to pubsub. This data will get picked up by a sub if a websocket is connected to
      # the pubsub channel.
      channel = get_pubsub_channel_name(current_user.id)
      redis_client.publish(
        channel=channel,
        message=json.dumps({
          "event": SIMULATION_FILE_SERVER_STARTED,
          "simulator_url": url_for("demo.simulator_index", path="/")
        }))
    elif "File server started at " in output:
      # Debug message for regex, not really needed
      print("No match for file server while output was:", output)

    # Store file server URL in the session
    if "server closed" in output:
      stop_simulator()


@sock.route("/notebook/<path:path>")
@demo_required_ws
def notebook_ws(ws, path):
  # Why does request.url have `http://` and not `ws://`? Requests are made to ws://
  nb_url = _get_nb_url_for_user(get_session_id())
  url = request.url.replace(SERVER_HOST, nb_url)
  url = url.replace("http", "ws")

  return mirror(ws, url, on_message)

@demo.route("/simulator", defaults={"path": "/"})
@demo.route("/simulator/<path:path>")
@login_required
def simulator_index(path):
  file_server_url = session_get("file_server_url")
  request_url = request.url.replace(request.host_url, file_server_url).replace("/simulator", "")
  return forward(request_url)

@sock.route("/simulator-ws")
@demo_required_ws
def simulator_ws(ws):
  # Why does request.url have `http://` and not `ws://`?
  url = _get_sim_url_for_user(current_user.id)
  url = url.replace("http", "ws")
  url = url.replace("-ws", "")
  return mirror(ws, url)
