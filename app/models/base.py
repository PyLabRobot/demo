import uuid

from sqlalchemy.dialects.postgresql import UUID

from app import db


class Base(db.Model):
  __abstract__ = True

  id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  created_on = db.Column(db.DateTime, default=db.func.now())
  updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

  def serialize(self):
    return {
      "id": str(self.id),
      "created_on": self.created_on.isoformat(),
      "updated_on": self.updated_on.isoformat(),
    }
