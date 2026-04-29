from fastapi import APIRouter

from pqn_node.core.config import GamesAvailability
from pqn_node.core.config import get_settings

router = APIRouter(prefix="/games", tags=["games"])


@router.get("/availability")
def get_availability() -> GamesAvailability:
    return get_settings().games_availability
