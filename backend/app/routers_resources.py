from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.dependencies import get_current_user
from backend.app.db.models import CalendarEvent, MemoryItem, Task, User
from backend.app.db.session import get_db
from backend.app.services.serializers import calendar_to_dict, memory_to_dict, task_to_dict


router = APIRouter(tags=["resources"])


class TaskCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    priority: str = Field(default="medium", pattern="^(high|medium|low)$")


class TaskUpdateRequest(BaseModel):
    content: str | None = None
    status: str | None = Field(default=None, pattern="^(pending|in_progress|completed)$")
    priority: str | None = Field(default=None, pattern="^(high|medium|low)$")
    progress: int | None = Field(default=None, ge=0, le=100)


class MemoryCreateRequest(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1)


class CalendarCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    start_time: str = Field(min_length=1)
    end_time: str | None = None
    description: str | None = None
    event_type: str = "personal"
    location: str | None = None


@router.get("/tasks")
def list_tasks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.execute(select(Task).where(Task.user_id == user.id).order_by(Task.created_at.desc())).scalars().all()
    return {"tasks": [task_to_dict(task) for task in tasks]}


@router.post("/tasks")
def create_task(payload: TaskCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = Task(user_id=user.id, content=payload.content, priority=payload.priority)
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"task": task_to_dict(task)}


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, payload: TaskUpdateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return {"task": task_to_dict(task)}


@router.get("/memories")
def list_memories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.execute(select(MemoryItem).where(MemoryItem.user_id == user.id).order_by(MemoryItem.updated_at.desc())).scalars().all()
    return {"memories": [memory_to_dict(item) for item in items]}


@router.post("/memories")
def create_memory(payload: MemoryCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = MemoryItem(user_id=user.id, key=payload.key, value=payload.value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"memory": memory_to_dict(item)}


@router.get("/calendar/events")
def list_calendar_events(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.execute(select(CalendarEvent).where(CalendarEvent.user_id == user.id).order_by(CalendarEvent.start_time.asc())).scalars().all()
    return {"events": [calendar_to_dict(item) for item in items]}


@router.post("/calendar/events")
def create_calendar_event(payload: CalendarCreateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = CalendarEvent(
        user_id=user.id,
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        description=payload.description,
        event_type=payload.event_type,
        location=payload.location,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"event": calendar_to_dict(item)}

