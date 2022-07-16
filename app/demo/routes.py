import asyncio
import json
import functools
import os
import re
import requests
import shutil
import subprocess
import time
import threading

from flask import request, jsonify, session, url_for, redirect, Response, Blueprint, render_template, current_app
from flask_login import current_user, login_required
import websockets

from app import (
  db,
  get_session_id,
  session_has,
  session_get,
  session_set,
  session_clear,
  sock,
  USER_DIR,
  TEMPLATE_FILE_PATH,
  loop,
  DEBUG_SINGLE_SESSION,
  PRINT,
  SERVER_URL
)



demo = Blueprint("demo", __name__)


@demo.route("/")
@login_required
def index():
  return render_template("index.html")


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
      ws.send({"error": "You must be logged in to access this resource."})
      ws.close()
      return
    if not current_user.can_demo:
      ws.send({"error": "You don't have permission to access the demo."})
      ws.close()
      return
    return func(ws, *args, **kwargs)
  return wrapper


@demo.route("/clean")
def clean(): # For debug
  sid = get_session_id()
  if sid in ps:
    for p in ps[sid]:
      p.kill()
      _ = p.communicate() # clear buffers
  session_clear()
  session.clear()
  return redirect(url_for("demo.index"))


ps = {} # dict of processes ordered by session ID

#PYTHON_PATH = "/home/web/demo/env/bin/python"
PYTHON_PATH = "env/bin/python"
# JUPYTER_CONFIG_FILE = "/home/web/demo/jupyter_notebook_config.py"
JUPYTER_CONFIG_FILE = "jupyter_notebook_config.py"

