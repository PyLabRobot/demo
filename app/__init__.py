import asyncio
import os
import threading
import uuid

from flask import Flask, request, jsonify, render_template, session, url_for, redirect, flash, Response
from flask_bcrypt import Bcrypt, check_password_hash
from flask_login import LoginManager, current_user, login_required, login_user, UserMixin
from flask_sock import Sock
from flask_sqlalchemy import SQLAlchemy
import redis

PRINT = True

SERVER_HOST = "http://simulator.pylabrobot.org/"


app = Flask(__name__, template_folder="templates", static_folder="static")
if "SECRET_KEY" in os.environ:
  app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
elif "SECRET_KEY_FILE" in os.environ:
  with open(os.environ["SECRET_KEY_FILE"]) as f:
    app.config["SECRET_KEY"] = f.read()
else:
  raise Exception("No secret key specified")

db_host = os.environ["DB_HOST"]
db_user = os.environ["DB_USER"]
db_name = os.environ["DB_NAME"]
if "DB_PASS" in os.environ:
  db_pass = os.environ["DB_PASS"]
elif "DB_PASSWORD_FILE" in os.environ:
  with open(os.environ["DB_PASSWORD_FILE"]) as f:
    db_pass = f.read()[:-1] # remove new line character
else:
  raise Exception("No database password specified")
app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql://{db_user}:{db_pass}@{db_host}/{db_name}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_DIR"] = "uploads"
app.url_map.strict_slashes = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
sock = Sock(app)

USER_DIR = "user_data"
TEMPLATE_FILE_PATH = os.path.join(os.path.dirname(__file__), "notebook.ipynb")

DEBUG_SINGLE_SESSION = False


def get_session_id():
  """ Get the session ID, creating one if it doesn't exist. This is in a cookie. """
  if DEBUG_SINGLE_SESSION: session['id'] = 'f423ddb3-8d1c-4cec-abe3-3abf3d9b7a21'
  return str(current_user.id)

# thread safe session
redis_host = os.environ.get("REDIS_HOST", "localhost")
redis_client = redis.StrictRedis(host=redis_host, port=6379, db=0, decode_responses=True)
def _redis_key(key): return f"demo.{get_session_id()}.{key}"
def session_set(key, value): redis_client.set(_redis_key(key), value)
def session_get(key): return redis_client.get(_redis_key(key))
def session_has(key): return redis_client.exists(_redis_key(key))
def session_clear():
  for k in redis_client.scan_iter(f"demo.{get_session_id()}"): redis_client.delete(k)

from app.models import *

@login_manager.user_loader
def load_user(user_id): return User.query.get(user_id)

@login_manager.unauthorized_handler
def unauthorized():
  if request.headers.get("Content-Type") == "application/json":
    return jsonify({"error": "Unauthorized"}), 401
  return redirect(url_for('auth.login'))

def start_background_loop(loop):
  asyncio.set_event_loop(loop)
  loop.run_forever()

loop = asyncio.new_event_loop()

t = threading.Thread(target=start_background_loop, args=(loop,), daemon=True)
t.start()

from app.demo import demo
app.register_blueprint(demo)

from app.auth import auth
app.register_blueprint(auth)

from app.platform import platform
app.register_blueprint(platform)

db.create_all()

