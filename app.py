""" Demo server """

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
import uuid

from flask import Flask, request, jsonify, render_template, session, url_for, redirect, flash, Response
from flask_bcrypt import Bcrypt, check_password_hash
from flask_login import LoginManager, current_user, login_required, login_user, UserMixin
from flask_sock import Sock
from flask_sqlalchemy import SQLAlchemy
import redis
import websockets


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pyhamilton-demo.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.url_map.strict_slashes = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
sock = Sock(app)

USER_DIR = "user_data"
TEMPLATE_FILE_PATH = os.path.join(os.path.dirname(__file__), "notebook.ipynb")


def get_session_id():
  """ Get the session ID, creating one if it doesn't exist. This is in a cookie. """
  if "id" not in session: session["id"] = str(uuid.uuid4())
  return session["id"]

def login_required_ws(func):
  """ Decorator for websockets that requires login. """
  @functools.wraps(func)
  def wrapper(ws, *args, **kwargs):
    if not current_user.is_authenticated:
      ws.send({"error": "You must be logged in to access this resource."})
      ws.close()
    return func(ws, *args, **kwargs)
  return wrapper

# thread safe session
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)
def _redis_key(key): return f"demo.{get_session_id()}.{key}"
def session_set(key, value): redis_client.set(_redis_key(key), value)
def session_get(key): return redis_client.get(_redis_key(key))
def session_has(key): return redis_client.exists(_redis_key(key))
def session_clear():
  for k in redis_client.scan_iter(f"demo.{get_session_id()}"): redis_client.delete(k)


class User(db.Model, UserMixin):
  __tablename__ = "users"
  id = db.Column(db.Integer, primary_key=True)
  password_hash = db.Column(db.String(80), nullable=False)
  email = db.Column(db.String(80), unique=True, nullable=False)

  def __init__(self, password_hash, email):
    self.password_hash = password_hash
    self.email = email

db.create_all()

@login_manager.user_loader
def load_user(user_id): return User.query.get(user_id)


@app.route("/")
@login_required
def index():
  return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
  if request.method == "POST":
    email = request.form.get("email")
    password = request.form.get("password")

    user = User.query.filter_by(email=email).first()
    if user is not None and check_password_hash(user.password_hash, password):
      login_user(user, remember=True)
      return redirect(url_for("index"))

    flash("Invalid email or password danger")

  return render_template("login.html")


@app.route("/clean")
def clean(): # For debug
  sid = get_session_id()
  if sid in ps:
    for p in ps[sid]:
      p.kill()
      _ = p.communicate() # clear buffers
  session_clear()
  session.clear()
  return redirect(url_for("index"))


ps = {} # dict of processes ordered by session ID

