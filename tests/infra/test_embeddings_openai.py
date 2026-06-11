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
