from fastapi import APIRouter, Request, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
import shutil
import os

from models import Task, Category, User, Message, File as FileModel
from database import SessionLocal
from .auth import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_TASK_DIR = "uploads/tasks"
PREVIEW_URL_PREFIX = "/uploads/tasks/"
os.makedirs(UPLOAD_TASK_DIR, exist_ok=True)

def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    user = db.query(User).filter(User.session_token == session_token).first()
    return user

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Активные задачи без родителя
    tasks = db.query(Task).filter(
        Task.parent_id == None,
        Task.is_active == True
    ).options(joinedload(Task.author), joinedload(Task.category)).all()

    return templates.TemplateResponse("tasks.html", {"request": request, "tasks": tasks, "user": user})

@router.get("/tasks/create", response_class=HTMLResponse)
async def create_task_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    categories = db.query(Category).all()
    parent_id = request.query_params.get("parent_id")
    return templates.TemplateResponse("task_create.html", {
        "request": request,
        "categories": categories,
        "parent_id": parent_id
    })

@router.post("/tasks/create")
async def create_task(
    request: Request,
    db: Session = Depends(get_db),
    preview: UploadFile = File(None)
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    # Извлекаем данные формы вручную
    form_data = await request.form()
    print(f"Form keys: {list(form_data.keys())}")
    for key, value in form_data.items():
        print(f"  {key}: {value}")

    title = form_data.get("title")
    description = form_data.get("description")
    due_date = form_data.get("due_date")
    category_id = form_data.get("category_id")
    parent_id = form_data.get("parent_id")

    print(f"Extracted: title={title}, description={description}, due_date={due_date}, category_id={category_id}, parent_id={parent_id}")

    if not title:
        # Если title отсутствует или пустая строка, вернуть ошибку
        raise HTTPException(status_code=400, detail="Название задачи обязательно")

    due_date_obj = None
    if due_date:
        due_date_obj = datetime.fromisoformat(due_date)

    # Преобразование category_id и parent_id в int, если они переданы
    category_id_int = None
    if category_id and category_id.isdigit():
        category_id_int = int(category_id)

    parent_id_int = None
    if parent_id and parent_id.isdigit():
        parent_id_int = int(parent_id)

    task = Task(
        title=title,
        description=description,
        due_date=due_date_obj,
        parent_id=parent_id_int,
        author_id=user.id,
        category_id=category_id_int,
        is_active=True
    )

    if preview:
        file_location = f"{UPLOAD_TASK_DIR}/{user.id}_{preview.filename}"
        print(f"Saving preview to {file_location}")
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(preview.file, buffer)
        task.preview_image_path = f"{PREVIEW_URL_PREFIX}{user.id}_{preview.filename}"

    db.add(task)
    db.commit()
    print(f"Task created with id {task.id}")
    return RedirectResponse(url=f"/task/{task.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/task/{task_id}", response_class=HTMLResponse)
async def task_detail_page(request: Request, task_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    task = db.query(Task).options(
        joinedload(Task.author),
        joinedload(Task.category),
        joinedload(Task.children),
        joinedload(Task.messages).joinedload(Message.author),
        joinedload(Task.messages).joinedload(Message.files)
    ).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    return templates.TemplateResponse("task_detail.html", {"request": request, "task": task, "user": user})

@router.get("/task/{task_id}/edit", response_class=HTMLResponse)
async def edit_task_page(request: Request, task_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    categories = db.query(Category).all()
    return templates.TemplateResponse("task_edit.html", {
        "request": request,
        "task": task,
        "categories": categories
    })

@router.post("/task/{task_id}/edit")
async def edit_task(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    preview: UploadFile = File(None)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Извлекаем данные формы вручную
    form_data = await request.form()
    print(f"Edit form keys: {list(form_data.keys())}")

    title = form_data.get("title")
    description = form_data.get("description")
    due_date = form_data.get("due_date")
    category_id = form_data.get("category_id")
    is_active = form_data.get("is_active")

    if title:
        task.title = title
    if description is not None:
        task.description = description
    if due_date:
        task.due_date = datetime.fromisoformat(due_date)
    if category_id is not None:
        if category_id == "":
            task.category_id = None
        else:
            task.category_id = int(category_id)
    if is_active is not None:
        task.is_active = (is_active == "on")  # чекбокс возвращает "on" если отмечен

    # Обработка превью
    if preview and preview.filename:
        # Удаляем старый файл, если он есть
        if task.preview_image_path:
            old_path = task.preview_image_path.replace(PREVIEW_URL_PREFIX, UPLOAD_TASK_DIR + "/")
            if os.path.exists(old_path):
                os.remove(old_path)
        # Сохраняем новый файл
        file_location = f"{UPLOAD_TASK_DIR}/{task.author_id}_{preview.filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(preview.file, buffer)
        task.preview_image_path = f"{PREVIEW_URL_PREFIX}{task.author_id}_{preview.filename}"
        print(f"Preview updated to {task.preview_image_path}")

    db.commit()
    return RedirectResponse(url=f"/task/{task.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/task/{task_id}/delete")
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    db.delete(task)
    db.commit()
    return RedirectResponse(url="/tasks", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/api/calendar/events")
async def calendar_events(request: Request, db: Session = Depends(get_db)):
    """Возвращает задачи в формате событий для календаря."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    
    # Получаем все задачи пользователя (включая неактивные)
    tasks = db.query(Task).filter(Task.author_id == user.id).all()
    
    events = []
    for task in tasks:
        # Цвет в зависимости от категории или статуса
        color = "#6f42c1"  # фиолетовый по умолчанию
        if task.category and task.category.color:
            color = task.category.color
        elif not task.is_active:
            color = "#6c757d"  # серый для неактивных
        
        event = {
            "id": task.id,
            "title": task.title,
            "start": task.due_date.isoformat() if task.due_date else None,
            "end": task.due_date.isoformat() if task.due_date else None,
            "color": color,
            "url": f"/task/{task.id}",
            "extendedProps": {
                "description": task.description,
                "category": task.category.name if task.category else None,
                "is_active": task.is_active
            }
        }
        events.append(event)
    
    return events