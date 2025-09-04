import logging
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, HTTPException, status

from pqnstack.app.api.deps import ClientDep
from pqnstack.app.core.config import state, state_change_event, settings, user_replied_event

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/coordination", tags=["coordination"])


@router.post("/collect_follower")
async def collect_follower(address: str, http_client: ClientDep) -> bool:

    logger.info("Requesting client at %s to follow", address)

    ret = await http_client.post(f"http://{address}/coordination/follow_requested?leaders_name={settings.node_name}")
    if ret.status_code != 200:
        raise HTTPException(status_code=ret.status_code, detail=ret.text)


    if ret.json() is True:
        state.leading = True
        state.followers_address = address
        logger.info("Successfully collected follower")
        return True
    if ret.json() is False:
        logger.info("Follower rejected follow request")
        return False

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR , detail="Could not collect follower for unknown reasons")


@router.post('/follow_requested')
async def follow_requested(request: Request, leaders_name: str) -> bool:

    logger.info("Requesting client at %s to follow", leaders_name)
    print("state.client_listening", state.client_listening_for_follower_requests)
    print("state.following", state.following)
    # Check if the client is ready to accept a follower request and that node is not already following someone.
    if state.client_listening_for_follower_requests and not state.following:

        # Load the state with the incoming info of the request
        state.leaders_address = request.client.host
        state.leaders_name = leaders_name
        state.following_requested = True
        # Trigger the state change to get the websocket to send question to user
        state_change_event.set()

        logger.info("Asking user to accept follow request from %s (%s)", leaders_name, request.client.host)
        await user_replied_event.wait()  # Wait for a state change event to see if user accepted
        user_replied_event.clear()  # Reset the event for the next change
        if state.following_requested_user_response:
            logger.info(f"Follow request from {request.client.host} accepted.")
            state.client_listening_for_follower_requests = True
            state.following = True
            state.leaders_address = request.client.host
            state_change_event.set()
            return True

        logger.info(f"Follow request from {request.client.host} rejected.")
        # Clean up the state if user rejected
        state.leaders_address = None
        state.leaders_name = None
        state.following_requested = False

    else:
        logger.info("Request rejected because %s", ("client is not listening for requests" if state.client_listening_for_follower_requests else "this node is already following someone"))

    return False


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    A simple websocket endpoint that accepts a connection, receives messages,
    and sends a response back.
    """
    from pqnstack.app.core.config import state, state_change_event
    await websocket.accept()
    logger.info("Client connected to websocket for multiplayer coordination.")
    state.client_listening_for_follower_requests = True

    async def state_change_handler():
        while True:
            await state_change_event.wait()  # Wait for a state change event
            if state.following_requested:
                logger.debug("Websocket detected a follow request, asking user for response.")
                await websocket.send_text(f"Do you want to accept a connection from {state.leaders_name} ({state.leaders_address})?")
            state_change_event.clear()  # Reset the event for the next change

    state_change_task = asyncio.create_task(state_change_handler())

    try:
        while True:
            response = await websocket.receive_text()
            state.following_requested_user_response = response.lower() in ["true", "yes", "y"]
            state.following_requested = False
            logger.debug("Websocket received a response from user: %s", state.following_requested_user_response)
            user_replied_event.set()

    except WebSocketDisconnect:
        logger.info("Client disconnected from websocket for multiplayer coordination.")
        state.client_listening_for_follower_requests = False
    finally:
        state_change_task.cancel()