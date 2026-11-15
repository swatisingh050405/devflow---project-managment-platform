
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.session import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate
)
from app.core.dependencies import (
    get_current_user,
    require_project_owner,
    require_project_member
)

router = APIRouter(prefix="/projects", tags=["Projects"])


# CREATE PROJECT
@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED
)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_project = Project(
        name=project_data.name,
        description=project_data.description,
        owner_id=current_user.id
    )

    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    return new_project


# GET ALL PROJECTS VISIBLE TO CURRENT USER
@router.get("/", response_model=list[ProjectResponse])
def get_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Project)

    # Admin can see every project
    if current_user.role == "admin":
        return query.all()

    # Normal users can see projects they own
    # OR projects they are members of
    member_project_ids = db.query(
        ProjectMember.project_id
    ).filter(
        ProjectMember.user_id == current_user.id
    )

    projects = query.filter(
        or_(
            Project.owner_id == current_user.id,
            Project.id.in_(member_project_ids)
        )
    ).all()

    return projects


# GET ONE PROJECT
@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_member)
):
    project = db.query(Project).filter(
        Project.id == project_id
    ).first()

    return project


# REPLACE PROJECT DETAILS
@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_owner)
):
    project = db.query(Project).filter(
        Project.id == project_id
    ).first()

    project.name = project_data.name
    project.description = project_data.description

    db.commit()
    db.refresh(project)

    return project


# PARTIALLY UPDATE PROJECT
@router.patch("/{project_id}", response_model=ProjectResponse)
def patch_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_owner)
):
    project = db.query(Project).filter(
        Project.id == project_id
    ).first()

    update_data = project_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(project, key, value)

    db.commit()
    db.refresh(project)

    return project


# DELETE PROJECT
@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_project_owner)
):
    project = db.query(Project).filter(
        Project.id == project_id
    ).first()

    db.delete(project)
    db.commit()

    return None
