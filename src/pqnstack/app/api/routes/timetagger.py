import logging

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status

from pqnstack.app.core.config import settings
from pqnstack.network.client import Client
from pqnstack.pqn.protocols.measurement import MeasurementConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/timetagger", tags=["timetagger"])


@router.get("/measure")
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
