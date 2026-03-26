import os
import json
import logging
import base64
import httpx
from typing import Dict, List, Optional, Any
try:
    from bs4 import BeautifulSoup
    HAS_BEAUTIFULSOUP = True
except ImportError:
    BeautifulSoup = None
    HAS_BEAUTIFULSOUP = False

logger = logging.getLogger(__name__)

# Проверяем наличие официального SDK gigachat
try:
    from gigachat import GigaChat
    from gigachat.models import Chat, Messages, MessagesRole, Function, FunctionParameters
    from gigachat.exceptions import (
        GigaChatException,
        AuthenticationError,
        RateLimitError,
        BadRequestError,
        ForbiddenError,
        NotFoundError,
        RequestEntityTooLargeError,
        ServerError,
    )
    HAS_GIGACHAT_SDK = True
except ImportError:
    GigaChat = None
    Chat = None
    Messages = None
    MessagesRole = None
    Function = None
    FunctionParameters = None
    GigaChatException = Exception
    AuthenticationError = Exception
    RateLimitError = Exception
    BadRequestError = Exception
    ForbiddenError = Exception
    NotFoundError = Exception
    RequestEntityTooLargeError = Exception
    ServerError = Exception
    HAS_GIGACHAT_SDK = False
    logger.warning("Официальный SDK gigachat не установлен, работа с GigaChat невозможна")

class GigaChatAPIError(Exception):
    """Базовое исключение для ошибок GigaChat API."""
    pass


