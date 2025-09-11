from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends

from pqnstack.app.core.config import CoordinationState
from pqnstack.app.core.config import state


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(timeout=600_000) as client:
        yield client


ClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


async def get_coordination_state() -> AsyncGenerator[CoordinationState, None]:
    yield state.coordination_state


CoordinationStateDep = Annotated[CoordinationState, Depends(get_coordination_state)]
