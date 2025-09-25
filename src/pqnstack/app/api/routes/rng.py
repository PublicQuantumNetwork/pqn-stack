import logging
from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from fastapi import status

from pqnstack.app.api.deps import ClientDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rng", tags=["rng"])


@router.get("/singles_parity")
async def singles_parity(
    timetagger_address: str,
    integration_time_s: float,
    channels: Annotated[list[int], Query()],
    http_client: ClientDep,
) -> list[int]:
    """Fetch singles counts from a timetagger and return their per-channel parity (mod 2)."""
    params: list[tuple[str, str | int | float | bool | None]] = [
        ("integration_time_s", integration_time_s),
        *[("channels", ch) for ch in channels],
    ]

    url = f"http://{timetagger_address}/timetagger/count_singles"
    response = await http_client.get(url, params=params)

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


@router.get("/fortune")
async def fortune(
    timetagger_address: str,
    integration_time_s: float,
    fortune_size: int,
    http_client: ClientDep,
    channels: Annotated[list[int], Query()],
) -> list[int]:
    """Run singles parity `fortune_size` times and, per channel, interpret the result in bitstring as a decimal number."""
    if fortune_size <= 0:
        raise HTTPException(status_code=400, detail="fortune_size must be a positive integer")

    trials: list[list[int]] = []
    for _ in range(fortune_size):
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("timetagger_address", timetagger_address),
            ("integration_time_s", integration_time_s),
            *[("channels", ch) for ch in channels],
        ]

        url = f"http://{timetagger_address}/rng/singles_parity"
        parities = await http_client.get(url, params=params)
        trials.append(parities.json())

    results: list[int] = []
    for bits_for_channel in zip(*trials, strict=True):
        value = 0
        for bit in bits_for_channel:
            value = (value << 1) | bit
        results.append(value)

    logger.info(
        "Fortune results (channels=%s, fortune_size=%d): %s",
        channels,
        fortune_size,
        results,
    )
    return results
