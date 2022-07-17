from app import db
from app.models.base import Base


class ActivationCode(Base):
  __tablename__ = "activation_codes"
