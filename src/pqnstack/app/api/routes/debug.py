from fastapi import APIRouter

from pqnstack.app.core.config import NodeState
from pqnstack.app.core.config import state

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/state")
async def get_state() -> NodeState:
    return state
