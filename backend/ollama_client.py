import asyncio
import time
from urllib.parse import urljoin

import httpx
import ollama


def get_ollama_client(host: str) -> "ollama.Client":
    host = (host or "").strip()
    return ollama.Client(host=host) if host else ollama.Client()


async def wait_for_ollama(host: str, timeout_sec: float = 5.0) -> None:
    """
    Wait until Ollama responds to /api/tags (or timeout).
    Raises TimeoutError on failure.
    """
    deadline = time.time() + max(0.1, float(timeout_sec))
    url = urljoin(host.rstrip("/") + "/", "api/tags")

    last_err: Exception | None = None
    async with httpx.AsyncClient(timeout=1.0) as client:
        while time.time() < deadline:
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    return
                last_err = RuntimeError(f"HTTP {r.status_code}")
            except Exception as e:
                last_err = e
            await asyncio.sleep(0.2)

    raise TimeoutError(f"Ollama not reachable at {host!r} within {timeout_sec}s: {last_err}")

