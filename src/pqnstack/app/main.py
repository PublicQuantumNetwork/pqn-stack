import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from dataclasses import field
from typing import Annotated

import random

import httpx
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel

from pqnstack.base.driver import DeviceDriver
from pqnstack.constants import QKDEncodingBasis, QKDAngleValuesHWP
from pqnstack.network.client import Client
from pqnstack.pqn.protocols.measurement import MeasurementConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()


@dataclass
class CHSHSettings:
    # Specifies which half waveplate to use for the CHSH experiment. First value is the provider's name, second is the motor name.
    hwp: tuple[str, str] = ("", "")
    request_hwp: tuple[str, str] = ("", "")
    measurement_config: MeasurementConfig = field(default_factory=lambda: MeasurementConfig(5))


@dataclass
class QKDSettings:
    hwp: tuple[str, str] = ("", "")
    request_hwp: tuple[str, str] = ("", "")
    bitstring_length: int = 4
    discriminating_threshold = 10
    measurement_config: MeasurementConfig = field(default_factory=lambda: MeasurementConfig(5))


@dataclass
class Settings:
    router_name: str
    router_address: str
    router_port: int
    chsh_settings: CHSHSettings
    qkd_settings: QKDSettings
    timetagger: tuple[str, str] | None = None  # Name of the timetagger to use for the CHSH experiment.


settings = Settings("", "", 0, CHSHSettings(), qkd_settings=QKDSettings())


# FIXME: This should probably be toggable depending on what the purpose of the call.
async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(timeout=600000) as client:
        yield client


ClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]

QKD_ENC = QKDEncodingBasis
QKD_ANG_VAL = QKDAngleValuesHWP


class NodeState(BaseModel):
    chsh_request_basis: list[float] = [22.5, 67.5]
    # FIXME: Use enums for this
    qkd_basis_list: list[QKD_ENC] = [QKD_ENC.DA, QKD_ENC.HV, QKD_ENC.DA, QKD_ENC.HV]
    qkd_bit_list: list = []
    qkd_resulting_bit_list: list = []  # Resulting bits after QKD
    qkd_request_basis_list: list = []  # Basis angles for QKD
    qkd_request_bit_list: list = []


state = NodeState()


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


def _get_timetagger(client) -> DeviceDriver:
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


async def _count_coincidences(
    measurement_config: MeasurementConfig,
    tagger: DeviceDriver | None = None,
    tagger_address: str | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> int:
    if tagger is None and tagger_address is None:
        raise ValueError("Either tagger or tagger_address must be provided")

    if tagger_address is not None and http_client is None:
        raise ValueError("http_client must be provided if tagger_address is provided")

    if tagger_address is None:
        assert hasattr(tagger, "measure_coincidence")
        count = tagger.measure_coincidence(
            measurement_config.channel1,
            measurement_config.channel2,
            measurement_config.binwidth,  # might have to cast to int
            int(measurement_config.duration * 1e12),
        )
    else:
        r = await http_client.get(
            f"http://{tagger_address}/timetagger/measure?duration={measurement_config.duration}&binwidth={measurement_config.binwidth}&channel1={measurement_config.channel1}&channel2={measurement_config.channel2}&dark_count={measurement_config.dark_count}"
        )
        # TODO: Handle other status codes
        if r.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to measure coincidences",
            )
        count = r.json()
        if not isinstance(count, int):
            logger.error("Invalid response from timetagger: %s", count)
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE,
                detail="Invalid response from timetagger",
            )
        logger.debug("Measured %d coincidences", count)
    return count


def _calculate_chsh_expectation_error(counts: list[int], dark_count: int = 0) -> float:
    total_counts = sum(counts)
    corrected_total = total_counts - 4 * dark_count
    if corrected_total <= 0:
        return 0
    first_term = (total_counts**0.5) / corrected_total
    expectation = abs(counts[0] + counts[3] - counts[1] - counts[2])
    second_term = (expectation / corrected_total**2) * (total_counts + 4 * dark_count) ** 0.5
    return float(first_term + second_term)


