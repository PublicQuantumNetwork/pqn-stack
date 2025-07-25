import logging
from typing import cast

import httpx
from fastapi import HTTPException
from fastapi import status

from pqnstack.app.core.config import settings
from pqnstack.base.driver import DeviceDriver
from pqnstack.network.client import Client
from pqnstack.pqn.protocols.measurement import MeasurementConfig

logger = logging.getLogger(__name__)


def get_timetagger(client: Client) -> DeviceDriver:
    if settings.timetagger is None:
        logger.error("No timetagger configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No timetagger configured",
        )

    tagger = client.get_device(settings.timetagger[0], settings.timetagger[1])
    if tagger is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find time tagger device",
        )

    logger.debug("Time tagger device found: %s", tagger)
    return tagger


async def count_coincidences(
    measurement_config: MeasurementConfig,
    tagger: DeviceDriver | None = None,
    tagger_address: str | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> int:
    if tagger is None and tagger_address is None:
        msg = "Either tagger or tagger_address must be provided"
        raise ValueError(msg)

    if tagger_address is not None and http_client is None:
        msg = "http_client must be provided if tagger_address is provided"
        raise ValueError(msg)

    if tagger_address is None:
        assert tagger is not None
        assert hasattr(tagger, "measure_coincidence")
        count = tagger.measure_coincidence(
            measurement_config.channel1,
            measurement_config.channel2,
            measurement_config.binwidth,  # might have to cast to int
            int(measurement_config.duration * 1e12),
        )
    else:
        assert http_client is not None
        r = await http_client.get(
            f"http://{tagger_address}/timetagger/measure?duration={measurement_config.duration}&binwidth={measurement_config.binwidth}&channel1={measurement_config.channel1}&channel2={measurement_config.channel2}&dark_count={measurement_config.dark_count}"
        )
        # TODO: Handle other status codes
        if r.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to measure coincidences",
            )
        count = cast("int", r.json())
        if not isinstance(count, int):
            logger.error("Invalid response from timetagger: %s", count)
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Invalid response from timetagger",
            )
        logger.debug("Measured %d coincidences", count)
    return int(count)


def calculate_chsh_expectation_error(counts: list[int], dark_count: int = 0) -> float:
    total_counts = sum(counts)
    corrected_total = total_counts - 4 * dark_count
    if corrected_total <= 0:
        return 0
    first_term = (total_counts**0.5) / corrected_total
    expectation = abs(counts[0] + counts[3] - counts[1] - counts[2])
    second_term = (expectation / corrected_total**2) * (total_counts + 4 * dark_count) ** 0.5
    return float(first_term + second_term)
