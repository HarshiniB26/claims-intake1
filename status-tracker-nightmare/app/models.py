from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(40), nullable=False, default="todo")
    priority = Column(Integer, nullable=False, default=3)
    completed = Column(Boolean, nullable=False, default=False)
    owner = Column(String(120), nullable=True)
    tenant_id = Column(String(80), nullable=False, default="internal")
    source_system = Column(String(80), nullable=False, default="manual")
    category = Column(String(80), nullable=False, default="general")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def as_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "completed": self.completed,
            "owner": self.owner,
            "tenant_id": self.tenant_id,
            "source_system": self.source_system,
            "category": self.category,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
