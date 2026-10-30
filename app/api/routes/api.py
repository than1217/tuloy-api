from fastapi import APIRouter
from . import auth, beneficiaries, matching

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(beneficiaries.router)
api_router.include_router(matching.router)
