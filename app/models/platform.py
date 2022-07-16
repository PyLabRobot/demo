from sqlalchemy.dialects.postgresql import UUID

from app import db
from app.models.base import Base


class Project(Base):
  __tablename__ = "projects"

  name = db.Column(db.String(100), nullable=False)

  owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
  owner = db.relationship("User", backref=db.backref("proejcts", lazy=True))

  def __repr__(self):
    return f"Project({self.name})"

  def serialize(self):
    return {
      **super().serialize(),
      "name": self.name,
      "owner_id": self.owner_id,
      "files": [file.serialize() for file in self.files],
    }


class File(Base):
  __tablename__ = "files"

  name = db.Column(db.String(100), nullable=False)
  path = db.Column(db.String(500), nullable=False)

  project_id = db.Column(UUID(as_uuid=True), db.ForeignKey("projects.id"), nullable=False)
  project = db.relationship("Project", backref=db.backref("files", lazy=True))

  def __repr__(self):
    return f"File({self.name} {self.url})"

  def serialize(self):
    return {
      **super().serialize(),
      "name": self.name,
      "project_id": self.project_id,
    }