def spawn_notebook_process(notebook_dir):
  notebook_p = subprocess.Popen(
    [f"env/bin/python -m jupyter notebook --config=jupyter_notebook_config.py {notebook_dir}"],
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
  gateway_p = subprocess.Popen(
    ["env/bin/python -m jupyter kernelgateway"],
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
@app.route("/get-session", methods=["GET"])
def get_session_id_api():
  return jsonify({"session_id": get_session_id()})

def get_session():
  """ Get or create a session for the current user. """

  sid = get_session_id()

  if session_has("notebook_host") and session_has("notebook_token") and session_has("gateway_port"):
    token = session_get("notebook_token")
  else:
    user_dir = os.path.join(app.instance_path, USER_DIR, current_user.email)

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
  if session_has("file_server_url"): d["simulator_url"] = url_for("simulator_index")
  return d


master_websocket_servers = {}

@sock.route("/master")
@login_required_ws
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
      session["id"] = sid # for `get_session`
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
  requests.utils.add_dict_to_cookiejar(s.cookies, request.cookies)
  resp = s.request(
        method=request.method,
        url=url,
        headers=request.headers,
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False)

  # filter out headers that are not allowed to be sent to the client
  excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
  headers = [(k, v) for k, v in resp.headers.items() if k not in excluded_headers]
  response = Response(resp.content, resp.status_code, headers)
  return response

async def send_websocket_message(message, client):
  await client.send(message)


@login_required
@app.route("/notebook", defaults={"path": "/"}, methods=all_methods)
@app.route("/notebook/", defaults={"path": "/"}, methods=all_methods)
@app.route("/notebook/<path:path>", methods=all_methods)
def notebook(path):
  gateway_port = session_get("gateway_port")
  if gateway_port is None: return f"No gateway port (session {get_session_id()})", 500

  if path == "api/kernelspecs" or path.startswith("api/kernels"):
    # real gateway requests
    forward_host = f"http://127.0.0.1:{gateway_port}/"
  elif path == "api/sessions" and request.method.lower() == "post":
    # POST /sessions to the real gateway
    forward_host = f"http://127.0.0.1:{gateway_port}/"
  else:
    forward_host = session_get("notebook_host")

  request_url = request.url.replace(request.host_url, forward_host)

  return forward(request_url)

notebook_ws_servers = {}
notebook_clients_dict = {}

@sock.route("/notebook/<path:path>")
@login_required_ws
def notebook_ws(ws, path):
  notebook_ws_servers[get_session_id()] = ws

  # Why does request.url have `http://` and not `ws://`? Requests are made to ws://
  gateway_host = f"ws://localhost:{session_get('gateway_port')}/"
  url = request.url.replace("http://127.0.0.1:5000/", gateway_host)

  # forward websocket requests
  asyncio.run_coroutine_threadsafe(start_notebook_websocket_client(url), loop)

  # `sock` is the websocket server
  while True:
    message = ws.receive()
    client = notebook_clients_dict.get(get_session_id())
    if client:
      asyncio.run_coroutine_threadsafe(send_websocket_message(message, client), loop)

    print("<---", message)

async def start_notebook_websocket_client(url):
  async with websockets.connect(url) as client:
    notebook_clients_dict[get_session_id()] = client

    while True:
      message = await client.recv()
      print("--->", message)
      session.pop("index", None)

      ws = notebook_ws_servers[get_session_id()]
      ws.send(message)

      # Intercept code output from the notebook
      data = json.loads(message)

      if data.get("msg_type") == "execute_result":
        output = data["content"]["data"].get("text/plain")
      elif data.get("msg_type") == "stream":
        output = data["content"]["text"]
      else:
        output = None

      mws = master_websocket_servers.get(get_session_id())
      if output is not None and mws is not None:
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
          mws.send(json.dumps({
            "type": "set-file-server",
            "simulator_url": url_for("simulator_index", path="/")
          }))
        elif "File server started at " in output:
          # Debug message for regex, not really needed
          print("No match for file server while output was:", output)


simulator_wss = {}
simulator_clients = {}

@login_required
@app.route("/simulator", defaults={"path": "/"})
@app.route("/simulator/<path:path>")
def simulator_index(path):
  file_server_url = session_get("file_server_url")
  request_url = request.url.replace(request.host_url, file_server_url).replace("/simulator", "")
  return forward(request_url)

@sock.route("/simulator")
@login_required_ws
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
  asyncio.run_coroutine_threadsafe(start_simulator_websocket_client(url, client_started_lock), loop)
  while client_started_lock.locked():
    time.sleep(0.1)

  while True:
    message = ws.receive()
    print("<---", message)

    client = simulator_clients.get(get_session_id())
    asyncio.run_coroutine_threadsafe(send_websocket_message(message, client), loop)

async def start_simulator_websocket_client(url, lock):
  async with websockets.connect(url) as client:
    lock.release()

    simulator_clients[get_session_id()] = client
    ws = simulator_wss[get_session_id()]

    while True:
      message = await client.recv()
      print("--->", message)
      ws.send(message)


def start_background_loop(loop):
  asyncio.set_event_loop(loop)
  loop.run_forever()


loop = asyncio.new_event_loop()


if __name__ == "__main__":
  t = threading.Thread(target=start_background_loop, args=(loop,), daemon=True)
  t.start()

  app.run()
