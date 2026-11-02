from datetime import datetime

from pydantic import BaseModel, EmailStr, ConfigDict


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    email: EmailStr
    password: str



class UserProfileUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str