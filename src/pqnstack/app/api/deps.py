from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends

from pqnstack.app.core.config import NodeState
from pqnstack.app.core.config import get_state


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(timeout=600_000) as client:
        yield client


ClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


StateDep = Annotated[NodeState, Depends(get_state)]
