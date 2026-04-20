from fastapi import APIRouter

from pqn_node.api.routes import chsh
from pqn_node.api.routes import coordination
from pqn_node.api.routes import debug
from pqn_node.api.routes import games
from pqn_node.api.routes import health
from pqn_node.api.routes import qkd
from pqn_node.api.routes import rng
from pqn_node.api.routes import serial
from pqn_node.api.routes import timetagger

api_router = APIRouter()
api_router.include_router(chsh.router)
api_router.include_router(qkd.router)
api_router.include_router(timetagger.router)
api_router.include_router(rng.router)
api_router.include_router(serial.router)
api_router.include_router(coordination.router)
api_router.include_router(debug.router)
api_router.include_router(games.router)
api_router.include_router(health.router)
