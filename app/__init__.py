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

PRINT = False

SERVER_URL = "http://127.0.0.1:5000"


app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
#app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pyhamilton-demo.db"
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://localhost/pyhamilton"
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

DEBUG_SINGLE_SESSION = True


def get_session_id():
  """ Get the session ID, creating one if it doesn't exist. This is in a cookie. """
  if DEBUG_SINGLE_SESSION: session['id'] = 'f423ddb3-8d1c-4cec-abe3-3abf3d9b7a21'
  if "id" not in session: session["id"] = str(uuid.uuid4())
  return session["id"]

# thread safe session
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0, decode_responses=True)
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
  return redirect(url_for('site.login'))

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
