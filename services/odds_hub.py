"""
In-process WebSocket fan-out for live odds updates.

Single-instance only by design: every connected browser gets pushed the
same odds row the moment it changes (generated, shaded for exposure, or
manually adjusted by an admin), instead of polling GET /betting/odds.

`publish()` is thread-safe and can be called from anywhere — a sync route
handler running in FastAPI's threadpool, or APScheduler's background
thread — because it hands the broadcast to the event loop via
`run_coroutine_threadsafe` rather than assuming it's already on it.

Scale-out note: this only fans out within one process. Running more than
one uvicorn worker/container means each would hold a different subset of
connections, with no shared broadcast between them. Swapping this for a
Redis pub/sub channel (publish stays a one-line call; subscribe runs as a
background task per process forwarding to local sockets) is the standard
fix — deliberately not pulled in now since this deployment is still single
process (see docker-compose.yml) and it would be a dependency this sandbox
can't even install to verify. The class below is kept narrow (connect /
disconnect / publish) specifically so that swap doesn't touch call sites.
"""

import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class OddsHub:

    def __init__(self):
        self._connections: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Call once, from the app's lifespan startup, on the running loop."""
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        logger.debug("Odds WS connected (%d total).", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def _broadcast(self, payload: dict) -> None:
        if not self._connections:
            return

        message = json.dumps(payload, default=str)
        dead = []

        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self._connections.discard(ws)

    def publish(self, payload: dict) -> None:
        """Thread-safe. No-op (logged) if called before bind_loop() or after
        the loop has stopped — a missed live-push is never worth crashing a
        bet-placement or scheduler job over."""

        if self._loop is None:
            return

        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(payload), self._loop)
        except RuntimeError:
            logger.debug("Odds WS publish dropped: event loop not running.")


odds_hub = OddsHub()
