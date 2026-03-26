

from fastapi import APIRouter, Request, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
import shutil
import os
import json
import markdown
import uuid
import logging

from models import Task, Category, User, Message, File as FileModel, Assistant
from gigachat_client import gigachat, GigaChatAPIError
from database import SessionLocal
from .auth import get_db
import file_reader

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["markdown"] = lambda text: markdown.markdown(text, extensions=["extra", "codehilite"])

logger = logging.getLogger(__name__)

UPLOAD_TASK_DIR = "uploads/tasks"
PREVIEW_URL_PREFIX = "/uploads/tasks/"
GENERATED_IMAGES_DIR = "uploads/generated_images"
GENERATED_CODE_DIR = "uploads/generated_code"
os.makedirs(UPLOAD_TASK_DIR, exist_ok=True)
os.makedirs(GENERATED_IMAGES_DIR, exist_ok=True)
os.makedirs(GENERATED_CODE_DIR, exist_ok=True)

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

    # Активные задачи без родителя, принадлежащие текущему пользователю
    tasks = db.query(Task).filter(
        Task.parent_id == None,
        Task.is_active == True,
        Task.author_id == user.id
    ).options(joinedload(Task.author), joinedload(Task.category)).all()

    return templates.TemplateResponse("tasks.html", {"request": request, "tasks": tasks, "user": user})

