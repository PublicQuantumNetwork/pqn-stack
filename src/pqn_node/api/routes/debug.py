from fastapi import APIRouter

from pqn_node.api.deps import StateDep
from pqn_node.core.config import NodeState
from pqn_node.core.config import Settings
from pqn_node.core.config import settings

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/state")
async def get_state(state: StateDep) -> NodeState:
    return state


@router.get("/settings")
async def get_settings() -> Settings:
    return settings