def spawn_notebook_process(notebook_dir):
  if DEBUG_SINGLE_SESSION:
    return 8888, "d81df88f0b9cce858eb74c4272ac17eb084915a0349d47ff"
  notebook_p = subprocess.Popen(
    [f"{PYTHON_PATH} -m jupyter notebook --config={JUPYTER_CONFIG_FILE} {notebook_dir}  --NotebookApp.allow_origin='*'"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    universal_newlines=True, shell=True,
    env={"JUPYTER_CONFIG_DIR": "."})
  matches = None
  while (matches is None) and (notebook_p.poll() is None):
    output = notebook_p.stderr.readline()
    print("notebook read output: " + output, end="\r")
    token_regex = r"http://localhost:(?P<port>[0-9]{4,5})/notebook/\?token=(?P<token>[a-f0-9]{48})"
    matches = re.search(token_regex, output)
    time.sleep(0.01)
  port = matches.group("port")
  token = matches.group("token")
  ps[get_session_id()].append(notebook_p)
  return port, token

def spawn_kernel_gateway_process():
  if DEBUG_SINGLE_SESSION:
    return 8889
  gateway_p = subprocess.Popen(
    [f"{PYTHON_PATH} -m jupyter kernelgateway  --KernelGatewayApp.allow_origin='*'"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    universal_newlines=True, shell=True,
    env={"KG_BASE_URL":"/notebook/"})
  gateway_matches = None
  while gateway_matches is None: # TODO: check if process is still running.
    output = gateway_p.stderr.readline()
    print("gateway read output: " + output, end="\r")
    port_regex = r"Jupyter Kernel Gateway at http://127.0.0.1:(?P<port>[0-9]{4,5})"
    gateway_matches = re.search(port_regex, output)
    time.sleep(0.01)
  gateway_port = gateway_matches.group("port")
  ps[get_session_id()].append(gateway_p)
  return gateway_port

@login_required
@demo.route("/get-session", methods=["GET"])
def get_session_id_api():
  return jsonify({"session_id": get_session_id()})

def get_session():
  """ Get or create a session for the current user. """

  sid = get_session_id()

  if session_has("notebook_host") and session_has("notebook_token") and session_has("gateway_port"):
    token = session_get("notebook_token")
  else:
    user_dir = os.path.join(current_app.instance_path, USER_DIR, current_user.email)

    # Create user directory if it doesn't exist
    if not os.path.exists(user_dir):
      os.makedirs(user_dir)

      # Create template notebook file
      notebook_file = os.path.join(user_dir, "notebook.ipynb")
      shutil.copy(TEMPLATE_FILE_PATH, notebook_file)

    if sid not in ps:
      ps[get_session_id()] = []

    # launch a jupyter kernel for the user
    port, token = spawn_notebook_process(user_dir)
    gateway_port = spawn_kernel_gateway_process()

    notebook_host = f"http://localhost:{port}/"

    session_set("notebook_host", notebook_host)
    session_set("notebook_token", token)
    session_set("gateway_port", gateway_port)

  iframe_url = f"/notebook/notebooks/notebook.ipynb?token={token}"

  d = {"notebook_iframe_url": iframe_url, "session_id": get_session_id()}
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


@demo_required
@demo.route("/notebook", defaults={"path": "/"}, methods=all_methods)
@demo.route("/notebook/", defaults={"path": "/"}, methods=all_methods)
@demo.route("/notebook/<path:path>", methods=all_methods)
def notebook(path):
  gateway_port = session_get("gateway_port")
  if gateway_port is None: return f"No gateway port (session {get_session_id()})", 500

  if path == "api/kernelspecs" or path.startswith("api/kernels"):
    # real gateway requests
    forward_host = f"http://127.0.0.1:{gateway_port}/" # 127.0.0.1
  elif path == "api/sessions" and request.method.lower() == "post":
    # POST /sessions to the real gateway
    forward_host = f"http://127.0.0.1:{gateway_port}/" # 127.0.0.1
  else:
    forward_host = session_get("notebook_host")

  request_url = request.url.replace(request.host_url, forward_host)

  return forward(request_url)

notebook_ws_servers = {}
notebook_clients_dict = {}

@sock.route("/notebook/<path:path>")
@demo_required_ws
def notebook_ws(ws, path):
  notebook_ws_servers[get_session_id()] = ws

  # Why does request.url have `http://` and not `ws://`? Requests are made to ws://
  gateway_host = f"ws://localhost:{session_get('gateway_port')}/"
  if DEBUG_SINGLE_SESSION:
    gateway_host = f"ws://localhost:8889"
  url = request.url.replace(SERVER_URL, gateway_host)

  # forward websocket requests
  client_started_lock = threading.Lock()
  client_started_lock.acquire()
  print("*"*20, "client url", url)
  asyncio.run_coroutine_threadsafe(start_notebook_websocket_client(url, client_started_lock, ws), loop)
  while client_started_lock.locked():
    time.sleep(0.1)

  # `sock` is the websocket server
  while True:
    message = ws.receive()
    client = notebook_clients_dict.get(get_session_id())
    if client:
      asyncio.run_coroutine_threadsafe(send_websocket_message(message, client), loop)

    if PRINT: print("<---", message)

async def start_notebook_websocket_client(url, lock, ws):
  async with websockets.connect(url) as client:
    notebook_clients_dict[get_session_id()] = client
    lock.release()

    while True:
      message = await client.recv()
      if PRINT: print("--->", message)

      #ws = notebook_ws_servers[get_session_id()]
      ws.send(message)

      # Intercept code output from the notebook
      data = json.loads(message)

      if data.get("msg_type") == "execute_result":
        output = data["content"]["data"].get("text/plain")
      elif data.get("msg_type") == "stream":
        output = data["content"]["text"]
      else:
        output = None

      if output is not None:
        matches = re.search(r"Simulation server started at (?P<simulator_url>http://[a-zA-Z.0-9:/]+)", output)
        if matches is not None:
          # Store the simulator URL in the session and send it to the browser
          simulator_url = matches.group("simulator_url") + "/"
          simulator_url = simulator_url.replace("http://", "ws://")
          session_set("simulator_url", simulator_url)
        elif "Simulation server started at " in output:
          # Debug message for regex, not really needed
          print("No match for simulation server while output was:", output)

        # Store file server URL in the session
        matches = re.search(r"File server started at (?P<file_server_url>http://[a-zA-Z.0-9:/]+)", output)
        if matches is not None:
          # Store the file serfver URL in the session and send it to the browser
          file_server_url = matches.group("file_server_url") + "/"
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


simulator_wss = {}
simulator_clients = {}

@login_required
@demo.route("/simulator", defaults={"path": "/"})
@demo.route("/simulator/<path:path>")
def simulator_index(path):
  file_server_url = session_get("file_server_url")
  request_url = request.url.replace(request.host_url, file_server_url).replace("/simulator", "")
  return forward(request_url)

@sock.route("/simulator")
@demo_required_ws
def simulator_ws(ws):
  if not "id" in session:
    return "no session", 400

  simulator_wss[get_session_id()] = ws

  # Why does request.url have `http://` and not `ws://`?
  url = session_get("simulator_url")

  # Lock until the client has started (which connects to the real simulator), before we accept
  # any messages from our client (the browser).
  client_started_lock = threading.Lock()
  client_started_lock.acquire()
  asyncio.run_coroutine_threadsafe(start_simulator_websocket_client(url, client_started_lock, ws), loop)
  while client_started_lock.locked():
    time.sleep(0.1)

  while True:
    message = ws.receive()
    if PRINT: print("<---", message)

    client = simulator_clients.get(get_session_id())
    asyncio.run_coroutine_threadsafe(send_websocket_message(message, client), loop)

async def start_simulator_websocket_client(url, lock, ws):
  async with websockets.connect(url) as client:
    lock.release()

    simulator_clients[get_session_id()] = client
    #ws = simulator_wss[get_session_id()]

    while True:
      message = await client.recv()
      if PRINT: print("--->", message)
      ws.send(message)
