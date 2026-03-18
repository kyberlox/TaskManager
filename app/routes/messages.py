from fastapi import APIRouter, Request, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import shutil
import os
from datetime import datetime

from models import Message, File as FileModel, Task, User
from database import SessionLocal
from .auth import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")

UPLOAD_MESSAGE_DIR = "uploads/messages"
os.makedirs(UPLOAD_MESSAGE_DIR, exist_ok=True)

def get_current_user(request: Request, db: Session = Depends(get_db)):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    user = db.query(User).filter(User.session_token == session_token).first()
    return user

@router.post("/task/{task_id}/message")
async def send_message(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    text: str = Form(""),
    files: list[UploadFile] = File([])
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Если text равен None (не должно быть, но на всякий случай)
    if text is None:
        text = ""

    message = Message(
        text=text,
        author_id=user.id,
        task_id=task_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(message)
    db.commit()

    for uploaded_file in files:
        file_location = f"{UPLOAD_MESSAGE_DIR}/{message.id}_{uploaded_file.filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(uploaded_file.file, buffer)
        file_record = FileModel(
            name=uploaded_file.filename,
            path=file_location,
            url=f"/uploads/messages/{message.id}_{uploaded_file.filename}",
            message_id=message.id
        )
        db.add(file_record)
    db.commit()

    return RedirectResponse(url=f"/task/{task_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/message/{message_id}/edit")
async def edit_message(
    request: Request,
    message_id: int,
    db: Session = Depends(get_db),
    text: str = Form("")
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    if message.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Нет прав на редактирование")

    # Обновляем текст, даже если он пустой (пользователь мог очистить поле)
    message.text = text
    message.updated_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url=f"/task/{message.task_id}", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/message/{message_id}/delete")
async def delete_message(
    request: Request,
    message_id: int,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    if message.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Нет прав на удаление")

    # Удаляем связанные файлы (из БД и файловой системы)
    for file in message.files:
        if os.path.exists(file.path):
            try:
                os.remove(file.path)
            except Exception as e:
                print(f"Ошибка удаления файла {file.path}: {e}")
        db.delete(file)
    db.commit()

    # Удаляем само сообщение
    db.delete(message)
    db.commit()
    return RedirectResponse(url=f"/task/{message.task_id}", status_code=status.HTTP_303_SEE_OTHER)