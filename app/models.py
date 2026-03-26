from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, ARRAY
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    login = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    avatar_path = Column(String(500), nullable=True)
    session_token = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tasks = relationship("Task", back_populates="author")
    messages = relationship("Message", back_populates="author")

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), default="#6a11cb")  # hex цвет
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, default=1)  # временно default=1

    tasks = relationship("Task", back_populates="category")
    owner = relationship("User")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(DateTime, nullable=True)
    reminders = Column(ARRAY(DateTime), nullable=True)  # список напоминаний
    preview_image_path = Column(String(500), nullable=True)
    parent_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Связи
    author = relationship("User", back_populates="tasks")
    category = relationship("Category", back_populates="tasks")
    parent = relationship("Task", remote_side=[id], backref="children")
    messages = relationship("Message", back_populates="task")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # может быть NULL если от помощника
    assistant_id = Column(Integer, ForeignKey("assistants.id"), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = relationship("User", back_populates="messages")
    assistant = relationship("Assistant")
    task = relationship("Task", back_populates="messages")
    files = relationship("File", back_populates="message")

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    path = Column(String(500), nullable=False)
    url = Column(String(500), nullable=False)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    message = relationship("Message", back_populates="files")

class Assistant(Base):
    __tablename__ = "assistants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    context = Column(Text, nullable=True)  # системный промпт/контекст
    avatar_path = Column(String(500), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_public = Column(Boolean, default=False)
    functions = Column(Text, nullable=True)  # JSON список функций (для обратной совместимости)
    function_ids = Column(ARRAY(String), nullable=True, default=[])  # массив ID выбранных функций
    settings = Column(Text, nullable=True)   # JSON настройки (лимиты, тарифы)
    capabilities = Column(Text, nullable=True)  # JSON список возможностей (для обратной совместимости)
    capability_ids = Column(ARRAY(String), nullable=True, default=[])  # массив ID возможностей
    model = Column(String(100), nullable=True, default="GigaChat-Lite")  # модель GigaChat
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User")