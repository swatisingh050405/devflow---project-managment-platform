from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi import Response
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse , UserLogin , UserProfileUpdate , UserPasswordUpdate
from app.core.security import hash_password , verify_password , create_access_token, create_refresh_token
from fastapi.security import OAuth2PasswordRequestForm
from app.core.dependencies import get_current_user
from app.models.refresh_token import RefreshToken



router = APIRouter(prefix="/users", tags=["Users"])

# user routes


# register user
@router.post( "/", response_model=UserResponse, status_code=status.HTTP_201_CREATED,)
def create_user(user_data: UserCreate, db: Session = Depends(get_db),):
    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    new_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# login
@router.post("/login")
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == form_data.username
    ).first()

    if not user or not verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    access_token = create_access_token(user.id)

    refresh_token, jti, expires_at = create_refresh_token(user.id)

    refresh_session = RefreshToken(
        user_id=user.id,
        jti=jti,
        expires_at=expires_at
    )

    db.add(refresh_session)
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # True in production with HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/auth"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
# get all users
@router.get("/", response_model=list[UserResponse])

def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users


# delete user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    db.delete(user)
    db.commit()

    return None


# get my profile
@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user:User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_my_profile(profile_data: UserProfileUpdate,db: Session =Depends(get_db),current_user: User = Depends(get_current_user)):
    if profile_data.email:
        existing_user = db.query(User).filter(
            User.email == profile_data.email,
            User.id != current_user.id
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

    update_data = profile_data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)

    return current_user


@router.patch("/me/password")
def change_password(
    password_data: UserPasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not verify_password(
        password_data.current_password,
        current_user.hashed_password
    ):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    current_user.hashed_password = hash_password(
        password_data.new_password
    )

    db.commit()

    return {"message": "Password updated successfully"}