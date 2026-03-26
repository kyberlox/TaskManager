from fastapi import APIRouter, Request, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import json
import os
from uuid import uuid4
import markdown

from models import Assistant, User, Message
from database import SessionLocal
from .auth import get_db, get_current_user
import assistant_functions

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["markdown"] = lambda text: markdown.markdown(text, extensions=["extra", "codehilite"])

@router.get("/assistants", response_class=HTMLResponse)
async def assistants_page(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Показываем только помощников текущего пользователя (или всех, если админ)
    if current_user.is_admin:
        assistants = db.query(Assistant).all()
    else:
        assistants = db.query(Assistant).filter(Assistant.owner_id == current_user.id).all()
    return templates.TemplateResponse("assistants/assistants.html", {"request": request, "assistants": assistants, "user": current_user})

@router.get("/assistants/create", response_class=HTMLResponse)
async def create_assistant_page(request: Request, current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Только администратор может создавать помощников")
    return templates.TemplateResponse("assistants/assistant_create.html", {
        "request": request,
        "user": current_user,
        "all_functions": assistant_functions.ALL_FUNCTIONS,
        "all_capabilities": assistant_functions.CAPABILITIES,
    })

@router.post("/assistants/create")
async def create_assistant(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    name: str = Form(...),
    description: str = Form(""),
    context: str = Form(""),
    is_public: bool = Form(False),
    functions: str = Form("[]"),
    settings: str = Form("{}"),
    capabilities: str = Form("[]"),
    model: str = Form("GigaChat-Lite"),
    avatar: UploadFile = File(None),
    function_ids: str = Form(""),
    capability_ids: str = Form("")
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Только администратор может создавать помощников")

    # Валидация JSON (для обратной совместимости)
    try:
        functions_obj = json.loads(functions)
    except json.JSONDecodeError:
        functions_obj = []
    try:
        settings_obj = json.loads(settings)
    except json.JSONDecodeError:
        settings_obj = {}
    try:
        capabilities_obj = json.loads(capabilities)
    except json.JSONDecodeError:
        capabilities_obj = []

    # Преобразование строк function_ids и capability_ids в массивы
    function_ids_list = []
    if function_ids:
        # Ожидается строка с разделителями запятыми или пробелами
        import re
        function_ids_list = [fid.strip() for fid in re.split(r'[, ]+', function_ids) if fid.strip()]
    capability_ids_list = []
    if capability_ids:
        import re
        capability_ids_list = [cid.strip() for cid in re.split(r'[, ]+', capability_ids) if cid.strip()]

    # Если переданы function_ids, обновляем functions_obj на основе выбранных функций
    if function_ids_list:
        functions_obj = []
        for fid in function_ids_list:
            func = assistant_functions.get_function_by_id(fid)
            if func:
                functions_obj.append({
                    "name": func["name"],
                    "description": func["description"],
                    "parameters": func["parameters"]
                })

    # Если переданы capability_ids, обновляем capabilities_obj
    if capability_ids_list:
        capabilities_obj = capability_ids_list

    # Обработка загрузки аватарки
    avatar_path = None
    if avatar and avatar.filename:
        upload_dir = "uploads/avatars"
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(avatar.filename)[1]
        filename = f"{uuid4()}{ext}"
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            content = await avatar.read()
            f.write(content)
        avatar_path = f"/uploads/avatars/{filename}"

    assistant = Assistant(
        name=name,
        description=description,
        context=context,
        avatar_path=avatar_path,
        owner_id=current_user.id,
        is_public=is_public,
        functions=json.dumps(functions_obj, ensure_ascii=False),
        settings=json.dumps(settings_obj, ensure_ascii=False),
        capabilities=json.dumps(capabilities_obj, ensure_ascii=False),
        model=model,
        function_ids=function_ids_list,
        capability_ids=capability_ids_list
    )
    db.add(assistant)
    db.commit()
    return RedirectResponse(url="/assistants", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/assistants/{assistant_id}/edit", response_class=HTMLResponse)
async def edit_assistant_page(
    request: Request,
    assistant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    assistant = db.query(Assistant).filter(Assistant.id == assistant_id).first()
    if not assistant:
        raise HTTPException(status_code=404, detail="Помощник не найден")
    # Проверка прав: только владелец или админ
    if assistant.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Нет прав на редактирование")
    # Получаем выбранные ID функций и возможностей
    selected_function_ids = assistant.function_ids or []
    selected_capability_ids = assistant.capability_ids or []
    return templates.TemplateResponse("assistants/assistant_edit.html", {
        "request": request,
        "assistant": assistant,
        "user": current_user,
        "all_functions": assistant_functions.ALL_FUNCTIONS,
        "all_capabilities": assistant_functions.CAPABILITIES,
        "selected_function_ids": selected_function_ids,
        "selected_capability_ids": selected_capability_ids,
    })

@router.post("/assistants/{assistant_id}/edit")
async def edit_assistant(
    request: Request,
    assistant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    avatar: UploadFile = File(None)
):
    assistant = db.query(Assistant).filter(Assistant.id == assistant_id).first()
    if not assistant:
        raise HTTPException(status_code=404, detail="Помощник не найден")
    if assistant.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Нет прав на редактирование")

    form = await request.form()
    if "name" in form:
        assistant.name = form.get("name")
    if "description" in form:
        assistant.description = form.get("description")
    if "context" in form:
        assistant.context = form.get("context")
    if "is_public" in form:
        assistant.is_public = form.get("is_public") == "on"
    if "functions" in form:
        functions_str = form.get("functions", "[]")
        try:
            assistant.functions = json.dumps(json.loads(functions_str), ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    if "settings" in form:
        settings_str = form.get("settings", "{}")
        try:
            assistant.settings = json.dumps(json.loads(settings_str), ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    if "capabilities" in form:
        capabilities_str = form.get("capabilities", "[]")
        try:
            assistant.capabilities = json.dumps(json.loads(capabilities_str), ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    if "model" in form:
        assistant.model = form.get("model", "GigaChat-Lite")

    # Обработка новых полей function_ids и capability_ids
    if "function_ids" in form:
        function_ids_str = form.get("function_ids", "")
        import re
        function_ids_list = [fid.strip() for fid in re.split(r'[, ]+', function_ids_str) if fid.strip()]
        assistant.function_ids = function_ids_list
        # Обновляем functions на основе выбранных ID
        functions_obj = []
        for fid in function_ids_list:
            func = assistant_functions.get_function_by_id(fid)
            if func:
                functions_obj.append({
                    "name": func["name"],
                    "description": func["description"],
                    "parameters": func["parameters"]
                })
        assistant.functions = json.dumps(functions_obj, ensure_ascii=False)

    if "capability_ids" in form:
        capability_ids_str = form.get("capability_ids", "")
        import re
        capability_ids_list = [cid.strip() for cid in re.split(r'[, ]+', capability_ids_str) if cid.strip()]
        assistant.capability_ids = capability_ids_list
        assistant.capabilities = json.dumps(capability_ids_list, ensure_ascii=False)

    # Загрузка новой аватарки (если предоставлена)
    if avatar and avatar.filename:
        upload_dir = "uploads/avatars"
        os.makedirs(upload_dir, exist_ok=True)
        ext = os.path.splitext(avatar.filename)[1]
        filename = f"{uuid4()}{ext}"
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            content = await avatar.read()
            f.write(content)
        # Удалить старую аватарку, если есть
        if assistant.avatar_path and os.path.exists(assistant.avatar_path.lstrip("/")):
            try:
                os.remove(assistant.avatar_path.lstrip("/"))
            except:
                pass
        assistant.avatar_path = f"/uploads/avatars/{filename}"

    db.commit()
    return RedirectResponse(url="/assistants", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/assistants/{assistant_id}/delete")
async def delete_assistant(
    assistant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    assistant = db.query(Assistant).filter(Assistant.id == assistant_id).first()
    if not assistant:
        raise HTTPException(status_code=404, detail="Помощник не найден")
    if assistant.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Нет прав на удаление")
    # Обнулить assistant_id в сообщениях, чтобы не нарушать целостность
    db.query(Message).filter(Message.assistant_id == assistant.id).update({"assistant_id": None})
    # Удалить аватарку
    if assistant.avatar_path and os.path.exists(assistant.avatar_path.lstrip("/")):
        try:
            os.remove(assistant.avatar_path.lstrip("/"))
        except:
            pass
    db.delete(assistant)
    db.commit()
    return RedirectResponse(url="/assistants", status_code=status.HTTP_303_SEE_OTHER)