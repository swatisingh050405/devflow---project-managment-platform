from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.routes.users import router as users_router
from app.api.routes.projects import router as projects_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.project_members import router as project_members_router


app = FastAPI(title="DevFlow")

app.include_router(users_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(project_members_router)


@app.get("/")
def home():
    return {"message": "DevFlow API is running"}


@app.get("/health/db")
def check_database(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"database": "connected"}