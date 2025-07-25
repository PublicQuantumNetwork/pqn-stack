from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends

from pqnstack.app.settings import settings
from pqnstack.network.client import Client


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(timeout=600_000) as client:
        yield client


async def get_internal_client() -> AsyncGenerator[Client, None]:
    with Client(host=settings.router_address, port=settings.router_port, timeout=600_000) as client:
        yield client


HTTPClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]

InternalClientDep = Annotated[Client, Depends(get_internal_client)]
