import logging
from typing import TYPE_CHECKING
from typing import cast

from fastapi import APIRouter
from pydantic import BaseModel

from pqnstack.app.api.deps import SERDep

if TYPE_CHECKING:
    from pqnstack.pqn.drivers.rotaryencoder import MockRotaryEncoder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/serial", tags=["measure"])


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
