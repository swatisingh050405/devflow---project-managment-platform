from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.task import Task
from app.models.project import Project
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse , TaskUpdate

router = APIRouter(prefix="/projects/{project_id}/tasks",tags=["Tasks"],)


@router.post("/",response_model=TaskResponse,status_code=status.HTTP_201_CREATED,)

def create_task(project_id: int,task_data: TaskCreate,db: Session = Depends(get_db),):
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    if task_data.assignee_id is not None:
        assignee = db.query(User).filter(
            User.id == task_data.assignee_id
        ).first()

        if not assignee:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignee not found",
            )

    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        priority=task_data.priority,
        project_id=project_id,
        assignee_id=task_data.assignee_id,
        created_by_id=project.owner_id,
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return new_task

@router.get("/", response_model=list[TaskResponse])
def get_tasks(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    tasks = db.query(Task).filter(
        Task.project_id == project_id
    ).all()

    return tasks


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.project_id == project_id
    ).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    return task


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    project_id: int,
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.project_id == project_id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_data.assignee_id is not None:
        assignee = db.query(User).filter(
            User.id == task_data.assignee_id
        ).first()

        if not assignee:
            raise HTTPException(status_code=404, detail="Assignee not found")

    task.title = task_data.title
    task.description = task_data.description
    task.status = task_data.status
    task.priority = task_data.priority
    task.assignee_id = task_data.assignee_id

    db.commit()
    db.refresh(task)

    return task



@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(
    project_id: int,
    task_id: int,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.project_id == project_id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_data.model_dump(exclude_unset=True)

    if "assignee_id" in update_data and update_data["assignee_id"] is not None:
        assignee = db.query(User).filter(
            User.id == update_data["assignee_id"]
        ).first()

        if not assignee:
            raise HTTPException(status_code=404, detail="Assignee not found")

    for key, value in update_data.items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)

    return task



@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.project_id == project_id
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()

    return None