from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from lib.models.base import Base


class Project(Base):
  __tablename__ = "projects"

  name = Column(String(100), nullable=False)

  owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
  owner = relationship("User", backref="projects", lazy="select")

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

  name = Column(String(100), nullable=False)
  path = Column(String(500), nullable=False)

  project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
  project = relationship("Project", backref="files", lazy="select")

  def __repr__(self):
    return f"File({self.name} {self.url})"

  def serialize(self):
    return {
      **super().serialize(),
      "name": self.name,
      "project_id": self.project_id,
    }
