import logging
from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends
from fastapi import FastAPI
from fastapi import status
from pydantic import BaseModel

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app = FastAPI()


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient() as client:
        yield client


ClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


class NodeState(BaseModel):
    waveplates_available: bool = False
    chsh_basis: list[float] = [0.0, 45.0]


state = NodeState()


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}


@app.post("/chsh")
async def chsh(basis: tuple[float, float], other_node_address: str, http_client: ClientDep) -> dict[str, str] | int:
    logger.debug("Starting CHSH")
    expectations = []
    for angle in basis:
        # measure ab, a'b, ab', a'b' for one expectation value
        counts = []
        for a in [angle, angle + 90]:
            # local_instruments.hwp.move_to(a)  # ruff: noqa: ERA001
            logger.info("moving waveplate", extra={"angle": a})

            for i in range(2):
                for perp in [False, True]:
                    r = await http_client.get(
                        f"http://{other_node_address}/chsh/request-angle-by-basis?i={i}&perp={perp}"
                    )

                    # TODO: Handle other status codes
                    if r.status_code != status.HTTP_200_OK:
                        logger.error("Failed to request follower: %s", r.text)
                        return {"error": "Failed to request follower"}
                    # count = local_instruments.measure(measurement_config)  # ruff: noqa: ERA001
                    count = 1
                    logger.info("measuring counts, %s", count)
                    counts.append(count)

        # expectation = compute_expectation(counts)  # ruff: noqa: ERA001
        expectation = sum(counts)
        expectations.append(expectation)

    # chsh_result = compute_chsh(expectations)  # ruff: noqa: ERA001
    return sum(expectations)


@app.post("/chsh/request-angle-by-basis")
async def request_angle_by_basis(index: int, *, perp: bool = False) -> bool:
    angle = state.chsh_basis[index] + 90 * perp
    logger.info("moving waveplate", extra={"angle": angle})
    return True
