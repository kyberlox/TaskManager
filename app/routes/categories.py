from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
import markdown

from models import Category, User
from database import SessionLocal
from .auth import get_db, get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["markdown"] = lambda text: markdown.markdown(text, extensions=["extra", "codehilite"])

@router.get("/categories", response_class=HTMLResponse)
async def categories_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Все пользователи (включая администраторов) видят только свои категории
    categories = db.query(Category).filter(Category.owner_id == user.id).options(joinedload(Category.owner)).all()
    return templates.TemplateResponse("categories.html", {"request": request, "categories": categories, "user": user})

@router.get("/categories/create", response_class=HTMLResponse)
async def create_category_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("category_create.html", {"request": request, "user": user})

@router.post("/categories/create")
async def create_category(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    form = await request.form()
    name = form.get("name")
    description = form.get("description")
    color = form.get("color", "#6a11cb")

    category = Category(name=name, description=description, color=color, owner_id=user.id)
    db.add(category)
    db.commit()
    return RedirectResponse(url="/categories", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/categories/{category_id}/edit", response_class=HTMLResponse)
async def edit_category_page(request: Request, category_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Все пользователи (включая администраторов) могут редактировать только свои категории
    category = db.query(Category).filter(Category.id == category_id, Category.owner_id == user.id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена или нет доступа")
    return templates.TemplateResponse("category_edit.html", {"request": request, "category": category, "user": user})

@router.post("/categories/{category_id}/edit")
async def edit_category(request: Request, category_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    # Все пользователи (включая администраторов) могут редактировать только свои категории
    category = db.query(Category).filter(Category.id == category_id, Category.owner_id == user.id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена или нет доступа")

    form = await request.form()
    category.name = form.get("name")
    category.description = form.get("description")
    category.color = form.get("color")
    db.commit()
    return RedirectResponse(url="/categories", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/categories/{category_id}/delete")
async def delete_category(request: Request, category_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    # Все пользователи (включая администраторов) могут удалять только свои категории
    category = db.query(Category).filter(Category.id == category_id, Category.owner_id == user.id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена или нет доступа")
    db.delete(category)
    db.commit()
    return RedirectResponse(url="/categories", status_code=status.HTTP_303_SEE_OTHER)