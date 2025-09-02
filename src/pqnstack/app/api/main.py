from fastapi import APIRouter

from pqnstack.app.api.routes import chsh
from pqnstack.app.api.routes import qkd
from pqnstack.app.api.routes import rng
from pqnstack.app.api.routes import serial
from pqnstack.app.api.routes import timetagger
from pqnstack.app.api.routes import websocket
from pqnstack.app.api.routes import handshake

api_router = APIRouter()
api_router.include_router(chsh.router)
api_router.include_router(qkd.router)
api_router.include_router(timetagger.router)
api_router.include_router(rng.router)
api_router.include_router(serial.router)
api_router.include_router(websocket.router)
api_router.include_router(handshake.router)