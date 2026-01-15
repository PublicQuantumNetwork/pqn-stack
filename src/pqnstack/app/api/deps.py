from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends

from pqnstack.app.core.config import NodeState
from pqnstack.app.core.config import get_state
from pqnstack.app.core.config import settings
from pqnstack.network.client import Client


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(timeout=60) as client:
        yield client


ClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


async def get_instrument_client() -> AsyncGenerator[Client, None]:
    async with Client(host=settings.router_address, port=settings.router_port) as client:
        yield client


InstrumentClientDep = Annotated[httpx.AsyncClient, Depends(get_instrument_client)]

StateDep = Annotated[NodeState, Depends(get_state)]
