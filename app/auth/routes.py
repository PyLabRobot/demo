from flask import Blueprint, render_template, request, redirect, flash, url_for, jsonify
from flask_bcrypt import check_password_hash
from flask_login import login_user

from app import db
from app.models import User

auth = Blueprint("auth", __name__, url_prefix="/auth")


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

  return render_template("login.html")
