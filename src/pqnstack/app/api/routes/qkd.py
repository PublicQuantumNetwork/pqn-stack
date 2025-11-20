import logging
import secrets
from typing import TYPE_CHECKING
from typing import cast

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from pqnstack.app.api.deps import ClientDep
from pqnstack.app.core.config import settings
from pqnstack.app.core.config import state
from pqnstack.constants import BasisBool
from pqnstack.constants import QKDEncodingBasis
from pqnstack.network.client import Client

if TYPE_CHECKING:
    from pqnstack.base.instrument import RotatorInstrument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qkd", tags=["qkd"])


async def _qkd(
    follower_node_address: str,
    http_client: ClientDep,
    timetagger_address: str | None = None,
) -> list[int]:
    logger.debug("Starting QKD")
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)
    hwp = cast("RotatorInstrument", client.get_device(settings.qkd_settings.hwp[0], settings.qkd_settings.hwp[1]))

    if hwp is None:
        logger.error("Could not find half waveplate device")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    counts = []
    for basis in state.qkd_basis_list:
        r = await http_client.post(f"http://{follower_node_address}/qkd/single_bit")

        if r.status_code != status.HTTP_200_OK:
            logger.error("Failed to handshake with follower: %s", r.text)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to handshake with follower",
            )
        logger.debug("Handshake with follower successful")

        int_choice = secrets.randbits(1)  # FIXME: Make this real quantum random.
        logger.debug("Chosen integer choice: %s", int_choice)
        state.qkd_bit_list.append(int_choice)
        hwp.move_to(basis.angles[int_choice].value)
        logger.debug("Moving half waveplate to angle: %s", basis.angles[int_choice].value)

        count_ret = await http_client.get(
            f"http://{timetagger_address}/timetagger/measure_correlation?integration_time_s={settings.chsh_settings.measurement_config.integration_time_s}&coincidence_window_ps={settings.chsh_settings.measurement_config.binwidth_ps}&channel1={settings.chsh_settings.measurement_config.channel1}&channel2={settings.chsh_settings.measurement_config.channel2}&dark_count={settings.chsh_settings.measurement_config.dark_count}"
        )
        if count_ret.status_code != status.HTTP_200_OK:
            logger.error("Failed to get correlation from timetagger: %s", count_ret.text)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get correlation from timetagger",
            )

        c = cast("int", count_ret.json())
        counts.append(c)
        logger.debug("Counted %d coincidences", c)

    def get_outcome(state: int, basis: int, choice: int, counts: int) -> int:
        above = counts > settings.qkd_settings.discriminating_threshold
        return ((int(above) ^ choice) ^ (1 - state)) ^ basis

    outcome = []
    logger.debug(
        "Going for qkd_basis_list: %s, qkd_bit_list: %s, counts: %s", state.qkd_basis_list, state.qkd_bit_list, counts
    )
    for basis, choice, count in zip(state.qkd_basis_list, state.qkd_bit_list, counts, strict=False):
        out = get_outcome(settings.bell_state.value, BasisBool[basis.name].value, choice, count)
        logger.debug(
            "Calculating outcome for basis: %s, choice: %s, count: %s, outcome: %s", basis.name, choice, count, out
        )
        outcome.append(out)

    basis_list = [basis.name for basis in state.qkd_basis_list]

    # FIXME: Send already binary basis instead of HV/AD.
    r = await http_client.post(f"http://{follower_node_address}/qkd/request_basis_list", json=basis_list)
    if r.status_code != status.HTTP_200_OK:
        logger.error("Failed to request basis list from follower: %s", r.text)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request basis list from follower",
        )
    follower_basis_list = r.json()

    index_list = [i for i in range(len(follower_basis_list)) if follower_basis_list[i] == basis_list[i]]
    final_bits = [outcome[i] for i in index_list]

    logger.info("Final bits: %s", final_bits)

    return final_bits


@router.post("")
async def qkd(
    follower_node_address: str,
    http_client: ClientDep,
    timetagger_address: str | None = None,
) -> list[int]:
    """Perform a QKD protocol with the given follower node."""
    if not state.qkd_basis_list:
        logger.error("QKD basis list is empty")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QKD basis list is empty",
        )

    return await _qkd(follower_node_address, http_client, timetagger_address)


@router.post("/single_bit")
async def request_qkd_single_pass() -> bool:
    client = Client(host=settings.router_address, port=settings.router_port, timeout=600_000)
    hwp = cast(
        "RotatorInstrument",
        client.get_device(settings.qkd_settings.request_hwp[0], settings.qkd_settings.request_hwp[1]),
    )

    if hwp is None:
        logger.error("Could not find half waveplate device")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    logger.debug("Halfwaveplate device found: %s", hwp)

    _bases = (QKDEncodingBasis.HV, QKDEncodingBasis.DA)
    basis_choice = _bases[secrets.randbits(1)]  # FIXME: Make this real quantum random.
    int_choice = secrets.randbits(1)  # FIXME: Make this real quantum random.

    state.qkd_request_basis_list.append(basis_choice)
    state.qkd_request_bit_list.append(int_choice)
    angle = basis_choice.angles[int_choice].value

    hwp.move_to(angle)

    return True


@router.post("/request_basis_list")
def request_qkd_basis_list(leader_basis_list: list[str]) -> list[str]:
    """Return the list of basis angles for QKD."""
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
    state.qkd_request_bit_list.clear()

    return ret
