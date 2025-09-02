from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    A simple websocket endpoint that accepts a connection, receives messages,
    and sends a response back.
    """
    from pqnstack.app.core.config import state, state_change_event
    await websocket.accept()
    await websocket.send_text("HELLO HELLO HELLO")
    try:
        while True:
            await state_change_event.wait()  # Wait for a state change event
            if state.incoming:
                await websocket.send_text("PING PING PING")
                state.incoming = False
                # To prevent sending this message in a loop, you might want to reset the state:

            state_change_event.clear()  # Reset the event for the next change
    except WebSocketDisconnect:
        print("Client disconnected")
