import logging
import random

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from pqnstack.app.api.deps import ClientDep
from pqnstack.app.core.config import settings
from pqnstack.app.core.config import state
from pqnstack.app.core.models import get_timetagger
from pqnstack.app.core.models import measure_correlation
from pqnstack.constants import BasisBool
from pqnstack.constants import QKDEncodingBasis
from pqnstack.network.client import Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qkd", tags=["qkd"])


async def _qkd(
    follower_node_address: str,
    http_client: ClientDep,
    timetagger_address: str | None = None,
) -> list[int]:
    logger.debug("Starting QKD")
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
        tagger = get_timetagger(client)

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

        int_choice = random.randint(0, 1)  # FIXME: Make this real quantum random.
        logger.debug("Chosen integer choice: %s", int_choice)
        state.qkd_bit_list.append(int_choice)
        assert hasattr(hwp, "move_to")
        hwp.move_to(basis.angles[int_choice].value)
        logger.debug("Moving half waveplate to angle: %s", basis.angles[int_choice].value)
        count = await measure_correlation(
            settings.qkd_settings.measurement_config, tagger, timetagger_address, http_client
        )
        logger.debug("Counted %d coincidences", count)
        counts.append(count)

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
    hwp = client.get_device(settings.qkd_settings.request_hwp[0], settings.qkd_settings.request_hwp[1])

    if hwp is None:
        logger.error("Could not find half waveplate device")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not find half waveplate device",
        )

    logger.debug("Halfwaveplate device found: %s", hwp)
    assert hasattr(hwp, "move_to")

    basis_choice = random.choices([QKDEncodingBasis.HV, QKDEncodingBasis.DA])[
        0
    ]  # FIXME: Make this real quantum random.
    int_choice = random.randint(0, 1)  # FIXME: Make this real quantum random.

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
