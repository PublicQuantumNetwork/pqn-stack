import logging
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rng", tags=["rng"])


@router.post("/singles_parity")
async def singles_parity(
    timetagger_address: str,
    integration_time_s: float,
    channels: list[int],
) -> dict[str, list[int]]:
    """Fetch singles counts from a timetagger and return their per-channel parity (mod 2)."""
    url = (
        f"http://{timetagger_address}/timetagger/count_singles"
        f"?integration_time_s={integration_time_s}"
        + "".join(f"&channels={ch}" for ch in channels)
    )

    async with httpx.AsyncClient(timeout=600.0) as client:
        response = await client.get(url)

    if response.status_code != status.HTTP_200_OK:
        logger.error("Failed to get singles counts: %s", response.text)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch singles counts from timetagger",
        )

    data: Any = response.json()
    if not isinstance(data, list) or not all(isinstance(x, int) for x in data):
        logger.error("Unexpected response format: %s", data)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected response format from timetagger",
        )

    parities = [count % 2 for count in data]

    logger.info("Singles counts %s, parities %s", data, parities)
    return parities

