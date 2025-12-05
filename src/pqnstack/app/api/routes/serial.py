import logging
from typing import Annotated
from typing import cast

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from pqnstack.app.core.config import settings
from pqnstack.pqn.drivers.rotaryencoder import MockRotaryEncoder
from pqnstack.pqn.drivers.rotaryencoder import RotaryEncoderInstrument
from pqnstack.pqn.drivers.rotaryencoder import SerialRotaryEncoder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/serial", tags=["measure"])


def get_rotary_encoder() -> RotaryEncoderInstrument:
    if settings.rotary_encoder is None:
        if settings.virtual_rotator:
            # Virtual rotator mode enabled, use mock with terminal input
            logger.info("Virtual rotator mode enabled")
            mock_encoder = MockRotaryEncoder()
            settings.rotary_encoder = mock_encoder
        else:
            # Use the real serial rotary encoder
            rotary_encoder = SerialRotaryEncoder(
                label="rotary_encoder", address=settings.rotary_encoder_address, offset_degrees=0.0
            )
            settings.rotary_encoder = rotary_encoder

    return settings.rotary_encoder


SERDep = Annotated[RotaryEncoderInstrument, Depends(get_rotary_encoder)]


class AngleResponse(BaseModel):
    theta: float


@router.get("/")
async def read_angle(rotary_encoder: SERDep) -> AngleResponse:
    return AngleResponse(theta=rotary_encoder.read())


@router.post("/debug_set_angle")
async def debug_set_angle(rotary_encoder: SERDep, angle: float) -> AngleResponse:
    try:
        rotary_encoder = cast("MockRotaryEncoder", rotary_encoder)
        rotary_encoder.theta = angle
    except AttributeError:
        logger.exception("Attempted to set angle on non-mock rotary encoder")
        raise

    logger.info("Debug: Theta set to %s", rotary_encoder.theta)
    return AngleResponse(theta=rotary_encoder.read())
