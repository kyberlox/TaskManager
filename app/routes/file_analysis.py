from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
import shutil
import tempfile
from typing import Optional

from database import SessionLocal
from models import File as FileModel, User
from .auth import get_db
from file_reader import read_file_content, summarize_text, analyze_text_with_prompt
from gigachat_client import gigachat

router = APIRouter()

UPLOAD_TEMP_DIR = "temp_uploads"
os.makedirs(UPLOAD_TEMP_DIR, exist_ok=True)

def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Получить текущего пользователя из сессии."""
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    user = db.query(User).filter(User.session_token == session_token).first()
    return user

@router.post("/api/analyze/file/summary")
async def file_summary(
    request: Request,
    file_id: Optional[int] = Form(None),
    uploaded_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Возвращает краткое содержание файла.
    Можно передать либо file_id (ID файла в БД), либо загрузить файл напрямую.
    """
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    file_path = None
    cleanup = False

    try:
        if file_id:
            # Получаем файл из БД
            file_record = db.query(FileModel).filter(FileModel.id == file_id).first()
            if not file_record:
                raise HTTPException(status_code=404, detail="Файл не найден")
            # Проверяем доступ: файл должен принадлежать сообщению, которое принадлежит задаче пользователя
            # Упрощённая проверка: пока разрешаем доступ к любому файлу (можно доработать)
            file_path = file_record.path
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Файл отсутствует на диске")
        elif uploaded_file:
            # Сохраняем загруженный файл во временную папку
            temp_dir = tempfile.mkdtemp(dir=UPLOAD_TEMP_DIR)
            file_path = os.path.join(temp_dir, uploaded_file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)
            cleanup = True
        else:
            raise HTTPException(status_code=400, detail="Не указан file_id или файл")

        # Чтение содержимого
        success, content, error = read_file_content(file_path)
        if not success:
            raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {error}")

        # Генерация краткого содержания с помощью GigaChat
        # Для простоты используем summarize_text, но лучше вызвать LLM
        summary = summarize_text(content)
        # Можно заменить на вызов gigachat
        # summary = await gigachat.summarize(content)

        return JSONResponse({
            "success": True,
            "summary": summary,
            "file_name": os.path.basename(file_path),
            "content_length": len(content)
        })
    finally:
        if cleanup and file_path and os.path.exists(file_path):
            # Удаляем временный файл и папку
            temp_dir = os.path.dirname(file_path)
            shutil.rmtree(temp_dir, ignore_errors=True)

@router.post("/api/analyze/file/detailed")
async def file_detailed_analysis(
    request: Request,
    file_id: Optional[int] = Form(None),
    uploaded_file: Optional[UploadFile] = File(None),
    prompt: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Детальный анализ файла с пользовательским промтом.
    """
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    file_path = None
    cleanup = False

    try:
        if file_id:
            file_record = db.query(FileModel).filter(FileModel.id == file_id).first()
            if not file_record:
                raise HTTPException(status_code=404, detail="Файл не найден")
            file_path = file_record.path
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Файл отсутствует на диске")
        elif uploaded_file:
            temp_dir = tempfile.mkdtemp(dir=UPLOAD_TEMP_DIR)
            file_path = os.path.join(temp_dir, uploaded_file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(uploaded_file.file, buffer)
            cleanup = True
        else:
            raise HTTPException(status_code=400, detail="Не указан file_id или файл")

        success, content, error = read_file_content(file_path)
        if not success:
            raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {error}")

        # Анализ с помощью GigaChat
        # Формируем сообщение для LLM
        messages = [
            {"role": "system", "content": "Ты помощник для анализа файлов. Пользователь предоставил файл и промт."},
            {"role": "user", "content": f"Содержимое файла:\n```\n{content[:5000]}\n```\n\nПромт: {prompt}"}
        ]
        response = await gigachat.send_message(messages=messages)
        if "error" in response:
            analysis = f"Ошибка при анализе: {response['error']}"
        else:
            analysis = response.get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа")

        return JSONResponse({
            "success": True,
            "analysis": analysis,
            "file_name": os.path.basename(file_path),
            "prompt": prompt
        })
    finally:
        if cleanup and file_path and os.path.exists(file_path):
            temp_dir = os.path.dirname(file_path)
            shutil.rmtree(temp_dir, ignore_errors=True)