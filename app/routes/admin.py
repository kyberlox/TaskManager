from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
import markdown

from models import User, Task, Assistant, Category, Message, File as FileModel
from database import SessionLocal
from .auth import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["markdown"] = lambda text: markdown.markdown(text, extensions=["extra", "codehilite"])

def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    user = db.query(User).filter(User.session_token == session_token).first()
    return user

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Требуются права администратора")

    # Статистика
    total_users = db.query(func.count(User.id)).scalar()
    total_tasks = db.query(func.count(Task.id)).scalar()
    total_assistants = db.query(func.count(Assistant.id)).scalar()
    total_categories = db.query(func.count(Category.id)).scalar()
    total_messages = db.query(func.count(Message.id)).scalar()

    # Последние 5 пользователей
    recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
    # Последние 5 задач с загрузкой автора
    recent_tasks = db.query(Task).options(joinedload(Task.author)).order_by(Task.created_at.desc()).limit(5).all()

    # Все категории с загрузкой владельца
    all_categories = db.query(Category).options(joinedload(Category.owner)).order_by(Category.id).all()
    # Все задачи с загрузкой автора
    all_tasks = db.query(Task).options(joinedload(Task.author)).order_by(Task.created_at.desc()).all()
    # Все сообщения с загрузкой автора, помощника и задачи
    all_messages = db.query(Message).options(
        joinedload(Message.author),
        joinedload(Message.assistant),
        joinedload(Message.task)
    ).order_by(Message.created_at.desc()).all()
    # Все файлы с загрузкой сообщения и задачи
    all_files = db.query(FileModel).options(
        joinedload(FileModel.message).joinedload(Message.task)
    ).order_by(FileModel.id.desc()).all()

    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "total_users": total_users,
        "total_tasks": total_tasks,
        "total_assistants": total_assistants,
        "total_categories": total_categories,
        "total_messages": total_messages,
        "recent_users": recent_users,
        "recent_tasks": recent_tasks,
        "all_categories": all_categories,
        "all_tasks": all_tasks,
        "all_messages": all_messages,
        "all_files": all_files
    })