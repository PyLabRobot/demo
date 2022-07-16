from flask import Blueprint, render_template, request, redirect, flash, url_for
from flask_bcrypt import check_password_hash
from flask_login import login_user

from app import User, db

auth = Blueprint("auth", __name__, url_prefix="/auth")


@auth.route("/login", methods=["GET", "POST"])
def login():
  if request.method == "POST":
    email = request.form.get("email")
    password = request.form.get("password")

    user = User.query.filter_by(email=email).first()
    if user is not None and check_password_hash(user.password_hash, password):
      login_user(user, remember=True)
      return redirect(url_for("demo.index"))

    flash("Invalid email or password", "danger")

  return render_template("login.html")
