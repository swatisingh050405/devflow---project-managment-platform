from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.user import User
from app.schemas.project_member import ProjectMemberCreate, ProjectMemberResponse
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/projects/{project_id}/members",tags=["Project Members"],)


@router.post("/", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    project_id: int,
    member_data: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    user = db.query(User).filter(
        User.id == member_data.user_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner is already part of the project")

    # Check if the user is already a member of the project

    existing_member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == member_data.user_id
    ).first()

    if existing_member:
        raise HTTPException(status_code=409, detail="User is already a project member")

    new_member = ProjectMember(
        project_id=project_id,
        user_id=member_data.user_id
    )

    db.add(new_member)
    db.commit()
    db.refresh(new_member)

    return new_member


@router.get("/", response_model=list[ProjectMemberResponse])
def get_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    members = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id
    ).all()

    return members


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Project member not found")

    db.delete(member)
    db.commit()

    return None