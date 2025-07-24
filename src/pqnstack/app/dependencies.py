import httpx
from typing import Annotated
from fastapi import Depends
from collections.abc import AsyncGenerator

async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(timeout=600_000) as client:
        yield client

ClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]
