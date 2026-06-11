import httpx


class OpenAIEmbeddingAdapter:
    """OpenAI-compatible embeddings client."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        client: httpx.Client | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.dimensions = dimensions
        self.client = client or httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )

    def embed(self, text: str) -> list[float]:
        """Create one embedding vector for text."""
        if not text:
            raise ValueError("Cannot embed empty text")

        response = self.client.post(
            "/embeddings",
            json={
                "input": text,
                "model": self.model,
                "dimensions": self.dimensions,
                "encoding_format": "float",
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]
