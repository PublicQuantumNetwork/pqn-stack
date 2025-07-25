import logging

from fastapi import FastAPI

from pqnstack.app.api.main import api_router

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Public Quantum Network",
)

app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}
