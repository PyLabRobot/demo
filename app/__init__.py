import asyncio
import os
import threading

from flask import Flask, request, jsonify, session, url_for, redirect
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, current_user
from flask_sock import Sock
import redis
from rq import Queue

from lib import db
from lib.conf import PRODUCTION

if PRODUCTION:
  SERVER_HOST = "http://simulator.pylabrobot.org/"
else:
  SERVER_HOST = "http://localhost/"


app = Flask(__name__, template_folder="templates", static_folder="static")
if "SECRET_KEY" in os.environ:
  app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
elif "SECRET_KEY_FILE" in os.environ:
  with open(os.environ["SECRET_KEY_FILE"]) as f:
    app.config["SECRET_KEY"] = f.read()
else:
  raise Exception("No secret key specified")

dbs = db.get_session()

@app.teardown_appcontext
def shutdown_session(exception=None):
  dbs.remove()

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
redis_pool = redis.ConnectionPool(host=redis_host, port=6379, db=0, decode_responses=True)
redis_client = redis.StrictRedis(connection_pool=redis_pool)

q = Queue(connection=redis_client)

from lib.models import *

@login_manager.user_loader
def load_user(user_id):
  return User.query.get(user_id)

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

from lib.db import engine
from lib.models.base import Base
Base.metadata.create_all(engine)
