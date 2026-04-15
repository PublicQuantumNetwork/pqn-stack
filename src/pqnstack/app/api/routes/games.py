from fastapi import APIRouter

from pqnstack.app.core.config import GamesAvailability, get_settings

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/availability")
def get_availability() -> GamesAvailability:
    return get_settings().games_availability
