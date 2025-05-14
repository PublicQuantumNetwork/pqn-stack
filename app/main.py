import logging
import secrets
from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from typing import Literal

import httpx
import jinja_partials
from fastapi import Depends
from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from starlette.templating import _TemplateResponse

logger = logging.getLogger("__file__")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    PROJECT_NAME: str = "Public Quantum Network"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
SettingsDep = Annotated[Settings, Depends(get_settings)]


class NodeState(BaseModel):
    waveplates_available: bool = False
    chsh_basis: list[float] = [0, 45]


_state = NodeState()


def get_state() -> NodeState:
    return _state


StateDep = Annotated[NodeState, Depends(get_state)]


app = FastAPI(
    title=settings.PROJECT_NAME,
)
app.mount("/static", StaticFiles(directory=f"{Path(__file__).parent}/static"), name="static")


@lru_cache
def get_templates() -> Jinja2Templates:
    return Jinja2Templates(directory=f"{Path(__file__).parent}/templates")


templates = get_templates()
TemplatesDep = Annotated[Jinja2Templates, Depends(get_templates)]
jinja_partials.register_starlette_extensions(templates)


@app.get("/", response_class=HTMLResponse)
def root(request: Request, templates: TemplatesDep, settings: SettingsDep) -> _TemplateResponse:
    ctx = {"protocols": ["chsh", "qkd", "qpv"]}
    return templates.TemplateResponse(request=request, name="home/index.html", context=ctx)


@app.get("/protocols/{name}", response_class=HTMLResponse)
def protocol(name: str, request: Request, templates: TemplatesDep, settings: SettingsDep) -> _TemplateResponse:
    ctx = {"protocol_name": name, "description": f"a description of the {name} protocol"}
    return templates.TemplateResponse(request=request, name="home/protocols.html", context=ctx)


# @app.get("/ping")
# def ping(target, other_arg):
#     return f"would ping {target}"
#
#
# def peers() -> list[Node]:
#     """Return nodes directly connected by quantum link"""
#
#
# def network_map(range: int):
#     """Return a full network map of all nodes within `range` hops"""


# @lru_cache
# def get_instruments() -> dict[Instrument]:
#     # query local hardware
#     ...


def get_instruments() -> set[str]:
    return {"hwp", "qwp", "ttag"}


instruments = get_instruments()
InstrumentDep = Annotated[set[str], Depends(get_instruments)]


async def get_http_client() -> Generator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as client:
        yield client


ClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


@app.get("/chsh")
# async def chsh(basis, other_node, measurement_config, local_instruments: InstrumentDep, client: ClientDep):  # type: ignore[no-untyped-def]
async def chsh(a1: float, a2: float, other_node, client: ClientDep):  # type: ignore[no-untyped-def]
    """We assume the party with the timetagger runs this function."""
    basis = [a1, a2]
    # Initialize and set first angle
    r = await client.get(f"{other_node}/request/chsh")
    c = r.status_code
    if c != 200:
        return f"got status code {c}"

    expectations = []
    for angle in basis:
        # measure ab, a'b, ab', a'b' for one expectation value
        counts = []
        for a in [angle, angle + 90]:
            # local_instruments.hwp.move_to(a)
            # TODO:
            logger.info("moving waveplate", extra={"angle": a})

            for i in range(2):
                for perp in [False, True]:
                    r = await client.get(f"{other_node}/request/basis?i={i}&perp={perp}")
                    # count = local_instruments.measure(measurement_config)
                    count = 5
                    # TODO:
                    logger.info("measuring counts")
                    counts.append(count)

        # TODO:
        # expectation = compute_expectation(counts)
        expectation = sum(counts)
        expectations.append(expectation)

    # chsh_result = compute_chsh(expectations)
    chsh_result = sum(expectations)

    await client.get(f"{other_node}/request/complete?data={chsh_result}")

    return chsh_result


@app.get("/request/chsh")  # type: ignore[misc]
async def request_chsh(local_instruments: InstrumentDep, state: StateDep) -> bool:
    """Only called by other nodes, not from local frontend."""
    if not state.waveplates_available:
        return False

    state.waveplates_available = False
    state.chsh_basis = [-22.5, 22.5]

    # TODO:
    # local_instruments.prepare_local(basis[0])
    logger.info("moving waveplate", extra={"angle": state.chsh_basis[0]})

    return True


@app.get("/request/basis")  # type: ignore[misc]
async def request_basis(i: int, perp: bool, local_instruments: InstrumentDep, state: StateDep) -> bool:
    angle = state.chsh_basis[i] + 90 * perp
    # TODO:
    logger.info("moving waveplate", extra={"angle": angle})
    return True


@app.get("/request/complete")  # type: ignore[misc]
async def request_complete(data: dict[str, Any], state: StateDep) -> bool:
    logger.info("request complete", extra=data)
    # TODO: maybe do something else with `data`
    state.waveplates_available = True
    return True


#
# async def supports(p: NetworkProtocol) -> bool:
#     return false
#
#
# # app.include_router(api_router, prefix=settings.API_V1_STR)
# # app.include_router(view_router)