# TODO: Refactor timetagger handling since it is going to be used in multiple places.
@app.post("/chsh")
async def chsh(  # noqa: C901, PLR0912, PLR0915  # Complexity is high due to the nature of the CHSH experiment.
    basis: tuple[float, float],
    follower_node_address: str,
    http_client: ClientDep,
    timetagger_address: str | None = None,
) -> tuple[float, float]:
    logger.debug("Starting CHSH")

    logger.debug("Instantiating client")
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)

    tagger = None
    if timetagger_address is None:
        tagger = _get_timetagger(client)

    # TODO: Check if settings.chsh_settings.hwp is set before even trying to get the device.
    hwp = client.get_device(settings.chsh_settings.hwp[0], settings.chsh_settings.hwp[1])
    if hwp is None:
        logger.error("Could not find half waveplate device")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    logger.debug("Halfwaveplate device found: %s", hwp)

    expectation_values = []
    expectation_errors = []
    for angle in basis:  # Going through my basis angles
        for i in range(2):  # Going through follower basis angles
            counts = []
            for a in [angle, (angle + 90)]:
                assert hasattr(hwp, "move_to")
                hwp.move_to(a / 2)
                for perp in [False, True]:
                    r = await http_client.post(
                        f"http://{follower_node_address}/chsh/request-angle-by-basis?index={i}&perp={perp}"
                    )
                    # TODO: Handle other status codes
                    if r.status_code != status.HTTP_200_OK:
                        logger.error("Failed to request follower: %s", r.text)
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to request follower",
                        )

                    count = _count_coincidences(
                        settings.chsh_settings.measurement_config, tagger, timetagger_address, http_client
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

            logger.info(
                "For angle %s, for follower index %s, expectation value: %s, error: %s",
                angle,
                i,
                expectation_value,
                error,
            )

    logger.info("Expectation values: %s", expectation_values)
    logger.info("Expectation errors: %s", expectation_errors)

    negative_count = sum(1 for v in expectation_values if v < 0)
    negative_indices = [i for i, v in enumerate(expectation_values) if v < 0]
    impossible_counts = [0, 2, 4]

    if negative_count in impossible_counts:
        msg = f"Impossible negative expectation values found: {negative_indices}, expectation_values = {expectation_values}, expectation_errors = {expectation_errors}"
        raise ValueError(msg)

    if len(negative_indices) > 1 or negative_indices[0] != 0:
        logger.warning("Expectation values have unexpected negative indices: %s", negative_indices)

    chsh_value = sum(abs(x) for x in expectation_values)
    chsh_error = sum(x**2 for x in expectation_errors) ** 0.5

    return chsh_value, chsh_error


@app.post("/chsh/request-angle-by-basis")
async def request_angle_by_basis(index: int, *, perp: bool = False) -> bool:
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)
    hwp = client.get_device(settings.chsh_settings.request_hwp[0], settings.chsh_settings.request_hwp[1])
    if hwp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    angle = state.chsh_basis[index] + 90 * perp
    assert hasattr(hwp, "move_to")
    hwp.move_to(angle / 2)
    logger.info("moving waveplate", extra={"angle": angle})
    return True


