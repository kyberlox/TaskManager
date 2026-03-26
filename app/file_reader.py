import os
import pandas as pd
import pdfplumber
from docx import Document
import mimetypes
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    '.txt': 'text',
    '.pdf': 'pdf',
    '.docx': 'docx',
    '.xlsx': 'excel',
    '.xls': 'excel',
    '.ods': 'excel',
    '.csv': 'csv',
    '.json': 'json',
    '.xml': 'xml',
}

def get_file_type(filename: str) -> Optional[str]:
    """Определить тип файла по расширению."""
    ext = os.path.splitext(filename)[1].lower()
    return SUPPORTED_EXTENSIONS.get(ext)

def read_text_file(file_path: str) -> str:
    """Чтение текстового файла (txt, csv, json, xml)."""
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        return f.read()

def read_pdf(file_path: str) -> str:
    """Извлечение текста из PDF с помощью pdfplumber."""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.error(f"Ошибка чтения PDF {file_path}: {e}")
        raise
    return text.strip()

def read_docx(file_path: str) -> str:
    """Извлечение текста из DOCX."""
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return "\n".join(full_text)

def read_excel(file_path: str) -> str:
    """Чтение Excel/ODS файла и преобразование в текстовое представление."""
    try:
        # Определяем движок по расширению
        if file_path.endswith('.ods'):
            df = pd.read_excel(file_path, engine='odf')
        else:
            df = pd.read_excel(file_path)
        # Преобразуем в строку (например, CSV)
        return df.to_string(index=False)
    except Exception as e:
        logger.error(f"Ошибка чтения Excel {file_path}: {e}")
        raise

def read_file_content(file_path: str) -> Tuple[bool, str, Optional[str]]:
    """
    Чтение содержимого файла любого поддерживаемого формата.
    Возвращает (успех, текст, ошибка).
    """
    if not os.path.exists(file_path):
        return False, "", "Файл не существует"
    filename = os.path.basename(file_path)
    file_type = get_file_type(filename)
    if not file_type:
        return False, "", f"Неподдерживаемый формат файла {filename}"
    try:
        if file_type == 'text':
            content = read_text_file(file_path)
        elif file_type == 'pdf':
            content = read_pdf(file_path)
        elif file_type == 'docx':
            content = read_docx(file_path)
        elif file_type == 'excel':
            content = read_excel(file_path)
        elif file_type == 'csv':
            # CSV можно читать как текст или через pandas
            content = read_text_file(file_path)
        else:
            return False, "", f"Тип {file_type} не реализован"
        return True, content, None
    except Exception as e:
        logger.error(f"Ошибка при чтении файла {file_path}: {e}")
        return False, "", str(e)

def summarize_text(text: str, max_length: int = 500) -> str:
    """Создание краткого содержания текста (упрощённая версия)."""
    # В реальности здесь можно использовать LLM
    # Пока просто обрезаем
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."

def analyze_text_with_prompt(text: str, prompt: str) -> str:
    """Анализ текста с помощью промта (заглушка, должна вызывать LLM)."""
    # TODO: интеграция с GigaChat
    return f"Анализ по промту '{prompt}': текст длиной {len(text)} символов."