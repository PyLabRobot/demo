from flask_login import UserMixin

from app import db
from app.models.base import Base


class User(Base, UserMixin):
  __tablename__ = "users"
  password_hash = db.Column(db.String(120), nullable=False)
  email = db.Column(db.String(80), unique=True, nullable=False)
  can_demo = db.Column(db.Boolean, default=False)

  def serialize(self):
    return {
      **super().serialize(),
      "email": self.email,
    }
