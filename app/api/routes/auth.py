from datetime import datetime, timezone

import jwt
from fastapi import (APIRouter,Cookie,HTTPException,status,Depends,Response)
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token , settings
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.models.refresh_token import RefreshToken

import hashlib
import secrets

from datetime import datetime, timedelta, timezone
from fastapi import BackgroundTasks

from app.core.email import send_password_reset_email
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.schemas.auth import (
    ForgotPasswordRequest,
    ResetPasswordRequest
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/refresh")
def refresh_access_token(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db)
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing"
        )

    try:
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        user_id = int(payload.get("sub"))
        jti = payload.get("jti")

        if not jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    session = db.query(RefreshToken).filter(
        RefreshToken.jti == jti,
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False
    ).first()

    if not session or session.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or expired"
        )

    user = db.query(User).filter(
        User.id == user_id,
        User.is_active == True
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Revoke the old refresh session
    session.revoked = True

    # Generate a new pair of tokens
    new_access_token = create_access_token(user.id)
    new_refresh_token, new_jti, new_expires_at = create_refresh_token(user.id)

    # Store the new refresh session
    new_session = RefreshToken(
        user_id=user.id,
        jti=new_jti,
        expires_at=new_expires_at
    )

    db.add(new_session)
    db.commit()

    # Send the new refresh token as an HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=False,  # True in production with HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
        path="/auth"
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db)
):
    if refresh_token:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )

            if payload.get("type") == "refresh":
                jti = payload.get("jti")

                if jti:
                    session = db.query(RefreshToken).filter(
                        RefreshToken.jti == jti,
                        RefreshToken.revoked == False
                    ).first()

                    if session:
                        session.revoked = True
                        db.commit()

        except jwt.InvalidTokenError:
            pass

    response.delete_cookie(
        key="refresh_token",
        path="/auth"
    )

    return {"message": "Logged out successfully"}


@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == data.email
    ).first()

    # Same response whether the email exists or not
    if not user:
        return {
            "message": "If the email is registered, a reset link will be sent."
        }

    # Invalidate any previous unused reset tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False
    ).update(
        {"used": True},
        synchronize_session=False
    )

    # Generate a secure random token
    raw_token = secrets.token_urlsafe(32)

    # Store only its hash
    token_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )

    db.add(reset_token)
    db.commit()

    # Create the link for the frontend
    reset_link = (
        f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    )

    background_tasks.add_task(
        send_password_reset_email,
        user.email,
        reset_link
    )

    return {
        "message": "If the email is registered, a reset link will be sent."
    }


@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    # Hash the token received from the user
    token_hash = hashlib.sha256(
        data.token.encode()
    ).hexdigest()

    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used == False
    ).first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used reset token"
        )

    # Check token expiry
    if reset_token.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )

    user = db.query(User).filter(
        User.id == reset_token.user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )

    # Update password
    user.hashed_password = hash_password(data.new_password)

    # Make this reset token unusable
    reset_token.used = True

    # Revoke all refresh sessions belonging to this user
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked == False
    ).update(
        {"revoked": True},
        synchronize_session=False
    )

    db.commit()

    return {
        "message": "Password reset successful"
    }