import logging
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from pqnstack.app.core.config import settings
from pqnstack.pqn.drivers.rotaryencoder import SerialRotaryEncoder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/serial", tags=["measure"])


def get_rotary_encoder() -> SerialRotaryEncoder:
    return settings.rotary_encoder


SERDep = Annotated[SerialRotaryEncoder, Depends(get_rotary_encoder)]


class AngleResponse(BaseModel):
    theta: float


@router.get("/")
async def read_angle(rotary_encoder: SERDep) -> AngleResponse:
    return AngleResponse(theta=rotary_encoder.read())
