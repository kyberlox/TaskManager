import sys
sys.path.append('.')

from sqlalchemy import text
from database import SessionLocal

def migrate():
    db = SessionLocal()
    try:
        # Проверяем наличие столбца owner_id в categories
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'categories' AND column_name = 'owner_id'
        """))
        if not result.fetchone():
            print("Добавляем столбец owner_id в таблицу categories...")
            db.execute(text("ALTER TABLE categories ADD COLUMN owner_id INTEGER NOT NULL DEFAULT 1 REFERENCES users(id)"))
            print("Столбец owner_id добавлен.")
        else:
            print("Столбец owner_id уже существует.")

        # Проверяем наличие столбца assistant_id в messages
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'messages' AND column_name = 'assistant_id'
        """))
        if not result.fetchone():
            print("Добавляем столбец assistant_id в таблицу messages...")
            db.execute(text("ALTER TABLE messages ADD COLUMN assistant_id INTEGER REFERENCES assistants(id)"))
            print("Столбец assistant_id добавлен.")
        else:
            print("Столбец assistant_id уже существует.")

        # Проверяем наличие столбца author_id в messages (должен быть nullable)
        result = db.execute(text("""
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_name = 'messages' AND column_name = 'author_id'
        """))
        row = result.fetchone()
        if row and row[0] == 'NO':
            print("Изменяем столбец author_id в messages на NULLABLE...")
            db.execute(text("ALTER TABLE messages ALTER COLUMN author_id DROP NOT NULL"))
            print("Столбец author_id изменён на NULLABLE.")
        else:
            print("Столбец author_id уже NULLABLE.")

        # Проверяем наличие столбца created_at в files
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'files' AND column_name = 'created_at'
        """))
        if not result.fetchone():
            print("Добавляем столбец created_at в таблицу files...")
            db.execute(text("ALTER TABLE files ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
            print("Столбец created_at добавлен.")
        else:
            print("Столбец created_at уже существует.")

        # Проверяем наличие столбца updated_at в files
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'files' AND column_name = 'updated_at'
        """))
        if not result.fetchone():
            print("Добавляем столбец updated_at в таблицу files...")
            db.execute(text("ALTER TABLE files ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
            print("Столбец updated_at добавлен.")
        else:
            print("Столбец updated_at уже существует.")

        # Проверяем наличие столбца capabilities в assistants
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'assistants' AND column_name = 'capabilities'
        """))
        if not result.fetchone():
            print("Добавляем столбец capabilities в таблицу assistants...")
            db.execute(text("ALTER TABLE assistants ADD COLUMN capabilities TEXT"))
            print("Столбец capabilities добавлен.")
        else:
            print("Столбец capabilities уже существует.")

        # Проверяем наличие столбца model в assistants
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'assistants' AND column_name = 'model'
        """))
        if not result.fetchone():
            print("Добавляем столбец model в таблицу assistants...")
            db.execute(text("ALTER TABLE assistants ADD COLUMN model VARCHAR(100) DEFAULT 'GigaChat-Lite'"))
            print("Столбец model добавлен.")
        else:
            print("Столбец model уже существует.")

        # Проверяем наличие столбца function_ids в assistants
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'assistants' AND column_name = 'function_ids'
        """))
        if not result.fetchone():
            print("Добавляем столбец function_ids в таблицу assistants...")
            db.execute(text("ALTER TABLE assistants ADD COLUMN function_ids TEXT[] DEFAULT '{}'"))
            print("Столбец function_ids добавлен.")
        else:
            print("Столбец function_ids уже существует.")

        # Проверяем наличие столбца capability_ids в assistants
        result = db.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'assistants' AND column_name = 'capability_ids'
        """))
        if not result.fetchone():
            print("Добавляем столбец capability_ids в таблицу assistants...")
            db.execute(text("ALTER TABLE assistants ADD COLUMN capability_ids TEXT[] DEFAULT '{}'"))
            print("Столбец capability_ids добавлен.")
        else:
            print("Столбец capability_ids уже существует.")

        db.commit()
        print("Миграция успешно завершена.")
    except Exception as e:
        db.rollback()
        print(f"Ошибка миграции: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    migrate()