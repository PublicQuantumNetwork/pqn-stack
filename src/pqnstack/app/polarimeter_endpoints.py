from fastapi import APIRouter
import threading
from pqnstack.app.settings import settings
import os

router = APIRouter()

@router.get("/polarimeter/theta")
async def get_theta():
    return {"theta": settings.polarimeter_theta}

def update_theta_terminal(settings_obj):
    while True:
        try:
            new_value = input("\nEnter new theta value: ")
            settings_obj.polarimeter_theta = float(new_value)
            print(f"Theta updated to {settings_obj.polarimeter_theta}")
        except EOFError:
            return
        except ValueError:
            print("Invalid value, please enter a number.")
            continue

def is_reloader():
    return os.environ.get("RUN_MAIN") == "true" or os.environ.get("UVICORN_RELOAD") == "true"

if not is_reloader():
    input_thread = threading.Thread(target=update_theta_terminal, args=(settings,), daemon=True)
    input_thread.start()

