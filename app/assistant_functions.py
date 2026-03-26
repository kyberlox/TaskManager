"""
Единый файл с описанием всех доступных функций помощников.

Содержит константы и функции для использования в шаблонах и роутах.
"""

import json
from typing import Dict, List, Any

# ============================================================================
# Список всех доступных функций (для выбора в интерфейсе)
# ============================================================================

ALL_FUNCTIONS = [
    {
        "id": "read_file_and_describe",
        "name": "read_file_and_describe",
        "title": "Чтение файла (краткое описание)",
        "description": "Прочитать содержимое текстового файла и предоставить краткое описание",
        "category": "file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "integer",
                    "description": "ID файла в системе"
                }
            },
            "required": ["file_id"]
        }
    },
    {
        "id": "analyze_file_with_prompt",
        "name": "analyze_file_with_prompt",
        "title": "Анализ файла с промтом",
        "description": "Проанализировать содержимое файла с использованием пользовательского промта",
        "category": "file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "integer",
                    "description": "ID файла в системе"
                },
                "user_prompt": {
                    "type": "string",
                    "description": "Промт от пользователя, задающий вопрос или задачу для анализа файла"
                }
            },
            "required": ["file_id", "user_prompt"]
        }
    },
    {
        "id": "generate_image",
        "name": "generate_image",
        "title": "Генерация изображения",
        "description": "Сгенерировать изображение по текстовому описанию",
        "category": "gigachat",
        "capability": "image_generation",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Детальное описание изображения для генерации"
                },
                "style": {
                    "type": "string",
                    "description": "Стиль изображения (реализм, аниме, цифровое искусство)",
                    "enum": ["realistic", "anime", "digital_art", "watercolor"]
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "id": "generate_code",
        "name": "generate_code",
        "title": "Генерация кода",
        "description": "Сгенерировать код на указанном языке программирования по описанию задачи",
        "category": "gigachat",
        "capability": "code_generation",
        "parameters": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "description": "Язык программирования определи из контекста (если не получилось,  то у молчанию -python)"
                },
                "task": {
                    "type": "string",
                    "description": "Описание задачи для которой нужен код"
                },
                "framework": {
                    "type": "string",
                    "description": "Фреймворк (опционально)"
                }
            },
            "required": ["language", "task"]
        }
    },
    {
        "id": "summarize_text",
        "name": "summarize_text",
        "title": "Суммаризация текста",
        "description": "Суммаризировать текст, выделяя ключевые моменты",
        "category": "text",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Текст для суммаризации"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Максимальная длина результата в словах"
                }
            },
            "required": ["text"]
        }
    },
    {
        "id": "translate_text",
        "name": "translate_text",
        "title": "Перевод текста",
        "description": "Перевести текст на указанный язык",
        "category": "text",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Текст для перевода"
                },
                "target_language": {
                    "type": "string",
                    "description": "Целевой язык (например, 'en', 'fr', 'de')"
                }
            },
            "required": ["text", "target_language"]
        }
    },
    {
        "id": "get_weather",
        "name": "get_weather",
        "title": "Получить погоду",
        "description": "Получить текущую погоду в указанном городе",
        "category": "external",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Название города"
                }
            },
            "required": ["city"]
        }
    },
    {
        "id": "calculate",
        "name": "calculate",
        "title": "Калькулятор",
        "description": "Выполнить математическое вычисление",
        "category": "utility",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Математическое выражение (например, '2+2*3')"
                }
            },
            "required": ["expression"]
        }
    },
]

# ============================================================================
# Функции для работы с функциями
# ============================================================================

def get_function_by_id(func_id: str) -> Dict[str, Any]:
    """Найти функцию по ID."""
    for func in ALL_FUNCTIONS:
        if func["id"] == func_id:
            return func
    return None

def get_functions_by_category(category: str) -> List[Dict[str, Any]]:
    """Получить список функций по категории."""
    return [func for func in ALL_FUNCTIONS if func.get("category") == category]

def get_all_categories() -> List[str]:
    """Получить список уникальных категорий."""
    categories = set()
    for func in ALL_FUNCTIONS:
        categories.add(func.get("category", "other"))
    return sorted(list(categories))

def function_ids_to_json(func_ids: List[str]) -> str:
    """Преобразовать список ID функций в JSON строку (для хранения в БД)."""
    functions = []
    for fid in func_ids:
        func = get_function_by_id(fid)
        if func:
            # Копируем только необходимые поля для хранения
            functions.append({
                "name": func["name"],
                "description": func["description"],
                "parameters": func["parameters"]
            })
    return json.dumps(functions, ensure_ascii=False, indent=2)

def json_to_function_ids(json_str: str) -> List[str]:
    """Извлечь ID функций из JSON строки."""
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return []
    ids = []
    for item in data:
        name = item.get("name")
        if name:
            # Найти функцию по name
            for func in ALL_FUNCTIONS:
                if func["name"] == name:
                    ids.append(func["id"])
                    break
    return ids

# ============================================================================
# Возможности (capabilities) связанные с функциями
# ============================================================================

CAPABILITIES = [
    {"id": "text", "title": "Текстовый диалог", "description": "Обычный текстовый диалог без специальных функций"},
    {"id": "function_calling", "title": "Вызов функций", "description": "Поддержка вызова внешних функций (function calling)"},
    {"id": "code_generation", "title": "Генерация кода", "description": "Генерация кода на различных языках программирования"},
    {"id": "image_generation", "title": "Генерация изображений", "description": "Генерация изображений по текстовому описанию"},
    {"id": "file_analysis", "title": "Анализ файлов", "description": "Чтение и анализ содержимого файлов (текст, PDF, Excel и др.)"},
]

def get_capability_by_id(cap_id: str) -> Dict[str, Any]:
    """Найти возможность по ID."""
    for cap in CAPABILITIES:
        if cap["id"] == cap_id:
            return cap
    return None

# ============================================================================
# Экспорт для использования в шаблонах
# ============================================================================

if __name__ == "__main__":
    # Пример использования
    print("Все функции:", len(ALL_FUNCTIONS))
    for func in ALL_FUNCTIONS:
        print(f"- {func['title']} ({func['id']})")