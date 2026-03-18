from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from models import Category
from database import SessionLocal
from .auth import get_db

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/categories", response_class=HTMLResponse)
async def categories_page(request: Request, db: Session = Depends(get_db)):
    categories = db.query(Category).all()
    return templates.TemplateResponse("categories.html", {"request": request, "categories": categories})

@router.get("/categories/create", response_class=HTMLResponse)
async def create_category_page(request: Request):
    return templates.TemplateResponse("category_create.html", {"request": request})

@router.post("/categories/create")
async def create_category(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    name = form.get("name")
    description = form.get("description")
    color = form.get("color", "#6a11cb")

    category = Category(name=name, description=description, color=color)
    db.add(category)
    db.commit()
    return RedirectResponse(url="/categories", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/categories/{category_id}/edit", response_class=HTMLResponse)
async def edit_category_page(request: Request, category_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    return templates.TemplateResponse("category_edit.html", {"request": request, "category": category})

@router.post("/categories/{category_id}/edit")
async def edit_category(request: Request, category_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    form = await request.form()
    category.name = form.get("name")
    category.description = form.get("description")
    category.color = form.get("color")
    db.commit()
    return RedirectResponse(url="/categories", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/categories/{category_id}/delete")
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    db.delete(category)
    db.commit()
    return RedirectResponse(url="/categories", status_code=status.HTTP_303_SEE_OTHER)