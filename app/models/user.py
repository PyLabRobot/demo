from flask_login import UserMixin

from app import db


class User(db.Model, UserMixin):
  __tablename__ = "users"
  id = db.Column(db.Integer, primary_key=True)
  password_hash = db.Column(db.String(80), nullable=False)
  email = db.Column(db.String(80), unique=True, nullable=False)
  can_demo = db.Column(db.Boolean, default=False)
