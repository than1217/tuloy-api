from fastapi import APIRouter
from . import auth, beneficiaries, matching
from . import health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(beneficiaries.router)
api_router.include_router(matching.router)
