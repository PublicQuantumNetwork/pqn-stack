from fastapi import APIRouter

from pqnstack.app.api.deps import StateDep
from pqnstack.app.core.config import NodeState, Settings, settings

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/state")
async def get_state(state: StateDep) -> NodeState:
    return state


@router.get("/settings")
async def get_settings() -> Settings:
    return settings