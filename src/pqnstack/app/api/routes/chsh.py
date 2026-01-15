import logging
from typing import TYPE_CHECKING
from typing import cast

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from pqnstack.app.api.deps import ClientDep
from pqnstack.app.api.deps import StateDep
from pqnstack.app.core.config import settings
from pqnstack.app.core.models import calculate_chsh_expectation_error
from pqnstack.network.client import Client

if TYPE_CHECKING:
    from pqnstack.base.instrument import RotatorInstrument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chsh", tags=["chsh"])


async def _chsh(  # Complexity is high due to the nature of the CHSH experiment.
    basis: tuple[float, float],
    follower_node_address: str,
    http_client: ClientDep,
    timetagger_address: str,
) -> tuple[float, float]:
    logger.debug("Starting CHSH")

    logger.debug("Instantiating client")
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)

    # TODO: Check if settings.chsh_settings.hwp is set before even trying to get the device.
    hwp = cast("RotatorInstrument", client.get_device(settings.chsh_settings.hwp[0], settings.chsh_settings.hwp[1]))
    if hwp is None:
        logger.error("Could not find half waveplate device")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    logger.debug("Halfwaveplate device found: %s", hwp)

    expectation_values = []
    expectation_errors = []
    basis = [0, abs(basis[0] - basis[1]) % 90]
    for angle in basis:  # Going through my basis angles
        for i in range(2):  # Going through follower basis angles
            counts = []
            for a in [angle, (angle + 90)]:
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

                    count_ret = await http_client.get(
                        f"http://{timetagger_address}/timetagger/measure_correlation?integration_time_s={settings.chsh_settings.measurement_config.integration_time_s}&coincidence_window_ps={settings.chsh_settings.measurement_config.binwidth_ps}&channel1={settings.chsh_settings.measurement_config.channel1}&channel2={settings.chsh_settings.measurement_config.channel2}&dark_count={settings.chsh_settings.measurement_config.dark_count}"
                    )
                    if count_ret.status_code != status.HTTP_200_OK:
                        logger.error("Failed to get correlation from timetagger: %s", count_ret.text)
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to get correlation from timetagger",
                        )
                    count = cast("int", count_ret.json())
                    counts.append(count)

            # Calculating expectation value
            numerator = counts[0] - counts[1] - counts[2] + counts[3]
            denominator = sum(counts) - 4 * settings.chsh_settings.measurement_config.dark_count
            expectation_value = 0 if denominator == 0 else numerator / denominator
            expectation_values.append(expectation_value)

            # Calculating error
            error = calculate_chsh_expectation_error(counts, settings.chsh_settings.measurement_config.dark_count)
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

    # FIXME: This is a temporary fix for handling impossible expectation values. We should not have to rely on the settings for this.
    expectation_values = [x*y for x,y in zip(expectation_values, settings.chsh_settings.expectation_signs)]
    logger.info("What are you settings? %s", settings.chsh_settings.expectation_signs)

    logger.info("After passing signed calculation: %s", expectation_values)
    chsh_value = sum(x for x in expectation_values)
    chsh_error = sum(x**2 for x in expectation_errors) ** 0.5

    return chsh_value, chsh_error


@router.post("/")
async def chsh(
    basis: tuple[float, float],
    follower_node_address: str,
    http_client: ClientDep,
    timetagger_address: str,
) -> dict[str, float]:
    logger.info("Starting CHSH experiment with basis: %s", basis)

    chsh_value, chsh_error = await _chsh(basis, follower_node_address, http_client, timetagger_address)

    return {
        "chsh_value": chsh_value,
        "chsh_error": chsh_error,
    }


@router.post("/request-angle-by-basis")
async def request_angle_by_basis(index: int, state: StateDep, *, perp: bool = False) -> bool:
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)
    hwp = cast(
        "RotatorInstrument",
        client.get_device(settings.chsh_settings.request_hwp[0], settings.chsh_settings.request_hwp[1]),
    )
    if hwp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    angle = state.chsh_request_basis[index] + 90 * perp
    hwp.move_to(angle / 2)
    logger.info("moving waveplate", extra={"angle": angle})
    return True
