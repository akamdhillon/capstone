"""SSE debug event emitter for live analysis progress."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

_sse_listeners: set[asyncio.Queue] = set()


async def emit_debug_event(event: dict):
    """Push a debug event to all SSE clients."""
    dead: set[asyncio.Queue] = set()
    for q in _sse_listeners:
        try:
            q.put_nowait(event.copy())
        except asyncio.QueueFull:
            dead.add(q)
    for q in dead:
        _sse_listeners.discard(q)


def get_sse_listeners():
    """Return the set of SSE listener queues (for main.py SSE endpoint)."""
    return _sse_listeners


@asynccontextmanager
async def frame_poller_context(capture_url: str) -> AsyncIterator[None]:
    """Poll Jetson capture-frame during analysis and emit to SSE clients."""
    import httpx
    stop = asyncio.Event()

    async def poll_loop() -> None:
        while not stop.is_set():
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    r = await client.post(capture_url)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("success") and data.get("image"):
                            await emit_debug_event({"type": "frame", "image": data["image"]})
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop.wait(), timeout=1.5)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(poll_loop())
    try:
        yield
    finally:
        stop.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
