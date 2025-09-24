import asyncio
import logging

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from fastapi import status
from pydantic import BaseModel

from pqnstack.app.api.deps import ClientDep
from pqnstack.app.api.deps import StateDep
from pqnstack.app.core.config import ask_user_for_follow_event
from pqnstack.app.core.config import settings
from pqnstack.app.core.config import user_replied_event

logger = logging.getLogger(__name__)


class FollowRequestResponse(BaseModel):
    accepted: bool


class CollectFollowerResponse(BaseModel):
    success: bool


class ResetCoordinationStateResponse(BaseModel):
    message: str = "Coordination state reset successfully"


router = APIRouter(prefix="/coordination", tags=["coordination"])


# TODO: Send a disconnection message if I was following someone.
@router.post("/reset_coordination_state")
async def reset_coordination_state(state: StateDep) -> ResetCoordinationStateResponse:
    """Reset the coordination state of the node."""
    state.leading = False
    state.followers_address = ""
    state.following = False
    state.following_requested = False
    state.following_requested_user_response = None
    state.leaders_address = ""
    state.leaders_name = ""
    return ResetCoordinationStateResponse()


@router.post("/collect_follower")
async def collect_follower(address: str, state: StateDep, http_client: ClientDep) -> CollectFollowerResponse:
    """
    Endpoint called by a leader node (this one) to request a follower node (other node) to follow it.

    Returns
    -------
        CollectFollowerResponse indicating if the follower accepted the request.
    """
    logger.info("Requesting client at %s to follow", address)

    ret = await http_client.post(f"http://{address}/coordination/follow_requested?leaders_name={settings.node_name}")
    if ret.status_code != status.HTTP_200_OK:
        raise HTTPException(status_code=ret.status_code, detail=ret.text)

    response_data = ret.json()
    if response_data.get("accepted") is True:
        state.leading = True
        state.followers_address = address
        logger.info("Successfully collected follower")
        return CollectFollowerResponse(success=True)
    if response_data.get("accepted") is False:
        logger.info("Follower rejected follow request")
        return CollectFollowerResponse(success=False)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not collect follower for unknown reasons"
    )


@router.post("/follow_requested")
async def follow_requested(request: Request, leaders_name: str, state: StateDep) -> FollowRequestResponse:
    """
    Endpoint is called by a leader node (other node) to request this node to follow it.

    Returns
    -------
        FollowRequestResponse indicating if the follow request is accepted.
    """
    logger.debug("Requesting client at %s to follow", leaders_name)

    if request.client is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request lacks the clients host")
    leaders_address = request.client.host

    # Check if the client is ready to accept a follower request and that node is not already following someone.
    if not state.client_listening_for_follower_requests and state.following:
        logger.info(
            "Request rejected because %s",
            (
                "client is not listening for requests"
                if not state.client_listening_for_follower_requests
                else "this node is already following someone"
            ),
        )
        return FollowRequestResponse(accepted=False)

    state.following_requested = True
    state.leaders_name = leaders_name
    state.leaders_address = leaders_address
    # Trigger the state change to get the websocket to send question to user
    ask_user_for_follow_event.set()

    logger.debug("Asking user to accept follow request from %s (%s)", leaders_name, leaders_address)
    await user_replied_event.wait()  # Wait for a state change event to see if user accepted
    user_replied_event.clear()  # Reset the event for the next change
    if state.following_requested_user_response:
        logger.debug("Follow request from %s accepted.", leaders_address)
        state.following = True
        state.leaders_name = leaders_name
        state.leaders_address = leaders_address
        return FollowRequestResponse(accepted=True)

    logger.debug("Follow request from %s rejected.", leaders_address)
    # Clean up the state if user rejected
    state.leaders_address = ""
    state.leaders_name = ""
    state.following_requested = False
    return FollowRequestResponse(accepted=False)


@router.websocket("/follow_requested_alerts")
async def follow_requested_alert(websocket: WebSocket, state: StateDep) -> None:
    """Websocket endpoint is used to alert the client when a follow request is received. It also handles the response from the client."""
    await websocket.accept()
    logger.info("Client connected to websocket for multiplayer coordination.")
    state.client_listening_for_follower_requests = True

    async def ask_user_for_follow_handler() -> None:
        """Task that waits for the ask_user_for_follow_event event and sends a message to the client if a follow request is detected."""
        while True:
            try:
                await ask_user_for_follow_event.wait()  # Wait for a state change event
                if state.following_requested:
                    logger.debug("Websocket detected a follow request, asking user for response.")
                    try:
                        await websocket.send_text(
                            f"Do you want to accept a connection from {state.leaders_name} ({state.leaders_address})?"
                        )
                    except RuntimeError as e:
                        if "websocket.close" in str(e) or "response already completed" in str(e):
                            logger.debug("WebSocket already closed, cannot send message")
                            break
                        raise
                ask_user_for_follow_event.clear()  # Reset the event for the next change
            except Exception as e:
                logger.error("Error in ask_user_for_follow_handler: %s", e)
                break

    async def client_message_handler() -> None:
        """Task that waits for a message from the client and handles the response. It also handles the case where the client disconnects."""
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

    state_change_task = asyncio.create_task(ask_user_for_follow_handler())
    client_message_task = asyncio.create_task(client_message_handler())

    try:
        await asyncio.gather(state_change_task, client_message_task)
    finally:
        state_change_task.cancel()
        client_message_task.cancel()
