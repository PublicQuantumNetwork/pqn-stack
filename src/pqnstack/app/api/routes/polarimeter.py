import logging
import threading

from fastapi import APIRouter

from pqnstack.app.api.deps import StateDep
from pqnstack.app.core.config import NodeState
from pqnstack.app.core.config import state as st

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/polarimeter/theta")
async def get_theta(state: StateDep) -> dict[str, float]:
    return {"theta": state.polarimeter_theta}


def update_theta_terminal(state_obj: NodeState) -> None:
    while True:
        try:
            new_value = input("\nEnter new theta value: ")
            state_obj.polarimeter_theta = float(new_value)
            logger.info("Theta updated to %s", state_obj.polarimeter_theta)
        except ValueError:
            logger.info("Invalid value, please enter a number.")
            continue


input_thread = threading.Thread(target=update_theta_terminal, args=(st,), daemon=True)
input_thread.start()
