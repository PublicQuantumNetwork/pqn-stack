import os
import threading

from fastapi import APIRouter

from pqnstack.app.core.config import settings
from pqnstack.pqn.drivers.rotaryencoder import SerialRotaryEncoder

router = APIRouter()

dev = SerialRotaryEncoder(label = "name", address = "/dev/ttyACM0")

@router.get("/polarimeter/theta")
async def get_theta():
    return {"theta": dev.read()}


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


def update_theta_rotary(settings_obj):
    dev = SerialRotaryEncoder(label = "name", address = "/dev/ttyACM0")
    while True:
        try:
            settings_obj.polarimeter_theta = float(dev.read())
            print(f"\r Theta updated to {settings_obj.polarimeter_theta:6.2f}", flush=True, end="")
        except EOFError:
            return
        except ValueError:
            print("Invalid value, please enter a number.")
            continue


def is_reloader():
    return os.environ.get("RUN_MAIN") == "true" or os.environ.get("UVICORN_RELOAD") == "true"

"""
if not is_reloader():
    try:
        input_thread_pol = threading.Thread(target=update_theta_rotary, args=(settings,), daemon=True)
        input_thread_pol.start()
    except:
        input_thread = threading.Thread(target=update_theta_terminal, args=(settings,), daemon=True)
        input_thread.start()
"""
