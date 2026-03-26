from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets
import markdown

from models import User
from database import SessionLocal

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["markdown"] = lambda text: markdown.markdown(text, extensions=["extra", "codehilite"])
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def truncate_password(password: str, max_bytes: int = 72) -> str:
    """Обрезает пароль до max_bytes байт (ограничение bcrypt)."""
    encoded = password.encode('utf-8')
    if len(encoded) > max_bytes:
        encoded = encoded[:max_bytes]
    return encoded.decode('utf-8', errors='ignore')

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    user = db.query(User).filter(User.session_token == session_token).first()
    return user

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    login = form.get("login")
    password = form.get("password")

    user = db.query(User).filter(User.login == login).first()
    truncated = truncate_password(password)
    if not user or not pwd_context.verify(truncated, user.password_hash):
        # Возвращаем ошибку
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный логин или пароль"})

    # Генерируем сессию
    session_token = secrets.token_urlsafe(32)
    user.session_token = session_token
    db.commit()

    response = RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="session_token", value=session_token, httponly=True)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True)
    return response

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    full_name = form.get("full_name")
    login = form.get("login")
    password = form.get("password")
    confirm_password = form.get("confirm_password")

    if password != confirm_password:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Пароли не совпадают"})

    existing = db.query(User).filter(User.login == login).first()
    if existing:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Пользователь уже существует"})

    truncated = truncate_password(password)
    hashed = pwd_context.hash(truncated)
    user = User(
        full_name=full_name,
        login=login,
        password_hash=hashed,
        is_admin=False,
        avatar_path=None,
        session_token=None
    )
    db.add(user)
    db.commit()

    # Автоматический логин
    session_token = secrets.token_urlsafe(32)
    user.session_token = session_token
    db.commit()

    response = RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="session_token", value=session_token, httponly=True)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True)
    return response

@router.get("/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    if session_token:
        user = db.query(User).filter(User.session_token == session_token).first()
        if user:
            user.session_token = None
            db.commit()
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    response.delete_cookie("user_id")
    return response