@router.get("/tasks/create", response_class=HTMLResponse)
async def create_task_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    categories = db.query(Category).filter(Category.owner_id == user.id).all()
    parent_id = request.query_params.get("parent_id")
    # Все задачи пользователя для выбора родителя
    available_parents = db.query(Task).filter(Task.author_id == user.id).all()
    return templates.TemplateResponse("task_create.html", {
        "request": request,
        "categories": categories,
        "parent_id": parent_id,
        "available_parents": available_parents
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

    # Администратор может видеть любую задачу, обычный пользователь — только свою
    query = db.query(Task).options(
        joinedload(Task.author),
        joinedload(Task.category),
        joinedload(Task.children),
        joinedload(Task.messages).joinedload(Message.author),
        joinedload(Task.messages).joinedload(Message.assistant),
        joinedload(Task.messages).joinedload(Message.files)
    ).filter(Task.id == task_id)
    if not user.is_admin:
        query = query.filter(Task.author_id == user.id)
    task = query.first()

    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Получаем помощников: публичные + принадлежащие пользователю
    assistants = db.query(Assistant).filter(
        (Assistant.is_public == True) | (Assistant.owner_id == user.id)
    ).all()

    return templates.TemplateResponse("task_detail.html", {
        "request": request,
        "task": task,
        "user": user,
        "assistants": assistants
    })

@router.get("/task/{task_id}/edit", response_class=HTMLResponse)
async def edit_task_page(request: Request, task_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    # Администратор может редактировать любую задачу, обычный пользователь — только свою
    query = db.query(Task).filter(Task.id == task_id)
    if not user.is_admin:
        query = query.filter(Task.author_id == user.id)
    task = query.first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена или нет доступа")
    # Категории: администратор видит все категории, обычный пользователь — только свои
    if user.is_admin:
        categories = db.query(Category).all()
    else:
        categories = db.query(Category).filter(Category.owner_id == user.id).all()
    # Задачи для выбора родителя: администратор видит все задачи, кроме текущей
    if user.is_admin:
        available_parents = db.query(Task).filter(Task.id != task_id).all()
    else:
        available_parents = db.query(Task).filter(Task.author_id == user.id, Task.id != task_id).all()
    return templates.TemplateResponse("task_edit.html", {
        "request": request,
        "task": task,
        "categories": categories,
        "available_parents": available_parents,
        "user": user
    })

@router.post("/task/{task_id}/edit")
async def edit_task(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    preview: UploadFile = File(None)
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    # Администратор может редактировать любую задачу, обычный пользователь — только свою
    query = db.query(Task).filter(Task.id == task_id)
    if not user.is_admin:
        query = query.filter(Task.author_id == user.id)
    task = query.first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена или нет доступа")

    # Извлекаем данные формы вручную
    form_data = await request.form()
    print(f"Edit form keys: {list(form_data.keys())}")

    title = form_data.get("title")
    description = form_data.get("description")
    due_date = form_data.get("due_date")
    category_id = form_data.get("category_id")
    parent_id = form_data.get("parent_id")
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
            # Для администратора пропускаем проверку принадлежности категории
            if user.is_admin:
                category = db.query(Category).filter(Category.id == int(category_id)).first()
            else:
                category = db.query(Category).filter(Category.id == int(category_id), Category.owner_id == user.id).first()
            if not category:
                raise HTTPException(status_code=400, detail="Категория не найдена или не принадлежит вам")
            task.category_id = int(category_id)
    if parent_id is not None:
        if parent_id == "":
            task.parent_id = None
        else:
            # Для администратора пропускаем проверку принадлежности родительской задачи
            if user.is_admin:
                parent = db.query(Task).filter(Task.id == int(parent_id)).first()
            else:
                parent = db.query(Task).filter(Task.id == int(parent_id), Task.author_id == user.id).first()
            if not parent:
                raise HTTPException(status_code=400, detail="Родительская задача не найдена или не принадлежит вам")
            # Проверяем, что родитель не является потомком текущей задачи (можно пропустить для простоты)
            task.parent_id = int(parent_id)

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

@router.post("/task/{task_id}/assistant")
async def ask_assistant(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    files: list[UploadFile] = File([])
):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    form = await request.form()
    assistant_id = form.get("assistant_id")
    text = form.get("text")

    print(f"DEBUG: assistant_id={assistant_id}, text={text}")
    print(f"DEBUG: files received: {files}")
    if files:
        for i, f in enumerate(files):
            print(f"  - file[{i}]: filename={f.filename}, size={f.size if hasattr(f, 'size') else 'unknown'}")

    if not assistant_id or not text:
        raise HTTPException(status_code=400, detail="Не указан помощник или текст")

    assistant = db.query(Assistant).filter(Assistant.id == assistant_id).first()
    if not assistant:
        raise HTTPException(status_code=404, detail="Помощник не найден")

    # Проверяем доступ: публичный или владелец
    if not assistant.is_public and assistant.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к этому помощнику")

    # Создаем сообщение от пользователя (автор = пользователь, assistant_id = None)
    user_message = Message(
        text=text,
        author_id=user.id,
        assistant_id=None,
        task_id=task_id
    )
    db.add(user_message)
    db.flush()  # чтобы получить id сообщения

    # Обработка загруженного файла (берём первый файл, если есть)
    file_content_summary = ""
    uploaded_file_id = None
    file_record = None
    if files and len(files) > 0:
        file = files[0]
        if file.filename:
            upload_dir = "uploads/assistant_files"
            os.makedirs(upload_dir, exist_ok=True)
            # Генерируем уникальное имя файла
            ext = os.path.splitext(file.filename)[1]
            filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            # Создаем запись File
            file_record = FileModel(
                name=file.filename,
                path=file_path,
                url=f"/uploads/assistant_files/{filename}",
                message_id=user_message.id
            )
            db.add(file_record)
            db.flush()  # чтобы получить ID файла
            uploaded_file_id = file_record.id
            # Пытаемся прочитать содержимое файла для анализа
            try:
                success, content, error = file_reader.read_file_content(file_path)
                if success:
                    # Ограничим размер, чтобы не превысить лимит токенов
                    if len(content) > 5000:
                        summary = file_reader.summarize_text(content, max_length=5000)
                        file_content_summary = f"\n\nСодержимое файла '{file.filename}' (сокращённо):\n```\n{summary}\n```"
                    else:
                        file_content_summary = f"\n\nСодержимое файла '{file.filename}':\n```\n{content}\n```"
                else:
                    file_content_summary = f"\n\n[Прикреплён файл: {file.filename}, но не удалось прочитать содержимое: {error}]"
            except Exception as e:
                file_content_summary = f"\n\n[Прикреплён файл: {file.filename}, ошибка анализа: {e}]"
    else:
        file_content_summary = ""
    
    text_with_file = text + file_content_summary

    db.commit()

    # Подготавливаем контекст для GigaChat
    context = assistant.context or """Ты полезный помощник по управлению задачами. Отвечай подробно, развёрнуто, с примерами и пояснениями. Старайся давать максимально полные ответы, учитывая контекст задачи.

**Структура ответа:**
1. Начни с краткого резюме (1-2 предложения).
2. Затем дай детальное объяснение, разбивая его на логические разделы с заголовками (используй маркдаун заголовки уровня 2 или 3).
3. Если уместно, используй маркированные или нумерованные списки для перечисления пунктов.
4. Если вопрос связан с кодом, оформи код в блоки с указанием языка программирования.
5. Если вопрос требует рекомендаций, предложи несколько вариантов с плюсами и минусами.
6. Заверши ответ итогом или следующим шагом.

**Форматирование:**
- Используй жирный текст для выделения ключевых терминов.
- Используй курсив для акцентов.
- Для блоков кода применяй тройные обратные кавычки с указанием языка (например ```python).
- Для цитат используй символ >.

**Контекст задачи:**
Пользователь работает с системой управления задачами, где есть задачи, категории, сообщения, файлы. Помогай ему в организации, планировании, анализе, генерации контента.

Если пользователь задаёт вопрос, объясни свои рассуждения, предложи альтернативные варианты, дай рекомендации. Будь дружелюбным, но профессиональным."""
    functions = []
    try:
        if assistant.functions:
            functions = json.loads(assistant.functions)
            print(f"DEBUG: assistant.functions raw = {assistant.functions}")
    except Exception as e:
        print(f"DEBUG: error parsing assistant.functions: {e}")
        pass

    # Настройки из assistant.settings (JSON)
    temperature = 0.7
    max_tokens = 1024
    default_model = os.getenv("GIGACHAT_MODEL", "GigaChat-2-Lite")
    model = assistant.model or default_model
    if model == "GigaChat-Lite":
        model = "GigaChat-2-Lite"
    try:
        if assistant.settings:
            settings = json.loads(assistant.settings)
            temperature = settings.get("temperature", temperature)
            max_tokens = settings.get("max_tokens", max_tokens)
    except:
        pass

    # Формируем системное сообщение с контекстом
    messages = [
        {"role": "system", "content": context},
        {"role": "user", "content": text_with_file}
    ]

    # Отправляем запрос к GigaChat с параметрами помощника
    logger.info(f"Отправка запроса к GigaChat для помощника {assistant.id} ({assistant.name})")
    logger.info(f"Функции: {functions}")
    logger.info(f"Модель: {model}, температура: {temperature}, max_tokens: {max_tokens}")
    logger.info(f"Сообщения: {messages}")
    try:
        response = await gigachat.send_message(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            functions=functions if functions else None
        )
        logger.info(f"Получен ответ от GigaChat: {response}")
        message = response.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")
        function_call = message.get("function_call")
        logger.info(f"Извлечённый контент: '{content}', function_call: {function_call}")
        
        # Если есть function_call, обрабатываем его
        if function_call:
            func_name = function_call.get("name")
            func_args_str = function_call.get("arguments", "{}")
            try:
                func_args = json.loads(func_args_str)
            except:
                func_args = {}
            logger.info(f"Обнаружен вызов функции: {func_name} с аргументами {func_args}")
            
            # Вызов соответствующей функции
            if func_name == "generate_image":
                prompt = func_args.get("prompt", "красивое изображение")
                style = func_args.get("style", "digital_art")
                # Вызываем генерацию изображения
                try:
                    logger.info(f"Генерация изображения с промптом: {prompt}, стиль: {style}")
                    image_result = await gigachat.generate_image(prompt=prompt, style=style)
                    logger.info(f"Результат генерации изображения: {image_result}")
                    # Проверяем, является ли ответ демо-режимом
                    if image_result.get("demo"):
                        assistant_response = image_result.get("description", "Демо-режим: изображение не сгенерировано.")
                        logger.info("Генерация изображения в демо-режиме")
                    else:
                        # Предполагаем, что image_result содержит URL или идентификатор изображения
                        image_url = image_result.get("url") or image_result.get("image_url")
                        if image_url:
                            assistant_response = f"Сгенерировано изображение: {image_url}"
                            # Извлекаем имя файла из URL
                            filename = os.path.basename(image_url)
                            # Определяем физический путь (файл уже сохранён в /app/uploads/generated/)
                            # image_url имеет вид /uploads/generated/{filename}
                            if image_url.startswith("/uploads/generated/"):
                                file_path = f"/app{image_url}"
                            else:
                                # Если URL другой, предполагаем, что файл уже сохранён в GENERATED_IMAGES_DIR
                                file_path = os.path.join(GENERATED_IMAGES_DIR, filename)
                            # Создаем запись File
                            file_record = FileModel(
                                name=f"generated_image_{prompt[:20]}{os.path.splitext(filename)[1]}",
                                path=file_path,
                                url=image_url,
                                message_id=None  # будет установлено позже
                            )
                            db.add(file_record)
                            db.flush()
                            assistant_response += f"\n\n[Изображение сохранено: {file_record.name}]({file_record.url})"
                            logger.info(f"Изображение сохранено как {file_path}")
                        else:
                            assistant_response = f"Изображение сгенерировано, но URL не получен. Результат: {image_result}"
                            logger.warning(f"URL изображения отсутствует в ответе: {image_result}")
                except GigaChatAPIError as e:
                    assistant_response = f"Ошибка генерации изображения: {e}"
                    logger.error(f"GigaChatAPIError при генерации изображения: {e}")
                except Exception as e:
                    assistant_response = f"Неизвестная ошибка при генерации изображения: {e}"
                    logger.error(f"Неизвестная ошибка при генерации изображения: {e}")
            elif func_name == "generate_code":
                prompt = func_args.get("prompt", "пример кода")
                language = func_args.get("language", "python")
                try:
                    logger.info(f"Генерация кода с промптом: {prompt}, язык: {language}")
                    code_result = await gigachat.generate_code(prompt=prompt, language=language)
                    logger.info(f"Результат генерации кода: {code_result}")
                    code = code_result.get("code") or code_result.get("generated_code")
                    if code:
                        assistant_response = f"Сгенерирован код:\n```{language}\n{code}\n```"
                        # Сохраняем как файл
                        try:
                            ext = ".py" if language == "python" else ".txt"
                            filename = f"{uuid.uuid4()}{ext}"
                            file_path = os.path.join(GENERATED_CODE_DIR, filename)
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(code)
                            file_record = FileModel(
                                name=f"generated_code_{prompt[:20]}{ext}",
                                path=file_path,
                                url=f"/uploads/generated_code/{filename}",
                                message_id=None
                            )
                            db.add(file_record)
                            db.flush()
                            assistant_response += f"\n\n[Файл с кодом сохранён: {file_record.name}]({file_record.url})"
                            logger.info(f"Код сохранён как {file_path}")
                        except Exception as e:
                            logger.error(f"Ошибка при сохранении кода: {e}")
                    else:
                        assistant_response = f"Код сгенерирован, но не получен. Результат: {code_result}"
                        logger.warning(f"Код отсутствует в ответе: {code_result}")
                except GigaChatAPIError as e:
                    assistant_response = f"Ошибка генерации кода: {e}"
                    logger.error(f"GigaChatAPIError при генерации кода: {e}")
                except Exception as e:
                    assistant_response = f"Неизвестная ошибка при генерации кода: {e}"
                    logger.error(f"Неизвестная ошибка при генерации кода: {e}")
            elif func_name == "summarize_text":
                text = func_args.get("text", "")
                max_length = func_args.get("max_length", 500)
                try:
                    logger.info(f"Суммаризация текста, длина: {len(text)}, максимальная длина: {max_length}")
                    summary = file_reader.summarize_text(text, max_length=max_length)
                    assistant_response = f"Суммаризация текста (макс. {max_length} слов):\n\n{summary}"
                    logger.info(f"Суммаризация завершена, длина результата: {len(summary)}")
                except Exception as e:
                    assistant_response = f"Ошибка суммаризации текста: {e}"
                    logger.error(f"Ошибка суммаризации: {e}")
            elif func_name == "analyze_file_with_prompt":
                user_prompt = func_args.get("user_prompt", "")
                logger.info(f"DEBUG analyze_file_with_prompt: func_args={func_args}, uploaded_file_id={uploaded_file_id}")
                try:
                    # Игнорируем file_id из аргументов, используем только загруженный файл
                    if not uploaded_file_id:
                        assistant_response = "Не загружен файл для анализа. Пожалуйста, прикрепите файл к сообщению."
                        logger.warning("Попытка анализа файла без загруженного файла")
                    else:
                        file_id = uploaded_file_id
                        logger.info(f"Анализ загруженного файла с ID {file_id}, промпт: {user_prompt}")
                        # Найти файл в БД (используем другую переменную, чтобы не перезаписать file_record)
                        analyzed_file_record = db.query(FileModel).filter(FileModel.id == file_id).first()
                        if not analyzed_file_record:
                            assistant_response = f"Файл с ID {file_id} не найден в базе данных."
                            logger.warning(f"Файл не найден: {file_id}")
                        else:
                            # Проверить доступ: файл должен быть прикреплён к сообщению в текущей задаче или доступен пользователю
                            # Упрощённая проверка: файл принадлежит сообщению в текущей задаче
                            message = db.query(Message).filter(Message.id == analyzed_file_record.message_id).first()
                            if message and message.task_id == task_id:
                                # Чтение содержимого файла
                                success, content, error = file_reader.read_file_content(analyzed_file_record.path)
                                if not success:
                                    assistant_response = f"Не удалось прочитать файл: {error}"
                                    logger.error(f"Ошибка чтения файла: {error}")
                                else:
                                    # Ограничим размер содержимого
                                    if len(content) > 5000:
                                        content = content[:5000] + "... [обрезано]"
                                    # Отправить запрос к GigaChat для анализа
                                    analysis_messages = [
                                        {"role": "system", "content": """Ты помощник для анализа файлов. Пользователь предоставил файл и промт. Проанализируй содержимое файла подробно, дай развёрнутый ответ, выдели ключевые моменты, предложи рекомендации.

**Структура ответа:**
1. Краткое резюме файла (о чём он, основные темы).
2. Детальный анализ по пунктам промта.
3. Выводы и рекомендации (если уместно).
4. Если в файле есть данные (числа, таблицы), проанализируй их и сделай выводы.

**Форматирование:**
- Используй заголовки уровня 2 (##) для разделов.
- Используй маркированные списки для перечисления.
- Выделяй ключевые термины жирным.
- Для блоков кода или данных используй тройные обратные кавычки.

Будь максимально полезным и конкретным."""},
                                        {"role": "user", "content": f"Содержимое файла '{analyzed_file_record.name}':\n```\n{content}\n```\n\nПромт: {user_prompt}"}
                                    ]
                                    logger.debug(f"Анализ файла: отправляемые сообщения: {analysis_messages}")
                                    analysis_response = await gigachat.send_message(
                                        messages=analysis_messages,
                                        model=model,
                                        temperature=temperature,
                                        max_tokens=max_tokens
                                    )
                                    logger.debug(f"Полный ответ от GigaChat для анализа файла: {analysis_response}")
                                    analysis_content = analysis_response.get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа")
                                    assistant_response = f"Анализ файла '{analyzed_file_record.name}' по промту '{user_prompt}':\n\n{analysis_content}"
                                    logger.info(f"Анализ файла завершён, длина ответа: {len(analysis_content)}")
                            else:
                                assistant_response = f"Файл с ID {file_id} не принадлежит текущей задаче или недоступен."
                                logger.warning(f"Файл не принадлежит задаче: {file_id}")
                except Exception as e:
                    assistant_response = f"Ошибка анализа файла: {e}"
                    logger.error(f"Ошибка анализа файла: {e}")
            else:
                assistant_response = f"Помощник вызвал функцию '{func_name}' с аргументами {func_args}. Обработка не реализована."
                logger.warning(f"Неизвестная функция вызвана: {func_name}")
        else:
            # Нет function_call, используем обычный контент
            assistant_response = content if content and content.strip() != "" else "Нет ответа"
            logger.info(f"Извлечённый ответ помощника: '{assistant_response}'")
            # Если ответ пустой, используем сообщение об ошибке
            if not assistant_response or assistant_response.strip() == "":
                logger.warning("Пустой ответ от GigaChat")
                assistant_response = "К сожалению, GigaChat не смог сгенерировать ответ. Попробуйте переформулировать запрос или проверьте настройки API."
    except GigaChatAPIError as e:
        assistant_response = f"Ошибка при обращении к помощнику: {e}"
        logger.error(f"GigaChatAPIError: {e}")
    except Exception as e:
        assistant_response = f"Неизвестная ошибка: {e}"
        logger.error(f"Неизвестная ошибка: {e}")

    # Сохраняем ответ помощника как сообщение (автор = NULL, assistant_id = assistant.id)
    assistant_message = Message(
        text=assistant_response,
        author_id=None,
        assistant_id=assistant.id,
        task_id=task_id
    )
    db.add(assistant_message)
    db.flush()  # Получаем ID сообщения для прикрепления файлов

    # Привязываем сохранённые файлы к сообщению (если они были созданы)
    if 'file_record' in locals() and file_record:
        file_record.message_id = assistant_message.id

    db.commit()

    # Редирект обратно на страницу задачи
    return RedirectResponse(url=f"/task/{task_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/task/{task_id}/delete")
async def delete_task(request: Request, task_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")
    # Администратор может удалить любую задачу, обычный пользователь — только свою
    query = db.query(Task).filter(Task.id == task_id)
    if not user.is_admin:
        query = query.filter(Task.author_id == user.id)
    task = query.first()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена или нет доступа")
    parent_id = task.parent_id

    # Рекурсивная функция удаления задачи и её поддерева
    def delete_task_recursive(task_id: int):
        # Получаем задачу
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return
        # Удаляем сообщения и файлы этой задачи
        messages = db.query(Message).filter(Message.task_id == task_id).all()
        for msg in messages:
            files = db.query(FileModel).filter(FileModel.message_id == msg.id).all()
            for file in files:
                # Удаляем физический файл
                if os.path.exists(file.path):
                    os.remove(file.path)
                db.delete(file)
            db.delete(msg)
        # Удаляем превью
        if task.preview_image_path:
            old_path = task.preview_image_path.replace(PREVIEW_URL_PREFIX, UPLOAD_TASK_DIR + "/")
            if os.path.exists(old_path):
                os.remove(old_path)
        # Рекурсивно удаляем детей
        children = db.query(Task).filter(Task.parent_id == task_id).all()
        for child in children:
            delete_task_recursive(child.id)
        # Удаляем саму задачу
        db.delete(task)

    delete_task_recursive(task.id)
    db.commit()
    # Редирект на родительскую задачу, если она есть, иначе на список задач
    if parent_id:
        return RedirectResponse(url=f"/task/{parent_id}", status_code=status.HTTP_303_SEE_OTHER)
    else:
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