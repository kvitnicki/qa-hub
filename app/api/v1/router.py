"""
Главный роутер API v1.

Зачем нужен агрегатор:
- В main.py подключается ОДИН роутер с префиксом /api/v1.
- Внутри — все роутеры версии v1 (auth, users, projects, ...).

Преимущества:
- Если завтра появится API v2 — сделаем router_v2.py и подключим его
  в main.py с префиксом /api/v2, не трогая v1.
- Каждый файл (auth.py, users.py) знает только про свои эндпоинты.
"""

from fastapi import APIRouter

from app.api.v1 import auth


# Главный роутер v1
api_router = APIRouter()

# Подключаем роутер auth. Все его эндпоинты будут доступны по /api/v1/auth/*
# Префикс /auth уже задан внутри auth.py (APIRouter(prefix="/auth"))
api_router.include_router(auth.router)
