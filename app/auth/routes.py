from flask import (
  Blueprint,
  render_template,
  request,
  redirect,
  flash,
  url_for,
  jsonify,
  current_app
)
from flask_bcrypt import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user

from app import q, dbs
from lib.models import User
from lib import create_pod

from .forms import SignUpForm

auth = Blueprint(
  "auth",
  __name__,
  url_prefix="/auth",
  template_folder="templates",
  static_folder="static"
)


@auth.route("/login", methods=["GET", "POST"])
def login():
  if request.method == "POST":
    if request.headers.get("Content-Type") == "application/json":
      data = request.json
      email = data.get("email")
      password = data.get("password")
    else:
      email = request.form.get("email")
      password = request.form.get("password")

    user = User.query.filter_by(email=email).first()
    if user is not None and check_password_hash(user.password_hash, password):
      login_user(user, remember=True)
      if request.headers.get("Content-Type") == "application/json":
        return jsonify(user.serialize())
      else:
        return redirect(url_for("demo.index"))

    if request.headers.get("Content-Type") == "application/json":
      return jsonify({"error": "Invalid email or password"}), 401
    else:
      flash("Invalid email or password", "danger")

  return render_template("auth/login.html")


@auth.route("/signup", methods=["GET", "POST"])
def signup():
  form = SignUpForm()

  if form.validate_on_submit():
    first_name = form.first_name.data
    last_name = form.last_name.data
    activation_code = form.activation_code.data
    username = form.username.data
    email = form.email.data
    password = form.password.data

    password_hash = generate_password_hash(password).decode("utf-8")
    user = User(
      email=email,
      password_hash=password_hash,
      first_name=first_name,
      last_name=last_name,
      username=username,
      activation_code=activation_code,
      can_demo=True # TODO: will probably want to set this to false some time.
    )

    dbs.add(user)
    try:
      dbs.commit()
    except Exception as e:
      dbs.rollback()
      current_app.logger.error(e)
      return jsonify({"error": "Could not sign up user"}), 500

    login_user(user, remember=True)

    # Create a container for this user in advance.
    q.enqueue_call(create_pod, args=(str(user.id),))

    return redirect(url_for("demo.index"))
  else:
    print(form.errors)

  return render_template("auth/signup.html", form=form)


@auth.route("/logout")
def logout():
  logout_user()
  return redirect(url_for("auth.login"))
