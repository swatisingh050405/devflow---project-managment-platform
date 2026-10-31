from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    status: Literal["todo", "in_progress", "done"] = "todo"
    priority: Literal["low", "medium", "high"] = "medium"
    assignee_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: Literal["todo", "in_progress", "done"] | None = None
    priority: Literal["low", "medium", "high"] | None = None
    assignee_id: int | None = None


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    status: str
    priority: str
    project_id: int
    assignee_id: int | None
    created_by_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)