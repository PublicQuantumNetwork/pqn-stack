import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Annotated

import httpx
from fastapi import Depends
from fastapi import FastAPI
from fastapi import status
from pydantic import BaseModel

from pqnstack.network.client import Client
from pqnstack.pqn.protocols.measurement import MeasurementConfig

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app = FastAPI()


@dataclass
class CHSHSettings():
    # Specifies which half waveplate to use for the CHSH experiment. First value is the provider's name, second is the motor name.
    hwp: tuple[str, str] = ()
    timetagger: tuple[str, str] = ()  # Name of the timetagger to use for the CHSH experiment.
    request_hwp: tuple[str, str] = ()
    measurement_config: MeasurementConfig = field(default_factory=lambda: MeasurementConfig(5))


@dataclass
class Settings():
    router_name: str
    router_address: str
    router_port: int
    chsh_settings: CHSHSettings

settings = Settings()

async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient() as client:
        yield client


ClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


class NodeState(BaseModel):
    waveplates_available: bool = False
    chsh_basis: list[float] = [0.0, 45.0]


state = NodeState()


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


def _calculate_chsh_expectation_error(counts: list[int], dark_count: int = 0) -> float:
    total_counts = sum(counts)
    corrected_total = total_counts - 4 * dark_count
    if corrected_total <= 0:
        return 0
    first_term = (total_counts ** 0.5) / corrected_total
    expectation = abs(counts[0] + counts[3] - counts[1] - counts[2])
    second_term = (expectation / corrected_total**2) * (total_counts + 4 * dark_count) ** 0.5
    return first_term + second_term


@app.post("/chsh")
async def chsh(basis: tuple[float, float], other_node_address: str, http_client: ClientDep) -> tuple[float, float]:
    logger.debug("Starting CHSH")

    logger.debug("Instantiating client")
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)

    tagger = client.get_device(settings.chsh_settings.timetagger[0], settings.chsh_settings.timetagger[1])
    if tagger is None:
        logger.error("Could not find time tagger device")
        return {"error": "Could not find time tagger device"}

    logger.debug("Time tagger device found: %s", tagger)

    hwp = client.get_device(settings.chsh_settings.hwp[0], settings.chsh_settings.hwp[1])
    if hwp is None:
        logger.error("Could not find half waveplate device")
        return {"error": "Could not find halfwaveplate device"}

    logger.debug("Halfwaveplate device found: %s", hwp)

    expectation_values = []
    expectation_errors = []
    for angle in basis:  # Going through my basis angles
        for i in range(2): # Going through follower basis angles
            counts = []
            for a in [angle, (angle + 90)]:
                hwp.move_to(a/2)
                for perp in [False, True]:
                    r = await http_client.post(
                        f"http://{other_node_address}/chsh/request-angle-by-basis?index={i}&perp={perp}"
                    )
                    # TODO: Handle other status codes
                    if r.status_code != status.HTTP_200_OK:
                        logger.error("Failed to request follower: %s", r.text)
                        return {"error": "Failed to request follower"}

                    count = tagger.measure_coincidence(
                        settings.chsh_settings.measurement_config.channel1,
                        settings.chsh_settings.measurement_config.channel2,
                        settings.chsh_settings.measurement_config.binwidth, # might have to cast to int
                        int(settings.chsh_settings.measurement_config.duration * 1e12)
                    )

                    counts.append(count)

            # Calculating expectation value
            numerator = counts[0] - counts[1] - counts[2] + counts[3]
            denominator = sum(counts) - 4 * settings.chsh_settings.measurement_config.dark_count
            expectation_value = 0 if denominator == 0 else numerator / denominator
            expectation_values.append(expectation_value)

            # Calculating error
            error = _calculate_chsh_expectation_error(counts, settings.chsh_settings.measurement_config.dark_count)
            expectation_errors.append(error)

            logger.info("For angle %s, for follower index %s, expectation value: %s, error: %s", angle, i, expectation_value, error)

    logger.info("Expectation values: %s", expectation_values)
    logger.info("Expectation errors: %s", expectation_errors)

    negative_count = sum(1 for v in expectation_values if v < 0)
    negative_indices = [i for i, v in enumerate(expectation_values) if v < 0]
    impossible_counts = [0, 2, 4]

    if negative_count in impossible_counts:
        raise ValueError(f"Impossible negative expectation values found: {negative_indices}, expectation_values = {expectation_values}, expectation_errors = {expectation_errors}")

    if len(negative_indices) > 1 or negative_indices[0] != 0:
        logger.warning("Expectation values have unexpected negative indices: %s", negative_indices)

    chsh_value = sum(abs(x) for x in expectation_values)
    chsh_error = sum((x**2 for x in expectation_errors))**0.5

    return chsh_value, chsh_error



@app.post("/chsh/request-angle-by-basis")
async def request_angle_by_basis(index: int, *, perp: bool = False) -> bool:
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)
    hwp = client.get_device(settings.chsh_settings.request_hwp[0], settings.chsh_settings.request_hwp[1])
    if hwp is None:
        logger.error("Could not find halfwaveplate device")
        return False

    angle = state.chsh_basis[index] + 90 * perp
    hwp.move_to(angle/2)
    logger.info("moving waveplate", extra={"angle": angle})
    return True
