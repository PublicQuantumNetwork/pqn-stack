import logging

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from pqnstack.app.dependencies import ClientDep
from pqnstack.app.settings import settings
from pqnstack.app.settings import state
from pqnstack.app.utils import _calculate_chsh_expectation_error
from pqnstack.app.utils import _count_coincidences
from pqnstack.app.utils import _get_timetagger
from pqnstack.base.errors import PacketError
from pqnstack.network.client import Client

router = APIRouter(prefix="/chsh")

logger = logging.getLogger(__name__)


async def _chsh(  # noqa: C901 # Complexity is high due to the nature of the CHSH experiment.
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
        if settings.timetagger is None:
            logger.error("No timetagger configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No timetagger configured, please pass a timetagger_address",
            )
        try:
            tagger = _get_timetagger(client, settings.timetagger[0], settings.timetagger[1])
        except PacketError as e:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e

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

                    count = await _count_coincidences(
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


@router.post("")
async def chsh(
    basis: tuple[float, float],
    follower_node_address: str,
    http_client: ClientDep,
    timetagger_address: str | None = None,
) -> dict[str, float]:
    logger.info("Starting CHSH experiment with basis: %s", basis)

    chsh_value, chsh_error = await _chsh(basis, follower_node_address, http_client, timetagger_address)

    return {
        "chsh_value": chsh_value,
        "chsh_error": chsh_error,
    }


@router.post("/request-angle-by-basis")
async def request_angle_by_basis(index: int, *, perp: bool = False) -> bool:
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)
    hwp = client.get_device(settings.chsh_settings.request_hwp[0], settings.chsh_settings.request_hwp[1])
    if hwp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    angle = state.chsh_request_basis[index] + 90 * perp
    assert hasattr(hwp, "move_to")
    hwp.move_to(angle / 2)
    logger.info("moving waveplate", extra={"angle": angle})
    return True
