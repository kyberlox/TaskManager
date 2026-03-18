from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os
import mimetypes
import pandas as pd

from models import File as FileModel
from database import SessionLocal
from .auth import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_current_user(request: Request, db: Session = Depends(get_db)):
    from models import User
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    user = db.query(User).filter(User.session_token == session_token).first()
    return user

@router.get("/file/{file_id}/view")
async def view_file(
    request: Request,
    file_id: int,
    db: Session = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="Файл не найден")

    # Проверяем, имеет ли пользователь доступ к сообщению (опционально)
    # Для простоты разрешаем доступ, если пользователь авторизован
    # Можно добавить проверку, что файл принадлежит задаче, к которой у пользователя есть доступ

    # Определяем MIME-тип
    mime_type, _ = mimetypes.guess_type(file.name)
    if mime_type is None:
        mime_type = "application/octet-stream"

    # Категории для рендеринга
    file_type = "unknown"
    file_content = None
    
    # Проверяем расширение файла для случаев, когда MIME-тип не определился
    file_ext = file.name.lower().split('.')[-1] if '.' in file.name else ''
    
    if mime_type.startswith("image/"):
        file_type = "image"
    elif mime_type.startswith("video/"):
        file_type = "video"
    elif mime_type == "application/pdf":
        file_type = "pdf"
    elif mime_type in ["text/plain", "text/csv", "application/json"]:
        file_type = "text"
        # Читаем содержимое текстового файла (ограничим размер)
        try:
            with open(file.path, 'r', encoding='utf-8') as f:
                content = f.read(1024 * 1024)  # максимум 1 МБ
                file_content = content
        except Exception as e:
            file_content = f"Ошибка чтения файла: {e}"
    elif mime_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       "application/msword"] or file_ext in ['doc', 'docx']:
        file_type = "doc"
    elif (mime_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       "application/vnd.ms-excel",
                       "application/vnd.oasis.opendocument.spreadsheet"] or
          file_ext in ['xlsx', 'xls', 'ods']):
        file_type = "spreadsheet"
        # Попробуем прочитать Excel/ODF файл и преобразовать в HTML таблицу
        try:
            # Определяем движок в зависимости от расширения
            if file.path.endswith('.xlsx'):
                df = pd.read_excel(file.path, engine='openpyxl', nrows=100)  # ограничим строки
            elif file.path.endswith('.xls'):
                df = pd.read_excel(file.path, engine='xlrd', nrows=100)
            elif file.path.endswith('.ods'):
                df = pd.read_excel(file.path, engine='odf', nrows=100)
            else:
                df = pd.read_excel(file.path, nrows=100)
            # Преобразуем DataFrame в HTML таблицу
            table_html = df.to_html(
                classes='table table-striped table-bordered',
                index=False,
                na_rep='',
                max_rows=100,
                max_cols=20
            )
            file_content = table_html
        except Exception as e:
            file_content = f"<p>Не удалось прочитать файл: {e}</p>"
    else:
        file_type = "download"

    return templates.TemplateResponse("file_view.html", {
        "request": request,
        "file": file,
        "file_type": file_type,
        "mime_type": mime_type,
        "file_content": file_content,
        "user": user
    })