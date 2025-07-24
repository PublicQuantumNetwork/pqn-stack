import logging

from fastapi import FastAPI

from pqnstack.app.chsh_endpoints import router as chsh_router
from pqnstack.app.qkd_endpoints import router as qkd_router
from pqnstack.app.timetagger_endpoints import router as timetagger_router

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

app.include_router(chsh_router)
app.include_router(qkd_router)
app.include_router(timetagger_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Hello World"}
