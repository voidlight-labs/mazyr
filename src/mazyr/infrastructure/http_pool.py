"""Shared HTTP client pool for sync infrastructure adapters.

Adapters that speak HTTP (LLM, embeddings, Telegram, GitHub) can reuse these
clients instead of creating a new connection per instance or per call.
"""

import atexit

import httpx


class HTTPPool:
    """Module-level pool of reusable httpx clients.

    The pool is intentionally simple: one sync client and one async client.
    Adapters receive the client they need via constructor injection; the pool
    just provides the default instances and handles global shutdown.
    """

    _sync_client: httpx.Client | None = None
    _async_client: httpx.AsyncClient | None = None

    @classmethod
    def sync_client(cls) -> httpx.Client:
        if cls._sync_client is None:
            cls._sync_client = httpx.Client(timeout=60.0)
            atexit.register(cls.close_sync)
        return cls._sync_client

    @classmethod
    def async_client(cls) -> httpx.AsyncClient:
        if cls._async_client is None:
            cls._async_client = httpx.AsyncClient(timeout=60.0)
            atexit.register(cls.close_async)
        return cls._async_client

    @classmethod
    def close_sync(cls):
        if cls._sync_client is not None:
            cls._sync_client.close()
            cls._sync_client = None

    @classmethod
    def close_async(cls):
        if cls._async_client is not None:
            # Async close cannot run at process exit without a loop; ignore if
            # the loop is gone. Production callers should await close_async()
            # explicitly during graceful shutdown.
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    cls._async_client = None
                    return
                loop.run_until_complete(cls._async_client.aclose())
            except Exception:
                pass
            cls._async_client = None


def get_sync_client() -> httpx.Client:
    return HTTPPool.sync_client()


def get_async_client() -> httpx.AsyncClient:
    return HTTPPool.async_client()
