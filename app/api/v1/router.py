"""
Главный роутер API v1.
"""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    mentor_applications,
    projects,
    test_cases,
    test_runs,
    test_suites,
)


api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(mentor_applications.router)
api_router.include_router(projects.router)
api_router.include_router(test_suites.router)
api_router.include_router(test_cases.router)
api_router.include_router(test_runs.router)
