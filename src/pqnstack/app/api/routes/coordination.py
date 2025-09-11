import asyncio
import logging

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi import status

from pqnstack.app.api.deps import ClientDep
from pqnstack.app.api.deps import CoordinationStateDep
from pqnstack.app.core.config import ask_user_for_follow_event
from pqnstack.app.core.config import settings
from pqnstack.app.core.config import user_replied_event

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/coordination", tags=["coordination"])


# TODO: Send a disconnection message if I was following someone.
@router.post("/reset_coordination_state")
async def reset_coordination_state(coord: CoordinationStateDep) -> None:
    """Reset the coordination state of the node."""
    coord.leading = False
    coord.followers_address = ""
    coord.following = False
    coord.following_requested = False
    coord.following_requested_user_response = None
    coord.leaders_address = ""
    coord.leaders_name = ""


@router.post("/collect_follower")
async def collect_follower(address: str, coord: CoordinationStateDep, http_client: ClientDep) -> bool:
    """
    Endpoint called by a leader node (this one) to request a follower node (other node) to follow it.

    Returns
    -------
        True if the follower accepted the request, False otherwise.
    """
    logger.info("Requesting client at %s to follow", address)

    ret = await http_client.post(f"http://{address}/coordination/follow_requested?leaders_name={settings.node_name}")
    if ret.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=ret.status_code, detail=ret.text)

    if ret.json() is True:
        coord.leading = True
        coord.followers_address = address
        logger.info("Successfully collected follower")
        return True
    if ret.json() is False:
        logger.info("Follower rejected follow request")
        return False

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not collect follower for unknown reasons"
    )


@router.post("/follow_requested")
async def follow_requested(request: Request, leaders_name: str, coord: CoordinationStateDep) -> bool:
    """
    Endpoint is called by a leader node (other node) to request this node to follow it.

    Returns
    -------
        True if the follow request is accepted, False otherwise.
    """
    logger.debug("Requesting client at %s to follow", leaders_name)

    if request.client is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request lacks the clients host")
    leaders_address = request.client.host

    # Check if the client is ready to accept a follower request and that node is not already following someone.
    if coord.client_listening_for_follower_requests and not coord.following:
        coord.following_requested = True
        coord.leaders_name = leaders_name
        coord.leaders_address = leaders_address
        # Trigger the state change to get the websocket to send question to user
        ask_user_for_follow_event.set()

        logger.debug("Asking user to accept follow request from %s (%s)", leaders_name, leaders_address)
        await user_replied_event.wait()  # Wait for a state change event to see if user accepted
        user_replied_event.clear()  # Reset the event for the next change
        if coord.following_requested_user_response:
            logger.debug("Follow request from %s accepted.", leaders_address)
            coord.following = True
            coord.leaders_name = leaders_name
            coord.leaders_address = leaders_address
            ask_user_for_follow_event.set()
            return True

        logger.debug("Follow request from %s rejected.", leaders_address)
        # Clean up the state if user rejected
        coord.leaders_address = ""
        coord.leaders_name = ""
        coord.following_requested = False

    else:
        logger.info(
            "Request rejected because %s",
            (
                "client is not listening for requests"
                if coord.client_listening_for_follower_requests
                else "this node is already following someone"
            ),
        )

    return False


@router.websocket("/follow_requested_alerts")
async def follow_requested_alert(websocket: WebSocket, coord: CoordinationStateDep) -> None:
    """Websocket endpoint is used to alert the client when a follow request is received. It also handles the response from the client."""
    await websocket.accept()
    logger.info("Client connected to websocket for multiplayer coordination.")
    coord.client_listening_for_follower_requests = True

    async def ask_user_for_follow_handler() -> None:
        """Task that waits for the ask_user_for_follow_event event and sends a message to the client if a follow request is detected."""
        while True:
            await ask_user_for_follow_event.wait()  # Wait for a state change event
            if coord.following_requested:
                logger.debug("Websocket detected a follow request, asking user for response.")
                await websocket.send_text(
                    f"Do you want to accept a connection from {coord.leaders_name} ({coord.leaders_address})?"
                )
            ask_user_for_follow_event.clear()  # Reset the event for the next change

    async def client_message_handler() -> None:
        """Task that waits for a message from the client and handles the response. It also handles the case where the client disconnects."""
        try:
            while True:
                response = await websocket.receive_text()
                coord.following_requested_user_response = response.lower() in ["true", "yes", "y"]
                coord.following_requested = False
                logger.debug("Websocket received a response from user: %s", coord.following_requested_user_response)
                user_replied_event.set()
        except WebSocketDisconnect:
            logger.info("Client disconnected from websocket for multiplayer coordination.")
            coord.client_listening_for_follower_requests = False

    state_change_task = asyncio.create_task(ask_user_for_follow_handler())
    client_message_task = asyncio.create_task(client_message_handler())

    try:
        await asyncio.gather(state_change_task, client_message_task)
    finally:
        state_change_task.cancel()
        client_message_task.cancel()
