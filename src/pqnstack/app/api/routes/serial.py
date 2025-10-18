import logging
import threading
from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel

from pqnstack.app.core.config import settings
from pqnstack.pqn.drivers.rotaryencoder import SerialRotaryEncoder

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/serial", tags=["measure"])


class MockRotaryEncoder:
    """Mock rotary encoder for terminal input when hardware is not available."""

    def __init__(self) -> None:
        self.theta = 0.0

    def read(self) -> float:
        return self.theta


def update_theta_terminal(mock_encoder: MockRotaryEncoder) -> None:
    while True:
        try:
            new_value = input("\nEnter new theta value: ")
            mock_encoder.theta = float(new_value)
            logger.info("Theta updated to %s", mock_encoder.theta)
        except ValueError:
            logger.info("Invalid value, please enter a number.")
            continue


def get_rotary_encoder() -> SerialRotaryEncoder | MockRotaryEncoder:
    if settings.rotary_encoder is None:
        if settings.virtual_rotator:
            # Virtual rotator mode enabled, use mock with terminal input
            logger.info("Virtual rotator mode enabled, using terminal input")
            mock_encoder = MockRotaryEncoder()
            input_thread = threading.Thread(target=update_theta_terminal, args=(mock_encoder,), daemon=True)
            input_thread.start()
            settings.rotary_encoder = mock_encoder
        else:
            # Use the real serial rotary encoder
            rotary_encoder = SerialRotaryEncoder(
                label="rotary_encoder", address=settings.rotary_encoder_address, offset_degrees=0.0
            )
            settings.rotary_encoder = rotary_encoder

    return settings.rotary_encoder


SERDep = Annotated[SerialRotaryEncoder | MockRotaryEncoder, Depends(get_rotary_encoder)]


class AngleResponse(BaseModel):
    theta: float


@router.get("/")
async def read_angle(rotary_encoder: SERDep) -> AngleResponse:
    return AngleResponse(theta=rotary_encoder.read())
