from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from lib.models.base import Base


class Event(Base):
  __tablename__ = "events"

  code = Column(String(255), nullable=False, unique=False)
  uid = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
  user = relationship("User", backref="events", lazy="select")
