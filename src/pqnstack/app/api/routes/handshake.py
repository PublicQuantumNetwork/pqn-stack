from fastapi import APIRouter

from pqnstack.app.core.config import state, state_change_event

router = APIRouter()



@router.get("/handshake")
async def handshake() -> bool:
    state.incoming = True

    state_change_event.set()
    return True

