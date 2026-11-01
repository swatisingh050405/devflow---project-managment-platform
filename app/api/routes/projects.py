from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse , ProjectUpdate
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post( "/",response_model=ProjectResponse,status_code=status.HTTP_201_CREATED,)
def create_project(project_data: ProjectCreate,db: Session = Depends(get_db),current_user: User = Depends(get_current_user)):
    new_project = Project(
        name=project_data.name,
        description=project_data.description,
        owner_id=current_user.id,
    )

    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    return new_project


@router.get("/", response_model=list[ProjectResponse])
def get_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = db.query(Project).filter(
        Project.owner_id == current_user.id
    ).all()

    return projects

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db) , current_user: User = Depends(get_current_user),):
    project = db.query(Project).filter(
    Project.id == project_id,
    Project.owner_id == current_user.id
).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int,project_data: ProjectUpdate,db: Session = Depends(get_db),current_user: User = Depends(get_current_user),):
    project = db.query(Project).filter(Project.id == project_id,Project.owner_id == current_user.id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    project.name = project_data.name
    project.description = project_data.description

    db.commit()
    db.refresh(project)

    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def patch_project(project_id: int,project_data: ProjectUpdate,db: Session = Depends(get_db),current_user: User = Depends(get_current_user),):
    project = db.query(Project).filter(Project.id == project_id,Project.owner_id == current_user.id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    update_data = project_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(project, key, value)

    db.commit()
    db.refresh(project)

    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id,Project.owner_id == current_user.id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    db.delete(project)
    db.commit()

    return None