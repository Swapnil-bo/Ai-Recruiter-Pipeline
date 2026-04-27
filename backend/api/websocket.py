import json
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from backend.core.schemas import PipelineStatus
from backend.agents.orchestrator import orchestrator
from backend.resume.resume_store import resume_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


# ── Message Types ──────────────────────────────────────────────────────────────

MSG_PIPELINE_STATUS  = "pipeline_status"
MSG_ERROR            = "error"
MSG_CONNECTED        = "connected"
MSG_PING             = "ping"
MSG_PONG             = "pong"
MSG_START            = "start"
MSG_CANCEL           = "cancel"


# ── Connection Manager ─────────────────────────────────────────────────────────

class ConnectionManager:
    """
    Manages active WebSocket connections.
    Supports multiple simultaneous clients monitoring the same pipeline.
    """

    def __init__(self):
        self._active: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._active.append(ws)
        logger.info(f"[ws] Client connected. Active: {len(self._active)}")

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._active:
                self._active.remove(ws)
        logger.info(f"[ws] Client disconnected. Active: {len(self._active)}")

    async def send(self, ws: WebSocket, message: dict) -> bool:
        """
        Send a message to a single client.
        Returns False if send failed (client likely disconnected).
        """
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json(message)
                return True
        except Exception as e:
            logger.warning(f"[ws] Send failed: {e}")
        return False

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all connected clients."""
        async with self._lock:
            clients = list(self._active)

        dead: list[WebSocket] = []
        for ws in clients:
            success = await self.send(ws, message)
            if not success:
                dead.append(ws)

        # Clean up dead connections
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._active:
                        self._active.remove(ws)

    @property
    def client_count(self) -> int:
        return len(self._active)


manager = ConnectionManager()


# ── WebSocket Endpoint ─────────────────────────────────────────────────────────

@router.websocket("/ws/pipeline")
async def pipeline_websocket(ws: WebSocket):
    """
    WebSocket endpoint for real-time pipeline progress streaming.

    Protocol:
    ─────────────────────────────────────────────────────────────
    Client → Server messages:
      {"type": "start", "keywords": [...], "use_cache": true, "generate_cover_letters": true}
      {"type": "ping"}
      {"type": "cancel"}   (not yet implemented — future feature)

    Server → Client messages:
      {"type": "connected", "message": "..."}
      {"type": "pong"}
      {"type": "pipeline_status", "data": PipelineStatus}
      {"type": "error", "message": "..."}
    ─────────────────────────────────────────────────────────────

    Flow:
    1. Client connects
    2. Server sends "connected" handshake
    3. Client sends "start" with pipeline config
    4. Server streams "pipeline_status" updates in real time
    5. Final status has stage="done"
    6. Connection stays open for further commands
    """
    await manager.connect(ws)

    try:
        # ── Handshake ──────────────────────────────────────────────────────────
        await _send(ws, {
            "type": MSG_CONNECTED,
            "message": "Connected to AI Recruiter Pipeline",
            "pipeline_running": orchestrator.is_running,
            "resume_uploaded": await resume_store.exists(),
        })

        # ── Message Loop ───────────────────────────────────────────────────────
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await _send(ws, {"type": MSG_PING})
                continue
            except WebSocketDisconnect:
                break

            # Parse incoming message
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, {
                    "type": MSG_ERROR,
                    "message": "Invalid JSON. Expected: {\"type\": \"start\", ...}",
                })
                continue

            msg_type = message.get("type", "").lower()

            # ── Handle: ping ───────────────────────────────────────────────────
            if msg_type == MSG_PING:
                await _send(ws, {"type": MSG_PONG})
                continue

            # ── Handle: start ──────────────────────────────────────────────────
            if msg_type == MSG_START:
                await _handle_start(ws, message)
                continue

            # ── Handle: cancel ─────────────────────────────────────────────────
            if msg_type == MSG_CANCEL:
                await _send(ws, {
                    "type": MSG_ERROR,
                    "message": "Cancel not yet supported. Pipeline will complete normally.",
                })
                continue

            # ── Unknown message type ───────────────────────────────────────────
            await _send(ws, {
                "type": MSG_ERROR,
                "message": f"Unknown message type: '{msg_type}'. Expected: start | ping | cancel",
            })

    except WebSocketDisconnect:
        logger.info("[ws] Client disconnected during session")
    except Exception as e:
        logger.error(f"[ws] Unexpected error: {e}")
        try:
            await _send(ws, {
                "type": MSG_ERROR,
                "message": f"Internal server error: {str(e)}",
            })
        except Exception:
            pass
    finally:
        await manager.disconnect(ws)


# ── Handler: Start Pipeline ────────────────────────────────────────────────────

async def _handle_start(ws: WebSocket, message: dict) -> None:
    """
    Handle a 'start' message from client.
    Runs the pipeline and streams status updates back.
    """
    # ── Guard: resume ──────────────────────────────────────────────────────────
    if not await resume_store.exists():
        await _send(ws, {
            "type": MSG_ERROR,
            "message": (
                "No resume uploaded. "
                "Upload your resume at POST /resume/upload before starting the pipeline."
            ),
        })
        return

    # ── Guard: already running ─────────────────────────────────────────────────
    if orchestrator.is_running:
        await _send(ws, {
            "type": MSG_ERROR,
            "message": (
                "Pipeline is already running. "
                "Wait for it to complete before starting a new run."
            ),
        })
        return

    # ── Parse config from message ──────────────────────────────────────────────
    keywords             = message.get("keywords", [])
    use_cache            = message.get("use_cache", True)
    force_refresh        = message.get("force_refresh", False)
    generate_cover_letters = message.get("generate_cover_letters", True)

    if not isinstance(keywords, list):
        await _send(ws, {
            "type": MSG_ERROR,
            "message": "keywords must be a list of strings.",
        })
        return

    logger.info(
        f"[ws] Pipeline start requested — "
        f"keywords={keywords}, use_cache={use_cache}, "
        f"cover_letters={generate_cover_letters}"
    )

    # ── Broadcast start notice to all connected clients ────────────────────────
    await manager.broadcast({
        "type": MSG_PIPELINE_STATUS,
        "data": PipelineStatus(
            stage="scraping",
            progress=0,
            message="Pipeline starting...",
        ).model_dump(),
    })

    # ── Stream pipeline with status callback ───────────────────────────────────
    async def on_status(status: PipelineStatus) -> None:
        """Broadcast every status update to ALL connected clients."""
        await manager.broadcast({
            "type": MSG_PIPELINE_STATUS,
            "data": status.model_dump(),
        })

    try:
        await orchestrator.run(
            keywords=keywords,
            use_cache=use_cache and not force_refresh,
            generate_cover_letters=generate_cover_letters,
            on_status=on_status,
        )

        # ── Final success message ──────────────────────────────────────────────
        timing = orchestrator.get_timing_report()
        await manager.broadcast({
            "type": MSG_PIPELINE_STATUS,
            "data": PipelineStatus(
                stage="done",
                progress=100,
                message=(
                    f"Pipeline complete in {timing.get('total_seconds', '?')}s. "
                    f"Fetch results from GET /pipeline/results."
                ),
            ).model_dump(),
        })

    except ValueError as e:
        await manager.broadcast({
            "type": MSG_ERROR,
            "message": str(e),
        })
    except Exception as e:
        logger.error(f"[ws] Pipeline execution error: {e}")
        await manager.broadcast({
            "type": MSG_ERROR,
            "message": f"Pipeline failed: {str(e)}",
        })


# ── Utility ────────────────────────────────────────────────────────────────────

async def _send(ws: WebSocket, message: dict) -> None:
    """Send a message to a single WebSocket client safely."""
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_json(message)
    except Exception as e:
        logger.warning(f"[ws] Failed to send to client: {e}")