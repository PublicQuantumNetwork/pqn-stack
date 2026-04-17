import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Annotated
from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from fastapi.responses import StreamingResponse

from pqnstack.app.api.deps import ClientDep
from pqnstack.app.api.deps import StateDep
from pqnstack.app.core.config import rng_progress_event
from pqnstack.app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rng", tags=["rng"])


@router.get("/progress")
async def rng_progress(state: StateDep) -> StreamingResponse:
    """SSE endpoint for streaming RNG fortune measurement progress to frontend."""

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'event': 'connected'})}\n\n"

            while True:
                event_sent = False

                # Check for progress event
                try:
                    await asyncio.wait_for(rng_progress_event.wait(), timeout=1.0)
                    yield f"data: {json.dumps({'event': 'rng_progress', 'current': state.rng_progress_current, 'total': state.rng_progress_total, 'running': state.rng_running})}\n\n"
                    rng_progress_event.clear()
                    event_sent = True
                except TimeoutError:
                    pass

                # Send heartbeat if no event was sent to keep connection alive
                if not event_sent:
                    yield ":\n"

                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("RNG SSE connection closed by client")
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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
async def fortune(  # noqa: PLR0913
    timetagger_address: str,
    http_client: ClientDep,
    state: StateDep,
    fortune_size: int | None = None,
    integration_time_s: float = 1.0,
    channels: Annotated[list[int] | None, Query()] = None,
) -> list[int]:
    """Run singles parity `fortune_size` times and, per channel, interpret the result in bitstring as a decimal number.

    `fortune_size` and `channels` default to the node's configured `rng_settings` when omitted.
    """
    resolved_fortune_size = fortune_size if fortune_size is not None else settings.rng_settings.fortune_size
    if resolved_fortune_size <= 0:
        raise HTTPException(status_code=400, detail="fortune_size must be a positive integer")

    resolved_channels = channels if channels is not None else settings.rng_settings.channels
    resolved_integration_time_s = integration_time_s

    # Initialize progress tracking
    state.rng_running = True
    state.rng_progress_current = 0
    state.rng_progress_total = resolved_fortune_size
    rng_progress_event.set()

    trials: list[list[int]] = []
    for _ in range(resolved_fortune_size):
        params: list[tuple[str, str | int | float | bool | None]] = [
            ("timetagger_address", timetagger_address),
            ("integration_time_s", resolved_integration_time_s),
            *[("channels", ch) for ch in resolved_channels],
        ]

        url = f"http://{timetagger_address}/rng/singles_parity"
        parities = await http_client.get(url, params=params)
        trials.append(parities.json())

        # Update progress
        state.rng_progress_current += 1
        rng_progress_event.set()

    results: list[int] = []
    for bits_for_channel in zip(*trials, strict=True):
        value = 0
        for bit in bits_for_channel:
            value = (value << 1) | bit
        results.append(value)

    logger.info(
        "Fortune results (channels=%s, fortune_size=%d): %s",
        resolved_channels,
        resolved_fortune_size,
        results,
    )

    # Mark RNG as complete
    state.rng_running = False
    rng_progress_event.set()

    return results
