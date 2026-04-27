import json
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.websockets import WebSocketState
from backend.core.schemas import PipelineStatus
from backend.agents.orchestrator import orchestrator
from backend.resume.resume_store import resume_store

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


# ── Message Type Constants ─────────────────────────────────────────────────────

class MsgType:
    # Server → Client
    CONNECTED        = "connected"
    PIPELINE_STATUS  = "pipeline_status"
    PIPELINE_DONE    = "pipeline_done"
    ERROR            = "error"
    PING             = "ping"
    PONG             = "pong"
    ATTACHED         = "attached"
    CLIENT_COUNT     = "client_count"

    # Client → Server
    START            = "start"
    CANCEL           = "cancel"
    STATUS           = "status"


# ── Client State ───────────────────────────────────────────────────────────────

@dataclass
class ClientConnection:
    """
    Represents a single connected WebSocket client.
    Tracks metadata, message queue, and health.
    """
    ws:              WebSocket
    client_id:       str                    = field(default_factory=lambda: str(uuid.uuid4())[:8])
    connected_at:    datetime               = field(default_factory=datetime.now)
    last_seen:       datetime               = field(default_factory=datetime.now)
    message_queue:   asyncio.Queue          = field(default_factory=lambda: asyncio.Queue(maxsize=100))
    missed_pings:    int                    = 0
    is_alive:        bool                   = True

    # Pipeline run context this client triggered
    triggered_run:   bool                   = False

    def touch(self):
        """Update last_seen timestamp."""
        self.last_seen = datetime.now()
        self.missed_pings = 0

    def uptime_seconds(self) -> float:
        return (datetime.now() - self.connected_at).total_seconds()


# ── Connection Manager ─────────────────────────────────────────────────────────

