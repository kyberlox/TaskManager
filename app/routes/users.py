from fastapi import APIRouter, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import shutil
import os

from models import User
from database import SessionLocal
from .auth import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads/avatars"
AVATAR_URL_PREFIX = "/uploads/avatars/"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    user = db.query(User).filter(User.session_token == session_token).first()
    return user

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("profile.html", {"request": request, "user": user})

@router.post("/profile/update")
async def update_profile(
    request: Request,
    db: Session = Depends(get_db),
    full_name: str = None,
    avatar: UploadFile = File(None)
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    if full_name:
        user.full_name = full_name

    if avatar:
        # Сохраняем аватар
        print(f"Uploading avatar: {avatar.filename}, user id: {user.id}")
        file_location = f"{UPLOAD_DIR}/{user.id}_{avatar.filename}"
        print(f"Saving to {file_location}")
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(avatar.file, buffer)
        user.avatar_path = f"{AVATAR_URL_PREFIX}{user.id}_{avatar.filename}"
        print(f"Avatar path set to {user.avatar_path}")

    db.commit()
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    users = db.query(User).all()
    return templates.TemplateResponse("users.html", {"request": request, "users": users, "current_user": user})