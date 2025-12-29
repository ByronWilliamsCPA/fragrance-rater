from fastapi import APIRouter
from app.api.fragrances import router as fragrances_router
from app.api.evaluations import router as evaluations_router
from app.api.imports import router as imports_router
from app.api.recommendations import router as recommendations_router

api_router = APIRouter()

api_router.include_router(fragrances_router)
api_router.include_router(evaluations_router)
api_router.include_router(imports_router)
api_router.include_router(recommendations_router)

__all__ = ["api_router"]