class ConnectionManager:
    """
    Production-grade WebSocket connection manager.

    Features:
    - Named client tracking with UUIDs
    - Per-client message queues (non-blocking sends)
    - Server-initiated heartbeat with auto-disconnect on dead clients
    - Broadcast to all or specific clients
    - Attach late-joiners to an already-running pipeline
    - Live connection stats
    """

    HEARTBEAT_INTERVAL   = 20.0       # seconds between server pings
    MAX_MISSED_PINGS     = 3          # disconnect after this many missed pings
    QUEUE_DRAIN_TIMEOUT  = 5.0        # seconds to drain queue on disconnect

    def __init__(self):
        self._clients:  dict[str, ClientConnection] = {}
        self._lock:     asyncio.Lock = asyncio.Lock()
        self._heartbeat_task: Optional[asyncio.Task] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> ClientConnection:
        """Accept connection, register client, start heartbeat if needed."""
        await ws.accept()
        client = ClientConnection(ws=ws)

        async with self._lock:
            self._clients[client.client_id] = client
            count = len(self._clients)

        logger.info(
            f"[ws] Client {client.client_id} connected. "
            f"Total active: {count}"
        )

        # Start heartbeat loop if not running
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        return client

    async def disconnect(self, client: ClientConnection) -> None:
        """Gracefully remove client and drain its queue."""
        client.is_alive = False

        async with self._lock:
            self._clients.pop(client.client_id, None)
            count = len(self._clients)

        logger.info(
            f"[ws] Client {client.client_id} disconnected "
            f"(uptime: {client.uptime_seconds():.0f}s). "
            f"Remaining: {count}"
        )

        # Stop heartbeat if no clients left
        if count == 0 and self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    # ── Sending ────────────────────────────────────────────────────────────────

    async def send(self, client: ClientConnection, message: dict) -> bool:
        """
        Send message to a single client.
        Non-blocking — enqueues message, writer task drains queue.
        Returns False if client is dead or queue is full.
        """
        if not client.is_alive:
            return False
        try:
            client.message_queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            logger.warning(
                f"[ws] Queue full for client {client.client_id} — dropping message"
            )
            return False

    async def send_direct(self, client: ClientConnection, message: dict) -> bool:
        """
        Send directly to WebSocket (blocking). Used for time-critical messages.
        Falls back gracefully if client disconnected.
        """
        try:
            if client.ws.client_state == WebSocketState.CONNECTED:
                await client.ws.send_json(message)
                return True
        except Exception as e:
            logger.warning(f"[ws] Direct send failed for {client.client_id}: {e}")
        return False

    async def broadcast(self, message: dict, exclude: Optional[str] = None) -> int:
        """
        Broadcast message to all connected clients.
        Returns count of clients successfully reached.
        exclude: client_id to skip (e.g. the sender)
        """
        async with self._lock:
            targets = [
                c for cid, c in self._clients.items()
                if c.is_alive and cid != exclude
            ]

        sent = 0
        for client in targets:
            if await self.send(client, message):
                sent += 1
        return sent

    # ── Queue Writer ───────────────────────────────────────────────────────────

    async def run_writer(self, client: ClientConnection) -> None:
        """
        Continuously drains the client's message queue to the WebSocket.
        Runs as a separate task per client for the lifetime of the connection.
        """
        while client.is_alive:
            try:
                message = await asyncio.wait_for(
                    client.message_queue.get(),
                    timeout=1.0,
                )
                try:
                    if client.ws.client_state == WebSocketState.CONNECTED:
                        await client.ws.send_json(message)
                except Exception as e:
                    logger.warning(
                        f"[ws] Writer failed for {client.client_id}: {e}"
                    )
                    client.is_alive = False
                    break
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    # ── Heartbeat ──────────────────────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        """
        Periodically ping all clients.
        Clients that miss MAX_MISSED_PINGS consecutive pings are evicted.
        """
        logger.debug("[ws] Heartbeat loop started")
        while True:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

            async with self._lock:
                clients = list(self._clients.values())

            if not clients:
                break

            dead: list[ClientConnection] = []
            for client in clients:
                if not client.is_alive:
                    dead.append(client)
                    continue

                client.missed_pings += 1
                if client.missed_pings > self.MAX_MISSED_PINGS:
                    logger.warning(
                        f"[ws] Client {client.client_id} missed "
                        f"{client.missed_pings} pings — evicting"
                    )
                    dead.append(client)
                    client.is_alive = False
                else:
                    await self.send(client, {
                        "type": MsgType.PING,
                        "timestamp": datetime.now().isoformat(),
                    })

            for client in dead:
                await self.disconnect(client)

        logger.debug("[ws] Heartbeat loop stopped — no clients")

    # ── Stats ──────────────────────────────────────────────────────────────────

    async def stats(self) -> dict:
        async with self._lock:
            clients = list(self._clients.values())
        return {
            "active_connections": len(clients),
            "clients": [
                {
                    "client_id": c.client_id,
                    "connected_at": c.connected_at.isoformat(),
                    "uptime_seconds": round(c.uptime_seconds(), 1),
                    "missed_pings": c.missed_pings,
                    "queue_size": c.message_queue.qsize(),
                    "triggered_run": c.triggered_run,
                }
                for c in clients
            ],
        }

    @property
    def client_count(self) -> int:
        return len(self._clients)


# ── Singleton Manager ──────────────────────────────────────────────────────────

manager = ConnectionManager()


# ── WebSocket Endpoint ─────────────────────────────────────────────────────────

@router.websocket("/ws/pipeline")
async def pipeline_websocket(
    ws: WebSocket,
    client_id: Optional[str] = Query(None, description="Optional client ID for reconnection"),
):
    """
    WebSocket endpoint for real-time pipeline progress streaming.

    ─────────────────────────────────────────────────────────────────────────
    CLIENT → SERVER PROTOCOL
    ─────────────────────────────────────────────────────────────────────────
    Start pipeline:
      {
        "type": "start",
        "keywords": ["python", "fastapi"],
        "use_cache": true,
        "force_refresh": false,
        "generate_cover_letters": true
      }

    Request current status:
      {"type": "status"}

    Respond to server ping:
      {"type": "pong"}

    ─────────────────────────────────────────────────────────────────────────
    SERVER → CLIENT PROTOCOL
    ─────────────────────────────────────────────────────────────────────────
    On connect:
      {"type": "connected", "client_id": "...", "resume_uploaded": bool, "pipeline_running": bool}

    If pipeline already running when client connects:
      {"type": "attached", "message": "Attached to running pipeline"}

    Pipeline progress:
      {"type": "pipeline_status", "data": PipelineStatus, "timestamp": "..."}

    Pipeline complete:
      {"type": "pipeline_done", "timing": {...}, "message": "..."}

    Heartbeat:
      {"type": "ping", "timestamp": "..."}   (client should respond with "pong")

    Error:
      {"type": "error", "message": "...", "code": "..."}
    ─────────────────────────────────────────────────────────────────────────
    """
    client = await manager.connect(ws)

    # Override client_id if reconnecting
    if client_id:
        client.client_id = client_id
        logger.info(f"[ws] Client reconnected with id: {client_id}")

    # Start writer task for this client
    writer_task = asyncio.create_task(manager.run_writer(client))

    try:
        # ── Handshake ──────────────────────────────────────────────────────────
        await manager.send(client, {
            "type": MsgType.CONNECTED,
            "client_id": client.client_id,
            "message": "Connected to AI Recruiter Pipeline WebSocket",
            "resume_uploaded": await resume_store.exists(),
            "pipeline_running": orchestrator.is_running,
            "server_time": datetime.now().isoformat(),
        })

        # If pipeline already running, attach this client automatically
        if orchestrator.is_running:
            await manager.send(client, {
                "type": MsgType.ATTACHED,
                "message": (
                    "Pipeline is already running. "
                    "You will receive live updates from the current run."
                ),
                "current_stage": orchestrator.current_stage,
            })

        # ── Message Loop ───────────────────────────────────────────────────────
        while client.is_alive:
            try:
                raw = await asyncio.wait_for(
                    ws.receive_text(),
                    timeout=manager.HEARTBEAT_INTERVAL + 5.0,
                )
                client.touch()

            except asyncio.TimeoutError:
                # Client hasn't sent anything in a while — they're probably
                # just listening. That's fine. Heartbeat handles eviction.
                continue

            except WebSocketDisconnect:
                logger.info(f"[ws] Client {client.client_id} disconnected cleanly")
                break

            # ── Parse ──────────────────────────────────────────────────────────
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send(client, {
                    "type": MsgType.ERROR,
                    "message": "Invalid JSON.",
                    "code": "INVALID_JSON",
                })
                continue

            if not isinstance(message, dict):
                await manager.send(client, {
                    "type": MsgType.ERROR,
                    "message": "Message must be a JSON object.",
                    "code": "INVALID_FORMAT",
                })
                continue

            msg_type = str(message.get("type", "")).lower()

            # ── Route message ──────────────────────────────────────────────────
            if msg_type == MsgType.PONG:
                client.touch()
                continue

            elif msg_type == MsgType.PING:
                await manager.send(client, {"type": MsgType.PONG})
                continue

            elif msg_type == MsgType.STATUS:
                await _handle_status(client)
                continue

            elif msg_type == MsgType.START:
                await _handle_start(client, message)
                continue

            elif msg_type == MsgType.CANCEL:
                await manager.send(client, {
                    "type": MsgType.ERROR,
                    "message": "Pipeline cancellation is not yet supported.",
                    "code": "NOT_IMPLEMENTED",
                })
                continue

            else:
                await manager.send(client, {
                    "type": MsgType.ERROR,
                    "message": (
                        f"Unknown message type: '{msg_type}'. "
                        f"Expected: start | status | ping | pong | cancel"
                    ),
                    "code": "UNKNOWN_TYPE",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[ws] Unhandled error for client {client.client_id}: {e}")
        try:
            await manager.send_direct(client, {
                "type": MsgType.ERROR,
                "message": f"Internal server error: {str(e)}",
                "code": "INTERNAL_ERROR",
            })
        except Exception:
            pass
    finally:
        client.is_alive = False
        writer_task.cancel()
        try:
            await asyncio.wait_for(writer_task, timeout=2.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        await manager.disconnect(client)


# ── Handler: Status ────────────────────────────────────────────────────────────

async def _handle_status(client: ClientConnection) -> None:
    """Respond to a status request from the client."""
    ws_stats = await manager.stats()
    await manager.send(client, {
        "type": MsgType.CLIENT_COUNT,
        "pipeline_running": orchestrator.is_running,
        "current_stage": orchestrator.current_stage if orchestrator.is_running else None,
        "resume_uploaded": await resume_store.exists(),
        "timing": orchestrator.get_timing_report() if orchestrator.has_run else None,
        "connections": ws_stats,
        "timestamp": datetime.now().isoformat(),
    })


# ── Handler: Start Pipeline ────────────────────────────────────────────────────

async def _handle_start(client: ClientConnection, message: dict) -> None:
    """
    Handle a 'start' message — validate, configure, and run the pipeline.
    Streams all status updates to ALL connected clients via broadcast.
    """

    # ── Guard: resume ──────────────────────────────────────────────────────────
    if not await resume_store.exists():
        await manager.send(client, {
            "type": MsgType.ERROR,
            "message": (
                "No resume uploaded. "
                "Upload your resume at POST /resume/upload before starting."
            ),
            "code": "NO_RESUME",
        })
        return

    # ── Guard: already running ─────────────────────────────────────────────────
    if orchestrator.is_running:
        await manager.send(client, {
            "type": MsgType.ERROR,
            "message": (
                "Pipeline is already running. "
                "You are receiving live updates from the current run."
            ),
            "code": "ALREADY_RUNNING",
        })
        return

    # ── Validate config ────────────────────────────────────────────────────────
    keywords = message.get("keywords", [])
    use_cache = message.get("use_cache", True)
    force_refresh = message.get("force_refresh", False)
    generate_cover_letters = message.get("generate_cover_letters", True)

    if not isinstance(keywords, list):
        await manager.send(client, {
            "type": MsgType.ERROR,
            "message": "keywords must be a JSON array of strings.",
            "code": "INVALID_KEYWORDS",
        })
        return

    # Sanitize keywords
    keywords = [str(k).strip() for k in keywords if k and str(k).strip()][:10]

    client.triggered_run = True

    logger.info(
        f"[ws] Client {client.client_id} started pipeline — "
        f"keywords={keywords}, use_cache={use_cache}, "
        f"cover_letters={generate_cover_letters}"
    )

    # ── Notify all clients pipeline is starting ────────────────────────────────
    start_count = await manager.broadcast({
        "type": MsgType.PIPELINE_STATUS,
        "data": PipelineStatus(
            stage="scraping",
            progress=0,
            message=f"Pipeline starting (triggered by client {client.client_id})...",
        ).model_dump(),
        "timestamp": datetime.now().isoformat(),
        "triggered_by": client.client_id,
    })
    logger.info(f"[ws] Pipeline start broadcast to {start_count} clients")

    # ── Status callback — broadcasts to ALL clients ────────────────────────────
    async def on_status(status: PipelineStatus) -> None:
        await manager.broadcast({
            "type": MsgType.PIPELINE_STATUS,
            "data": status.model_dump(),
            "timestamp": datetime.now().isoformat(),
        })

    # ── Run pipeline ───────────────────────────────────────────────────────────
    try:
        await orchestrator.run(
            keywords=keywords,
            use_cache=use_cache and not force_refresh,
            generate_cover_letters=generate_cover_letters,
            on_status=on_status,
        )

        timing = orchestrator.get_timing_report()
        last_result = orchestrator.get_last_result()

        await manager.broadcast({
            "type": MsgType.PIPELINE_DONE,
            "message": (
                f"Pipeline complete in {timing.get('total_seconds', '?')}s. "
                f"Fetch results from GET /pipeline/results."
            ),
            "timing": timing,
            "summary": {
                "total_scraped": last_result.total_jobs_scraped if last_result else 0,
                "total_matched": last_result.total_jobs_matched if last_result else 0,
                "cover_letters": (
                    sum(1 for r in last_result.results if r.cover_letter)
                    if last_result else 0
                ),
            },
            "timestamp": datetime.now().isoformat(),
        })

    except ValueError as e:
        await manager.broadcast({
            "type": MsgType.ERROR,
            "message": str(e),
            "code": "VALIDATION_ERROR",
        })
    except Exception as e:
        logger.error(f"[ws] Pipeline error: {e}")
        await manager.broadcast({
            "type": MsgType.ERROR,
            "message": f"Pipeline failed: {str(e)}",
            "code": "PIPELINE_ERROR",
        })
    finally:
        client.triggered_run = False


# ── Stats Endpoint ─────────────────────────────────────────────────────────────

@router.get(
    "/ws/stats",
    summary="WebSocket connection statistics",
    tags=["WebSocket"],
)
async def get_ws_stats():
    """Returns live WebSocket connection statistics."""
    return await manager.stats()