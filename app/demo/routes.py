import asyncio
import json
import functools
import re
import requests
import time
import threading
import urllib

from flask import request, jsonify, session, url_for, redirect, Response, Blueprint, render_template, current_app
from flask_login import current_user, login_required
from simple_websocket import ConnectionClosed
import websockets

from app import (
  get_session_id,
  session_has,
  session_get,
  session_set,
  session_clear,
  sock,
  loop,
  PRINT,
  SERVER_HOST,
  PRODUCTION
)
from app.lib import (
  create_pod,
  container_running,
  run_pod
)

demo = Blueprint("demo", __name__)

# helper when not running in a cluster.
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

  while True:
    message = ws.receive()
    try: message = json.loads(message)
    except json.JSONDecodeError:
      ws.send("Invalid JSON")
      print("Invalid JSON")
      continue

    d = {"id": message.get("id"), "type": message.get("type")}

    if message.get("type") == "set-session":
      sid = message.get("session_id")
      master_websocket_servers[sid] = ws
      print("set master", sid)
      session["id"] = sid # for `get_session`, which uses this
      d.update(get_session())
      ws.send(json.dumps(d))

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

async def send_websocket_message(message, client):
  await client.send(message)

def get_host_for_user(uid):
  return f"nb-{uid}"

@demo.route("/notebook", defaults={"path": "/"}, methods=all_methods)
@demo.route("/notebook/", defaults={"path": "/"}, methods=all_methods)
@demo.route("/notebook/<path:path>", methods=all_methods)
@demo_required
def notebook(path):
  forward_host = _get_nb_url_for_user(current_user.id)
  request_url = request.url.replace(request.host_url, forward_host)
  return forward(request_url)

websocket_clients = {}

def mirror(ws, url, on_message=None):
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

    print("output:", output)
  except:
    print("whatever, blah")

  if output is not None:
    matches = re.search(r"Simulation server started at (?P<simulator_url>http://[a-zA-Z.0-9:/]+)", output)
    if matches is not None:
      # Store the simulator URL in the session and send it to the browser
      simulator_url = matches.group("simulator_url") + "/"
      simulator_url = simulator_url.replace("http://", "wss://")
      session_set("simulator_url", simulator_url)
    elif "Simulation server started at " in output:
      # Debug message for regex, not really needed
      print("No match for simulation server while output was:", output)
    session_set("simulator_url", _get_sim_url_for_user(current_user.id))
    print("Simulator URL:", session_get("simulator_url"))

    # Store file server URL in the session
    matches = re.search(r"File server started at (?P<file_server_url>http://[a-zA-Z.0-9:/]+)", output)
    if matches is not None:
      # Store the file serfver URL in the session and send it to the browser
      # file_server_url = matches.group("file_server_url") + "/"
      file_server_url = _get_fs_url_for_user(current_user.id)
      session_set("file_server_url", file_server_url)
      print("did find fsu", file_server_url)

      mws = master_websocket_servers.get(get_session_id())
      if mws is not None:
        mws.send(json.dumps({
          "type": "set-file-server",
          "simulator_url": url_for("demo.simulator_index", path="/")
        }))
      else: print("mws is none with ", get_session_id())
    elif "File server started at " in output:
      # Debug message for regex, not really needed
      print("No match for file server while output was:", output)


@sock.route("/notebook/<path:path>")
@demo_required_ws
def notebook_ws(ws, path):
  # Why does request.url have `http://` and not `ws://`? Requests are made to ws://
  nb_url = _get_nb_url_for_user(get_session_id())
  url = request.url.replace(SERVER_HOST, nb_url)
  url = url.replace("http", "ws")

  return mirror(ws, url, on_message)

@login_required
@demo.route("/simulator", defaults={"path": "/"})
@demo.route("/simulator/<path:path>")
def simulator_index(path):
  file_server_url = session_get("file_server_url")
  request_url = request.url.replace(request.host_url, file_server_url).replace("/simulator", "")
  print(file_server_url, request.host_url, request_url)
  return forward(request_url)

@sock.route("/simulator-ws")
@demo_required_ws
def simulator_ws(ws):
  # Why does request.url have `http://` and not `ws://`?
  url = _get_sim_url_for_user(current_user.id)
  print("sim url for user:", url)
  print(1000*"sim url for user:", url)
  url = url.replace("http", "ws")
  url = url.replace("-ws", "")

  return mirror(ws, url)
