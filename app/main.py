import os
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from dotenv import load_dotenv

load_dotenv()

# Импорт моделей
from models import Base, User, Category, Task, Message, File
from database import engine, SessionLocal

# Импорт роутов
from routes import auth, users, categories, tasks, messages, files

# Создание таблиц
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Task Manager", docs_url=None, redoc_url=None)

# Монтирование статики
app.mount("/static", StaticFiles(directory="static"), name="static")

# Настройка шаблонов
templates = Jinja2Templates(directory="templates")

# Зависимость для сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Middleware для проверки сессии
@app.middleware("http")
async def session_middleware(request: Request, call_next):
    # Пропускаем статику
    if request.url.path.startswith("/static"):
        response = await call_next(request)
        return response
    
    session_token = request.cookies.get("session_token")
    user = None
    if session_token:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.session_token == session_token).first()
        finally:
            db.close()
    
    # Устанавливаем пользователя в состояние запроса, если найден
    if user:
        request.state.user = user
    else:
        # Если пользователь не авторизован и маршрут требует авторизации, перенаправляем
        if request.url.path not in ["/", "/login", "/register", "/logout"]:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    response = await call_next(request)
    return response

# Подключение роутов
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(tasks.router)
app.include_router(messages.router)
app.include_router(files.router)

# Главная страница
@app.get("/", response_class=HTMLResponse)
async def root(request: Request, db: Session = Depends(get_db)):
    # Проверяем сессию пользователя
    session_token = request.cookies.get("session_token")
    user = None
    if session_token:
        user = db.query(User).filter(User.session_token == session_token).first()
    
    # Активные задачи без родителя (если пользователь авторизован)
    tasks = []
    if user:
        tasks = db.query(Task).filter(
            Task.parent_id == None,
            Task.is_active == True,
            Task.author_id == user.id
        ).options(joinedload(Task.author), joinedload(Task.category)).all()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "tasks": tasks
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)