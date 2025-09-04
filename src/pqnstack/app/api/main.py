from fastapi import APIRouter

from pqnstack.app.api.routes import chsh
from pqnstack.app.api.routes import qkd
from pqnstack.app.api.routes import rng
from pqnstack.app.api.routes import serial
from pqnstack.app.api.routes import timetagger
from pqnstack.app.api.routes import coordination
from pqnstack.app.api.routes import debug

api_router = APIRouter()
api_router.include_router(chsh.router)
api_router.include_router(qkd.router)
api_router.include_router(timetagger.router)
api_router.include_router(rng.router)
api_router.include_router(serial.router)
api_router.include_router(coordination.router)
api_router.include_router(debug.router)