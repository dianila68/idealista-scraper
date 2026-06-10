from fastapi import APIRouter

from app.api.v1 import auth, devices, filters, listings, users

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(filters.router, prefix="/filters", tags=["filters"])
router.include_router(listings.router, prefix="/listings", tags=["listings"])
router.include_router(devices.router, prefix="/devices", tags=["devices"])
