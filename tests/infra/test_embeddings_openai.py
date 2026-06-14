import httpx

from mazyr.infrastructure.embeddings_openai import OpenAIEmbeddingAdapter


def test_openai_embedding_adapter_posts_embedding_request():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "embedding": [0.1, 0.2, 0.3],
                    }
                ]
            },
        )

    client = httpx.Client(
        base_url="https://api.openai.com/v1",
        headers={"Authorization": "Bearer secret"},
        transport=httpx.MockTransport(handler),
    )
    adapter = OpenAIEmbeddingAdapter(
        api_key="secret",
        model="text-embedding-3-small",
        dimensions=3,
        client=client,
    )

    embedding = adapter.embed("remember this")

    assert embedding == [0.1, 0.2, 0.3]
    assert requests[0].url.path == "/v1/embeddings"
    assert requests[0].headers["authorization"] == "Bearer secret"
    assert requests[0].read()
    body = requests[0].content.decode()
    assert '"input":"remember this"' in body
    assert '"model":"text-embedding-3-small"' in body
    assert '"dimensions":3' in body


def test_embed_batch_posts_array_input_and_returns_vectors_in_order():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = request.read().decode()
        assert '"input":["alpha","beta"]' in body
        return httpx.Response(
            200,
            json={
                "data": [
                    {"embedding": [0.1, 0.2]},
                    {"embedding": [0.3, 0.4]},
                ]
            },
        )

    client = httpx.Client(
        base_url="https://api.openai.com/v1",
        headers={"Authorization": "Bearer secret"},
        transport=httpx.MockTransport(handler),
    )
    adapter = OpenAIEmbeddingAdapter(
        api_key="secret", model="text-embedding-3-small", dimensions=2, client=client
    )

    vectors = adapter.embed_batch(["alpha", "beta"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert len(requests) == 1


def test_embed_batch_skips_empty_strings_and_preserves_alignment():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.5, 0.6]}]},
        )

    client = httpx.Client(
        base_url="https://api.openai.com/v1",
        headers={"Authorization": "Bearer secret"},
        transport=httpx.MockTransport(handler),
    )
    adapter = OpenAIEmbeddingAdapter(
        api_key="secret", model="text-embedding-3-small", dimensions=2, client=client
    )

    vectors = adapter.embed_batch(["", "non-empty", ""])

    assert vectors == [[], [0.5, 0.6], []]


def test_embed_caches_repeated_text_and_avoids_duplicate_http_calls():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.9, 1.0]}]},
        )

    client = httpx.Client(
        base_url="https://api.openai.com/v1",
        headers={"Authorization": "Bearer secret"},
        transport=httpx.MockTransport(handler),
    )
    adapter = OpenAIEmbeddingAdapter(
        api_key="secret", model="text-embedding-3-small", dimensions=2, client=client
    )

    assert adapter.embed("cached") == [0.9, 1.0]
    assert adapter.embed("cached") == [0.9, 1.0]
    assert adapter.embed_batch(["cached", "cached"]) == [[0.9, 1.0], [0.9, 1.0]]

    assert len(requests) == 1


def test_embed_batch_uses_cache_for_partial_hits():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
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

    adapter.embed("hit")  # cache
    vectors = adapter.embed_batch(["hit", "miss"])

    assert vectors == [[0.1, 0.2], [0.1, 0.2]]
    assert len(requests) == 2
