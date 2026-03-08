"""
Модуль для генерации и проверки HMAC-подписей URL и upload-токенов.
Используется как в media_api, так и в core/api для единообразия подписи.
"""

import hashlib
import hmac
import time
import json
import base64
from typing import Optional


def sign_url(path: str, secret_key: str, expires_in: int = 3600) -> tuple:
    """
    Сгенерировать подпись и время истечения для файлового пути.

    Returns:
        (signature, expires) — hex-строка подписи и unix-timestamp истечения.
    """
    expires = int(time.time()) + expires_in
    message = f"{path}:{expires}"
    signature = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return signature, expires


def verify_url(path: str, signature: str, expires: int, secret_key: str) -> bool:
    """Проверить подпись URL. Возвращает False если подпись невалидна или истекла."""
    if int(time.time()) > expires:
        return False
    message = f"{path}:{expires}"
    expected = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


def create_upload_token(payload: dict, secret_key: str, expires_in: int = 300) -> str:
    """
    Создать подписанный upload-токен.

    payload может содержать: user_id, target_dir, max_size, allowed_types.
    """
    data = dict(payload)
    data['expires'] = int(time.time()) + expires_in
    payload_json = json.dumps(data, sort_keys=True)
    signature = hmac.new(
        secret_key.encode('utf-8'),
        payload_json.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    token_data = {'payload': data, 'signature': signature}
    return base64.urlsafe_b64encode(
        json.dumps(token_data).encode('utf-8')
    ).decode('utf-8')


def verify_upload_token(token: str, secret_key: str) -> Optional[dict]:
    """
    Проверить upload-токен.

    Returns:
        Словарь payload при успешной проверке, None при ошибке.
    """
    try:
        raw = base64.urlsafe_b64decode(token.encode('utf-8'))
        token_data = json.loads(raw)
        payload = token_data['payload']
        signature = token_data['signature']

        if int(time.time()) > payload.get('expires', 0):
            return None

        payload_json = json.dumps(payload, sort_keys=True)
        expected = hmac.new(
            secret_key.encode('utf-8'),
            payload_json.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return None

        return payload
    except Exception:
        return None
