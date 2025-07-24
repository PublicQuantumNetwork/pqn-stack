import threading
from fastapi import APIRouter
from pqnstack.app.settings import settings

router = APIRouter()

@router.get("/polarimeter/theta")
async def get_theta() -> dict[str, float]:
    return {"theta": settings.polarimeter_theta}

def update_theta_terminal(settings_obj) -> None:
    while True:
        try:
            new_value = input("\nEnter new theta value: ")
            settings_obj.polarimeter_theta = float(new_value)
            print(f"Theta updated to {settings_obj.polarimeter_theta}")
        except ValueError:
            print("Invalid value, please enter a number.")
            continue

input_thread = threading.Thread(target=update_theta_terminal, args=(settings,), daemon=True)
input_thread.start()

