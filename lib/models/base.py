import uuid

from sqlalchemy import Column, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID

from lib.db import Session


B = declarative_base()


class Base(B):
  __abstract__ = True

  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  created_on = Column(DateTime, default=func.now())
  updated_on = Column(DateTime, default=func.now(), onupdate=func.now())

  def serialize(self):
    return {
      "id": str(self.id),
      "created_on": self.created_on.isoformat(),
      "updated_on": self.updated_on.isoformat(),
    }

Base.query = Session.query_property()