@app.post("/qkd/")
async def qkd(
    follower_node_address: str,
    http_client: ClientDep,
    timetagger_address: str | None = None,
) -> dict[str, str]:
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)
    hwp = client.get_device(settings.qkd_settings.hwp[0], settings.qkd_settings.hwp[1])

    if hwp is None:
        logger.error("Could not find half waveplate device")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    tagger = None
    if timetagger_address is None:
        tagger = _get_timetagger(client)

    counts = []
    for basis in settings.qkd_settings.qkd_basis_list:
        r = await http_client.post(f"http://{follower_node_address}/qkd/single_bit")

        if r.status_code != status.HTTP_200_OK:
            logger.error("Failed to handshake with follower: %s", r.text)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to handshake with follower",
            )
        logger.debug("Handshake with follower successful")

        int_choice = random.randint(0, 1)  # FIXME: Make this real quantum random.
        state.qkd_bit_list.append(int_choice)

        hwp.move_to(basis.value[int_choice].value)

        count = _count_coincidences(settings.qkd_settings.measurement_config, tagger, timetagger_address, http_client)

        counts.append(count)

    bit_list = []
    for count, choice, basis in zip(counts, state.qkd_bit_list, settings.qkd_settings.qkd_basis_list):
        if basis == QKD_ENC.HV:
            if choice == 0:
                if counts > settings.qkd_settings.discriminating_threshold:
                    bit_list.append(1)
                else:
                    bit_list.append(0)
            elif choice == 1:
                if counts > settings.qkd_settings.discriminating_threshold:
                    bit_list.append(0)
                else:
                    bit_list.append(1)
            else:
                raise RuntimeError("something went really wrong with QKD choice list")
        elif basis == QKD_ENC.DA:
            if choice == 0:
                if counts > settings.qkd_settings.discriminating_threshold:
                    bit_list.append(0)
                else:
                    bit_list.append(1)
            elif choice == 1:
                if counts > settings.qkd_settings.discriminating_threshold:
                    bit_list.append(1)
                else:
                    bit_list.append(0)
            else:
                raise RuntimeError("something went really wrong with QKD choice list")

    basis_list = [basis.name for basis in settings.qkd_settings.qkd_basis_list]
    r = await http_client.post(f"http://{follower_node_address}/qkd/request_basis_list?leader_basis_list={basis_list}")
    if r.status_code != status.HTTP_200_OK:
        logger.error("Failed to request basis list from follower: %s", r.text)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request basis list from follower",
        )
    follower_basis_list = r.json()

    index_list = [i for i in range(len(follower_basis_list)) if follower_basis_list[i] == basis_list[i]]
    final_bits = [bit_list[i] for i in index_list]

    logger.info("Final bits: %s", final_bits)

    return final_bits


@app.post("/qkd/single_bit")
async def request_qkd_single_pass() -> bool:
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)
    hwp = client.get_device(settings.qkd_settings.request_hwp[0], settings.qkd_settings.request_hwp[1])

    if hwp is None:
        logger.error("Could not find half waveplate device")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    logger.debug("Halfwaveplate device found: %s", hwp)

    basis_choice = random.choices([QKD_ENC.HV, QKD_ENC.DA])  # FIXME: Make this real quantum random.
    int_choice = random.randint(0, 1)  # FIXME: Make this real quantum random.

    state.qkd_request_basis_list.append(basis_choice)
    state.qkd_request_bit_list.append(int_choice)

    angle = basis_choice.value[int_choice].value

    assert hasattr(hwp, "move_to")
    hwp.move_to(angle)

    return True


@app.get("/qkd/request_basis_list")
def request_qkd_basis_list(leader_basis_list: list[str]) -> list[str]:
    """
    Returns the list of basis angles for QKD.
    """

    # Check that lengths match
    if len(leader_basis_list) != len(state.qkd_request_basis_list):
        logger.error("Length of leader basis list does not match length of request basis list")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Length of leader basis list does not match length of request basis list",
        )

    ret = [basis.name for basis in state.qkd_request_basis_list]

    index_list = [i for i in range(len(leader_basis_list)) if ret[i] == leader_basis_list[i]]
    final_bits = [state.qkd_request_bit_list[i] for i in index_list]

    logger.error("Final bits: %s", final_bits)

    state.qkd_request_basis_list.clear()

    return ret


@app.get("/timetagger/measure")
async def timetagger_measure(duration: int, binwidth: int = 500, channel1: int = 1, channel2: int = 2) -> int:
    if settings.timetagger is None:
        logger.error("No timetagger configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No timetagger configured",
        )

    mconf = MeasurementConfig(duration=duration, binwidth=binwidth, channel1=channel1, channel2=channel2)
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)
    tagger = client.get_device(settings.timetagger[0], settings.timetagger[1])
    if tagger is None:
        logger.error("Could not find time tagger device")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find time tagger device",
        )

    logger.debug("Time tagger device found: %s", tagger)
    assert hasattr(tagger, "measure_coincidence")
    count = tagger.measure_coincidence(
        mconf.channel1,
        mconf.channel2,
        mconf.binwidth,
        int(mconf.duration * 1e12),  # Convert seconds to picoseconds
    )

    logger.info("Measured %d coincidences", count)
    return int(count)
