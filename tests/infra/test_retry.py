import httpx
import pytest

from mazyr.infrastructure.embeddings_openai import OpenAIEmbeddingAdapter
from mazyr.infrastructure.github_sync import GitHubSyncAdapter
from mazyr.infrastructure.messenger_telegram import TelegramAdapter


def test_embedding_adapter_retries_transient_httpx_error():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) < 2:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2]}]},
        )

    client = httpx.Client(
        base_url="https://api.openai.com/v1",
        headers={"Authorization": "Bearer secret"},
        transport=httpx.MockTransport(handler),
    )
    adapter = OpenAIEmbeddingAdapter(
        api_key="secret", model="text-embedding-3-small", dimensions=2, client=client
    )

    vector = adapter.embed("retry me")

    assert vector == [0.1, 0.2]
    assert len(attempts) == 2


def test_embedding_adapter_stops_after_exhausted_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    client = httpx.Client(
        base_url="https://api.openai.com/v1",
        headers={"Authorization": "Bearer secret"},
        transport=httpx.MockTransport(handler),
    )
    adapter = OpenAIEmbeddingAdapter(
        api_key="secret", model="text-embedding-3-small", dimensions=2, client=client
    )

    with pytest.raises(httpx.ConnectError):
        adapter.embed("fail")


def test_telegram_adapter_retries_send_message():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) < 2:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client = httpx.Client(
        base_url="https://api.telegram.org/bot123",
        transport=httpx.MockTransport(handler),
    )
    adapter = TelegramAdapter("123")
    adapter.client = client

    adapter.send_message(1, "hello")

    assert len(attempts) == 2


def test_github_adapter_retries_push_snapshot():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        if len(attempts) < 2:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(
            201,
            json={"content": {"html_url": "https://github.com/test/repo/blob/main/snapshot.json"}},
        )

    client = httpx.Client(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
    )
    adapter = GitHubSyncAdapter("token", "owner/repo")
    adapter.client = client

    result = adapter.push_snapshot({"key": "value"})

    assert result["content"]["html_url"].endswith("snapshot.json")
    assert len(attempts) == 3  # GET retries once, then PUT succeeds
