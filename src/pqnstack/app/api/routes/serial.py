import logging
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from pqnstack.app.core.config import settings
from pqnstack.pqn.drivers.rotaryencoder import SerialRotaryEncoder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/serial", tags=["measure"])


_rotary_encoder: SerialRotaryEncoder | None = None

def get_rotary_encoder() -> SerialRotaryEncoder:
    global _rotary_encoder
    if _rotary_encoder is None:
        rotary_encoder = SerialRotaryEncoder(
            label="rotary_encoder", address=settings.rotary_encoder_address, offset_degrees=0.0
        )
        _rotary_encoder = rotary_encoder

    return _rotary_encoder


SERDep = Annotated[SerialRotaryEncoder, Depends(get_rotary_encoder)]


class AngleResponse(BaseModel):
    theta: float


@router.get("/")
async def read_angle(rotary_encoder: SERDep) -> AngleResponse:
    return AngleResponse(theta=rotary_encoder.read())
