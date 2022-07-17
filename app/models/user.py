from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID

from app import db
from app.models.base import Base


class User(Base, UserMixin):
  __tablename__ = "users"

  first_name = db.Column(db.String(50), nullable=False)
  last_name = db.Column(db.String(50), nullable=False)
  username = db.Column(db.String(255), nullable=False, unique=True, index=True)
  activation_code = db.Column(UUID(as_uuid=True), db.ForeignKey("activation_codes.id"), nullable=False)
  activation = db.relationship("ActivationCode", backref=db.backref("activation_codes", lazy=True))

  password_hash = db.Column(db.String(120), nullable=False)
  email = db.Column(db.String(80), unique=True, nullable=False, index=True)
  can_demo = db.Column(db.Boolean, default=False)

  def serialize(self):
    return {
      **super().serialize(),
      "first_name": self.first_name,
      "last_name": self.last_name,
      "username": self.username,
      "email": self.email,
    }
