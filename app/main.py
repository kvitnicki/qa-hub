"""
Точка входа FastAPI-приложения qa-hub.

Здесь:
- создаётся app,
- настраивается CORS,
- подключается API v1,
- добавляется healthcheck.

Бизнес-логика сюда не попадает — только конфигурация приложения.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan — «жизненный цикл» приложения.

    Код ДО yield выполняется при старте (startup).
    Код ПОСЛЕ yield — при остановке (shutdown).

    Зачем это нужно:
    - На старте можно прогреть БД, подключиться к Redis, загрузить кеш.
    - На стопе — закрыть соединения, отменить фоновые задачи.

    @asynccontextmanager превращает async-функцию с одним yield
    в асинхронный контекстный менеджер — FastAPI сам вызовет его
    в нужные моменты.

    Пример на будущее:
        @asynccontextmanager
        async def lifespan(app):
            await init_db()
            yield
            await close_db()
    """
    # Startup
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    yield
    # Shutdown
    print(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title="qa-hub API",
    description=(
        "Test Case Management System API. "
        "Позволяет управлять проектами, тест-кейсами, прогонами и результатами."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# CORS — Cross-Origin Resource Sharing.
# Разрешает браузеру делать запросы с других доменов (например, фронт на :3000).
# Настройка CORS_ORIGINS в config.py — список разрешённых источников.
# ["*"] разрешает всем — ок для разработки, НЕ для прода.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Подключаем API v1. Все эндпоинты будут по /api/v1/*
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["root"], summary="Корень API")
def root():
    """Проверка, что API живой."""
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"], summary="Healthcheck")
def health():
    """
    Проверка здоровья для Docker/K8s healthcheck.
    Возвращает 200, если приложение работает.
    """
    return {"status": "healthy"}
