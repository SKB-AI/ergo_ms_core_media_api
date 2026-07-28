# Media API

Отдельный сервис для хранения и раздачи файлов. Основной Django API **не** отдаёт пользовательские файлы по `/media/`.

## Зачем отдельный сервис

Проверка прав и подписанные URL реализованы здесь, а не в основном API. Так проще изолировать доступ к файлам и не смешивать медиа с остальными эндпоинтами сервера.

## Правила для разработчиков

| Тема | Правило |
|------|---------|
| Загрузка и отдача файлов | [`.cursor/rules/media_api.mdc`](../../.cursor/rules/media_api.mdc) |
| Безопасность | [`.cursor/rules/security.mdc`](../../.cursor/rules/security.mdc) |
| Redis, nginx (prod) | [`.cursor/rules/deployment-infra.mdc`](../../.cursor/rules/deployment-infra.mdc) |

Серверная часть ядра, которая вызывает media_api: `core/api/src/core/utils/media_client/`, `media_signing.py`. Общая HMAC-логика подписи — `core/shared/media_hmac.py`. Порт по умолчанию — **8003** (`.env`, `MEDIA_API_BIND_PORT`).

За nginx задайте `MEDIA_API_URL` или `MEDIA_API_HOST` / `MEDIA_API_PROTOCOL` — см. [`env/nginx.env.example`](../../env/nginx.env.example).