class GigaChatAPI:
    """Клиент для работы с GigaChat API, использующий официальный SDK."""

    def __init__(self):
        self.client_id = os.getenv("GIGACHAT_CLIENT_ID")
        self.scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
        self.auth_key = os.getenv("GIGACHAT_AUTHORIZATION_KEY")
        model = os.getenv("GIGACHAT_MODEL", "GigaChat-2-Lite")
        # if model in ("GigaChat-Lite", "GigaChat Lite"):
        #     model = "GigaChat"
        self.model = model
        self.sdk_client = None

        # Если api_url пустой, используем значение по умолчанию
        # if not self.api_url:
        #     self.api_url = "https://gigachat.devices.sberbank.ru/api/v1"
        #     logger.warning(f"GIGACHAT_API_URL не установлен, используется значение по умолчанию: {self.api_url}")

        # Устанавливаем переменные окружения для SDK
        # if self.auth_url:
        #     os.environ["GIGACHAT_AUTH_URL"] = self.auth_url
        # if self.api_url:
        #     os.environ["GIGACHAT_API_URL"] = self.api_url

        # Инициализация официального SDK (как в примере пользователя)
        if HAS_GIGACHAT_SDK and self.auth_key:
            try:
                self.sdk_client = GigaChat(
                    credentials=self.auth_key,
                    verify_ssl_certs=False,
                    scope=self.scope,
                    timeout=60.0,
                    model=self.model,
                )
                logger.info("Инициализирован официальный клиент GigaChat SDK с параметрами из примера")
                # Получаем токен для проверки
                self.token = self.sdk_client.get_token()
                self.access_token = self.token.access_token
                logger.info(f"Токен получен, истекает в {self.token.expires_at}")
            except Exception as e:
                logger.error(f"Ошибка инициализации официального SDK GigaChat: {e}")
                self.sdk_client = None
        else:
            logger.warning("Официальный SDK GigaChat недоступен или отсутствует ключ авторизации")

        # Демо-режим включен, если SDK недоступен
        self.demo_mode = self.sdk_client is None
        if self.demo_mode:
            logger.info("Демо-режим включен (SDK недоступен или отсутствует ключ авторизации)")
        else:
            logger.info("Используется официальный SDK GigaChat")


    def _demo_response(self, messages: List[Dict[str, str]], functions: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Создать демо-ответ на основе последнего сообщения пользователя."""
        # Извлекаем последнее сообщение пользователя
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        if not user_message:
            user_message = "Привет"

        # Определяем тему запроса
        lower = user_message.lower()
        demo_text = ""
        if any(word in lower for word in ["привет", "hello", "здравствуй"]):
            demo_text = "Привет! Я ваш виртуальный помощник. В демо-режиме я могу отвечать на вопросы, но для полного функционала настройте GigaChat API."
        elif any(word in lower for word in ["задача", "task", "дело"]):
            demo_text = "Я вижу, вы спрашиваете о задачах. В системе управления задачами вы можете создавать, редактировать, удалять задачи, назначать категории и сроки. Рекомендую разбить крупные задачи на подзадачи и установить напоминания."
        elif any(word in lower for word in ["категория", "category"]):
            demo_text = "Категории помогают организовать задачи по темам или проектам. Вы можете назначить цвет каждой категории для визуального различия в календаре."
        elif any(word in lower for word in ["файл", "file", "документ"]):
            demo_text = "Вы можете прикреплять файлы к сообщениям. Помощник может анализировать текстовые файлы, изображения и таблицы. В демо-режиме анализ файлов не выполняется, но при настройке GigaChat API вы получите полную функциональность."
        elif any(word in lower for word in ["код", "code", "программа"]):
            demo_text = "Для генерации кода используйте функцию 'generate_code'. В демо-режиме я могу предложить пример кода на Python:\n\n```python\ndef hello_world():\n    print('Hello, World!')\n```"
        elif any(word in lower for word in ["изображение", "image", "картинка"]):
            demo_text = "Для генерации изображений используйте функцию 'generate_image'. В демо-режиме я могу описать, как бы выглядело изображение по вашему запросу."
        else:
            demo_text = f"Вы написали: '{user_message}'. Это демо-ответ, так как GigaChat API не настроен. Для получения реальных ответов настройте переменные окружения GIGACHAT_CLIENT_ID и GIGACHAT_AUTHORIZATION_KEY."

        # Если есть функции, можно сгенерировать function_call для демо
        if functions:
            # Проверяем, есть ли среди функций generate_image или generate_code
            func_names = [f.get("name") for f in functions if f.get("name")]
            if "generate_image" in func_names and any(word in lower for word in ["изображение", "image", "картинка", "нарисуй"]):
                demo_text += "\n\n(Демо: функция generate_image была бы вызвана с промптом 'красивое изображение')"
                # Возвращаем демо function_call
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "function_call": {
                                    "name": "generate_image",
                                    "arguments": json.dumps({"prompt": "красивое изображение", "style": "digital_art"})
                                }
                            }
                        }
                    ]
                }
            elif "generate_code" in func_names and any(word in lower for word in ["код", "code", "программа", "сгенерируй код"]):
                demo_text += "\n\n(Демо: функция generate_code была бы вызвана с промптом 'функция сложения двух чисел')"
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "function_call": {
                                    "name": "generate_code",
                                    "arguments": json.dumps({"prompt": "функция сложения двух чисел", "language": "python"})
                                }
                            }
                        }
                    ]
                }

        return {
            "choices": [
                {
                    "message": {
                        "content": demo_text,
                        "role": "assistant"
                    }
                }
            ]
        }

    async def send_message(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        functions: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Отправить сообщение в GigaChat и получить ответ."""
        if model is None:
            model = self.model

        logger.info(f"Отправка сообщения в GigaChat, модель {model}, количество сообщений: {len(messages)}")
        if functions:
            logger.info(f"Передаваемые функции: {json.dumps(functions, ensure_ascii=False, indent=2)}")

        # Попытка использовать официальный SDK
        if self.sdk_client and HAS_GIGACHAT_SDK and not self.demo_mode:
            logger.info("Используется официальный SDK GigaChat")
            try:
                # Преобразуем сообщения в формат SDK
                sdk_messages = []
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        sdk_role = MessagesRole.USER
                    elif role == "assistant":
                        sdk_role = MessagesRole.ASSISTANT
                    elif role == "system":
                        sdk_role = MessagesRole.SYSTEM
                    else:
                        sdk_role = MessagesRole.USER
                    sdk_messages.append(Messages(role=sdk_role, content=content))

                # Поддержка функций (function calling) в SDK
                chat_params = {
                    "model": model,
                    "messages": sdk_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream,
                }
                if functions:
                    chat_params["functions"] = functions
                    chat_params["function_call"] = "auto"
                    logger.debug(f"Параметры чата с функциями: {chat_params}")

                chat = Chat(**chat_params)
                logger.debug(f"Отправка запроса через SDK: {chat}")
                response = await self.sdk_client.achat(chat)
                logger.debug(f"Получен ответ SDK: {response}")
                # Преобразуем ответ в совместимый формат
                message = response.choices[0].message
                result_message = {
                    "content": message.content,
                    "role": message.role,
                }
                # Если есть function_call, добавляем его
                if hasattr(message, 'function_call') and message.function_call:
                    func = message.function_call
                    func_name = getattr(func, 'name', None)
                    func_args = getattr(func, 'arguments', None)
                    if func_args and isinstance(func_args, dict):
                        func_args_str = json.dumps(func_args, ensure_ascii=False)
                    elif func_args and isinstance(func_args, str):
                        func_args_str = func_args
                    else:
                        func_args_str = "{}"
                    result_message["function_call"] = {
                        "name": func_name,
                        "arguments": func_args_str
                    }
                    logger.info(f"Помощник вызвал функцию '{func_name}' с аргументами: {func_args_str}")
                result = {
                    "choices": [
                        {
                            "message": result_message
                        }
                    ]
                }
                logger.info(f"Успешный ответ от GigaChat SDK, длина контента: {len(message.content)}")
                return result
            except AuthenticationError as e:
                logger.error(f"Ошибка аутентификации в официальном SDK: {e}")
                raise GigaChatAPIError(f"Ошибка аутентификации: {e}")
            except RateLimitError as e:
                logger.error(f"Достигнут лимит скорости: {e}")
                raise GigaChatAPIError(f"Достигнут лимит скорости: {e}")
            except BadRequestError as e:
                logger.error(f"Неверный запрос: {e}")
                raise GigaChatAPIError(f"Неверный запрос: {e}")
            except ForbiddenError as e:
                logger.error(f"Отказано в доступе: {e}")
                raise GigaChatAPIError(f"Отказано в доступе: {e}")
            except NotFoundError as e:
                logger.error(f"Ресурс не найден: {e}")
                raise GigaChatAPIError(f"Ресурс не найден: {e}")
            except RequestEntityTooLargeError as e:
                logger.error(f"Слишком большой объём запроса: {e}")
                raise GigaChatAPIError(f"Слишком большой объём запроса: {e}")
            except ServerError as e:
                logger.error(f"Ошибка сервера: {e}")
                raise GigaChatAPIError(f"Ошибка сервера: {e}")
            except GigaChatException as e:
                logger.error(f"Ошибка GigaChat: {e}")
                raise GigaChatAPIError(f"Ошибка GigaChat: {e}")
            except Exception as e:
                logger.error(f"Неожиданная ошибка в официальном SDK: {e}")
                raise GigaChatAPIError(f"Неожиданная ошибка: {e}")
        else:
            # Демо-режим: генерируем осмысленный ответ на основе промпта
            logger.info("Используется демо-режим (SDK недоступен)")
            return self._demo_response(messages, functions)

    async def generate_image(self, prompt: str, model: str = None, **kwargs) -> Dict[str, Any]:
        """Генерация изображения через чат GigaChat (как в примере пользователя)."""
        if model is None:
            model = self.model

        logger.info(f"Генерация изображения по промпту: {prompt}, модель: {model}")

        if not self.sdk_client or not HAS_GIGACHAT_SDK:
            raise GigaChatAPIError("Официальный SDK GigaChat недоступен или не инициализирован")

        try:
            # Получаем токен из существующего клиента (с credentials)
            token = self.sdk_client.get_token()
            access_token = token.access_token
            logger.info(f"Токен получен, истекает в {token.expires_at}")

            # Системный промпт для дизайнера (как в test.py)
            system_prompt = "Ты - дизайнер. Рисуешь арты, скетчи и логотипы по просьбе пользователя"
            payload = Chat(
                messages=[
                    Messages(
                        role=MessagesRole.SYSTEM,
                        content=system_prompt,
                    )
                ],
                temperature=0.7,
                function_call="auto",
            )

            # Создаём новый клиент с access_token (как в test.py)
            with GigaChat(access_token=access_token, verify_ssl_certs=False) as giga:
                # Добавляем пользовательский промпт
                payload.messages.append(Messages(role=MessagesRole.USER, content=prompt))
                # Отправляем запрос
                response = giga.chat(payload)
                payload.messages.append(response.choices[0].message)

                # Извлекаем file_id из HTML, если есть изображение
                if "img" in response.choices[0].message.content:
                    file_id = BeautifulSoup(response.choices[0].message.content, "html.parser").find('img').get("src")
                    if not file_id:
                        raise GigaChatAPIError(f"Не удалось извлечь file_id из ответа GigaChat: {response.choices[0].message.content}")
                    logger.info(f"Получен file_id: {file_id}")

                    # Получаем изображение по file_id
                    try:
                        image = giga.get_image(file_id)
                        logger.debug(f"Получен объект изображения: {image}")
                    except Exception as e:
                        logger.error(f"Ошибка получения изображения по file_id {file_id}: {e}")
                        raise GigaChatAPIError(f"Не удалось загрузить изображение: {e}")
                    
                    # Декодируем base64
                    try:
                        image_data = base64.b64decode(image.content)
                    except Exception as e:
                        logger.error(f"Ошибка декодирования base64: {e}")
                        raise GigaChatAPIError(f"Неверный формат изображения: {e}")
            
                    # Сохраняем изображение в папку uploads/generated
                    import os
                    import uuid
                    os.makedirs("/app/uploads/generated", exist_ok=True)
                    filename = f"{uuid.uuid4().hex}.jpg"
                    filepath = f"/app/uploads/generated/{filename}"

                    with open(filepath, mode="wb") as fd:
                        fd.write(image_data)

                    # URL для доступа через nginx
                    image_url = f"/uploads/generated/{filename}"
                    logger.info(f"Изображение сохранено, URL: {image_url}")
                    return {
                        "demo": False,
                        "url": image_url,
                        "description": f"Изображение по запросу: {prompt}",
                        "data": {"file_id": file_id, "content_length": len(image_data)}
                    }
                else:
                    # Если изображения нет, возвращаем ошибку
                    logger.error(f"В ответе нет изображения: {response.choices[0].message.content}")
                    raise GigaChatAPIError(f"Ответ не содержит изображение: {response.choices[0].message.content[:200]}")

        except AuthenticationError as e:
            logger.error(f"Ошибка аутентификации в официальном SDK: {e}")
            raise GigaChatAPIError(f"Ошибка аутентификации: {e}")
        except RateLimitError as e:
            logger.error(f"Достигнут лимит скорости: {e}")
            raise GigaChatAPIError(f"Достигнут лимит скорости: {e}")
        except BadRequestError as e:
            logger.error(f"Неверный запрос: {e}")
            raise GigaChatAPIError(f"Неверный запрос: {e}")
        except ForbiddenError as e:
            logger.error(f"Отказано в доступе: {e}")
            raise GigaChatAPIError(f"Отказано в доступе: {e}")
        except NotFoundError as e:
            logger.error(f"Ресурс не найден: {e}")
            raise GigaChatAPIError(f"Ресурс не найден: {e}")
        except RequestEntityTooLargeError as e:
            logger.error(f"Слишком большой объём запроса: {e}")
            raise GigaChatAPIError(f"Слишком большой объём запроса: {e}")
        except ServerError as e:
            logger.error(f"Ошибка сервера: {e}")
            raise GigaChatAPIError(f"Ошибка сервера: {e}")
        except GigaChatException as e:
            logger.error(f"Ошибка GigaChat: {e}")
            raise GigaChatAPIError(f"Ошибка GigaChat: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка в официальном SDK: {e}")
            raise GigaChatAPIError(f"Неожиданная ошибка: {e}")

    async def generate_code(self, prompt: str, language: str = "python", **kwargs) -> Dict[str, Any]:
        """Генерация кода через GigaChat API."""
        # Используем официальный SDK
        if self.sdk_client and HAS_GIGACHAT_SDK:
            logger.info("Попытка генерации кода через GigaChat SDK")
            try:
                # Системный промпт для генерации кода
                system_prompt = f"Ты — опытный программист. Сгенерируй код на языке {language} по следующему описанию. Верни только код, без пояснений."
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
                # Преобразуем сообщения в формат SDK
                sdk_messages = []
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        sdk_role = MessagesRole.USER
                    elif role == "assistant":
                        sdk_role = MessagesRole.ASSISTANT
                    elif role == "system":
                        sdk_role = MessagesRole.SYSTEM
                    else:
                        sdk_role = MessagesRole.USER
                    sdk_messages.append(Messages(role=sdk_role, content=content))

                chat = Chat(
                    model=self.model,
                    messages=sdk_messages,
                    temperature=kwargs.get("temperature", 0.7),
                    max_tokens=kwargs.get("max_tokens", 1024),
                    stream=False,
                )
                response = await self.sdk_client.achat(chat)
                logger.debug(f"Получен ответ чата для генерации кода: {response}")
                content = response.choices[0].message.content
                # Возвращаем сгенерированный код
                return {
                    "demo": False,
                    "code": content.strip(),
                    "language": language,
                    "data": response
                }
            except Exception as e:
                logger.error(f"Ошибка генерации кода через SDK: {e}")
                raise GigaChatAPIError(f"Ошибка генерации кода: {e}")
        else:
            raise GigaChatAPIError("Официальный SDK GigaChat недоступен или не инициализирован")

    async def close(self):
        """Закрыть клиенты."""
        if HAS_GIGACHAT_SDK and self.sdk_client:
            # В официальном SDK может быть метод close или aclose
            if hasattr(self.sdk_client, 'aclose'):
                await self.sdk_client.aclose()
            elif hasattr(self.sdk_client, 'close'):
                self.sdk_client.close()
            else:
                logger.warning("Не удалось закрыть SDK клиент, метод close/aclose не найден")


# Глобальный экземпляр клиента GigaChat
gigachat = GigaChatAPI()


async def get_gigachat() -> GigaChatAPI:
    """Зависимость FastAPI для получения клиента GigaChat."""
    return gigachat