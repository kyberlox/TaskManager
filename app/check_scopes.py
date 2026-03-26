import os
import httpx
import uuid
import base64

credentials = os.getenv("GIGACHAT_AUTHORIZATION_KEY")
if not credentials:
    print("GIGACHAT_AUTHORIZATION_KEY не установлен")
    exit(1)

scopes_to_test = [
    "GIGACHAT_API_PERS",
    "GIGACHAT_API_PERS_IMAGES",
    "GIGACHAT_API_CORP",
    "GIGACHAT_API_CORP_IMAGES",
    "GIGACHAT_API_PERS_GENERATION",
    "GIGACHAT_API_CORP_GENERATION",
]

api_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

for scope in scopes_to_test:
    print(f"Проверка scope: {scope}")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {credentials}"
    }
    data = {"scope": scope}
    try:
        with httpx.Client(verify=False) as client:
            resp = client.post(api_url, headers=headers, data=data, timeout=30)
            if resp.status_code == 200:
                print(f"  Успех! Токен получен.")
                # можно распарсить ответ, но не обязательно
            else:
                print(f"  Ошибка {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"  Исключение: {e}")