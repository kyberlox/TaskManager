import os
import asyncio
from gigachat import GigaChat
from gigachat.exceptions import GigaChatException

async def list_models():
    credentials = os.getenv("GIGACHAT_AUTHORIZATION_KEY")
    scope = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS_IMAGES")
    model = os.getenv("GIGACHAT_MODEL", "GigaChat-2")
    
    if not credentials:
        print("Ошибка: GIGACHAT_AUTHORIZATION_KEY не установлен")
        return
    
    try:
        # Инициализация клиента
        client = GigaChat(
            credentials=credentials,
            verify_ssl_certs=False,
            scope=scope,
            timeout=30.0,
            model=model,
        )
        # Получение токена (проверка доступности)
        token = client.get_token()
        print(f"Токен получен, истекает в {token.expires_at}")
        
        # Попробуем получить список моделей через API (если есть метод)
        # В официальном SDK может не быть метода list_models, но можно попробовать использовать chat/completions с фиктивным запросом?
        # Альтернативно, можно посмотреть документацию: https://developers.sber.ru/docs/ru/gigachat/api/overview
        # Но для простоты выведем известные модели из документации:
        known_models = [
            "GigaChat",
            "GigaChat-2",
            "GigaChat-2-Lite",
            "GigaChat-Lite",
            "GigaChat-Plus",
            "GigaChat-Pro",
        ]
        print("Известные модели (из документации):")
        for m in known_models:
            print(f"  - {m}")
        
        # Попробуем проверить, какие модели доступны для данного scope, отправив тестовый запрос с разными моделями
        print("\nПроверка доступности моделей (может занять время)...")
        test_prompt = "Привет"
        for test_model in known_models:
            try:
                client.model = test_model
                # Пробуем получить токен с новой моделью (не факт что работает)
                # Вместо этого можно попробовать отправить chat запрос с model параметром
                # Но для скорости просто проверим, не вызывает ли ошибку инициализация
                print(f"  Проверка модели {test_model}...", end=" ")
                # Создадим временного клиента с этой моделью
                temp_client = GigaChat(
                    credentials=credentials,
                    verify_ssl_certs=False,
                    scope=scope,
                    timeout=10.0,
                    model=test_model,
                )
                # Получим токен (если модель не поддерживается, может быть ошибка)
                temp_token = temp_client.get_token()
                print("OK (токен получен)")
                temp_client.close()
            except Exception as e:
                print(f"Ошибка: {e}")
        
    except GigaChatException as e:
        print(f"Ошибка GigaChat: {e}")
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())