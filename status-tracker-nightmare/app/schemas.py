from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: Optional[str] = None
    status: str = "todo"
    priority: int = 3
    owner: Optional[str] = None
    source_system: str = "manual"
    category: str = "general"


class TaskUpdate(BaseModel):
    title: str = ""
    description: Optional[str] = None
    status: str = "todo"
    priority: int = 3
    completed: bool = False
    owner: Optional[str] = None
    source_system: str = "manual"
    category: str = "general"


class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    priority: int
    completed: bool
    owner: Optional[str] = None
    tenant_id: str
    source_system: str
    category: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
