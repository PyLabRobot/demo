# from flask_login import UserMixin
from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from lib.models.base import Base


class User(Base):#, UserMixin):
  __tablename__ = "users"

  first_name = Column(String(50), nullable=False)
  last_name = Column(String(50), nullable=False)
  username = Column(String(255), nullable=False, unique=True, index=True)
  activation_code = Column(UUID(as_uuid=True), ForeignKey("activation_codes.id"), nullable=False)
  activation = relationship("ActivationCode", backref="activation_codes", lazy="select")

  password_hash = Column(String(120), nullable=False)
  email = Column(String(80), unique=True, nullable=False, index=True)
  can_demo = Column(Boolean, default=False)

  def serialize(self):
    return {
      **super().serialize(),
      "first_name": self.first_name,
      "last_name": self.last_name,
      "username": self.username,
      "email": self.email,
    }

  # https://github.com/maxcountryman/flask-login/blob/main/src/flask_login/mixins.py
  __hash__ = object.__hash__

  @property
  def is_active(self):
    return True

  @property
  def is_authenticated(self):
    return self.is_active

  @property
  def is_anonymous(self):
    return False

  def get_id(self):
    try:
      return str(self.id)
    except AttributeError:
      raise NotImplementedError("No `id` attribute - override `get_id`") from None
