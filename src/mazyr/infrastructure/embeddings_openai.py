from collections import OrderedDict

import httpx

from mazyr.infrastructure.http_pool import get_sync_client
from mazyr.infrastructure.retry import retry_embedding


def _normalize(text: str) -> str:
    """Normalize text for cache-key stability."""
    return " ".join(text.split())


def _cache_key(text: str, model: str, dimensions: int) -> str:
    return f"{model}:{dimensions}:{text}"


class OpenAIEmbeddingAdapter:
    """OpenAI-compatible embeddings client with LRU cache and batch support."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        client: httpx.Client | None = None,
        cache_size: int = 1024,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.dimensions = dimensions
        self.client = client or get_sync_client()
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._cache_size = cache_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()

    def _get_cached(self, text: str) -> list[float] | None:
        key = _cache_key(text, self.model, self.dimensions)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _set_cached(self, text: str, vector: list[float]) -> None:
        key = _cache_key(text, self.model, self.dimensions)
        self._cache[key] = vector
        self._cache.move_to_end(key)
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    @retry_embedding
    def embed(self, text: str) -> list[float]:
        """Create one embedding vector for text, cached by normalized content."""
        if not text:
            raise ValueError("Cannot embed empty text")
        normalized = _normalize(text)
        cached = self._get_cached(normalized)
        if cached is not None:
            return cached

        response = self.client.post(
            f"{self.base_url}/embeddings",
            headers=self._headers,
            json={
                "input": normalized,
                "model": self.model,
                "dimensions": self.dimensions,
                "encoding_format": "float",
            },
        )
        response.raise_for_status()
        data = response.json()
        vector = data["data"][0]["embedding"]
        self._set_cached(normalized, vector)
        return vector

    @retry_embedding
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for multiple texts in a single API call.

        Results are cached individually. Empty texts are returned as empty
        vectors to preserve input/output alignment.
        """
        if not texts:
            return []

        normalized = [_normalize(t) for t in texts]
        results: list[list[float]] = []
        missing_indices: list[int] = []
        missing_texts: list[str] = []

        for idx, key in enumerate(normalized):
            if not key:
                results.append([])
                continue
            cached = self._get_cached(key)
            if cached is not None:
                results.append(cached)
            else:
                results.append([])  # placeholder
                missing_indices.append(idx)
                missing_texts.append(key)

        if missing_texts:
            response = self.client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers,
                json={
                    "input": missing_texts,
                    "model": self.model,
                    "dimensions": self.dimensions,
                    "encoding_format": "float",
                },
            )
            response.raise_for_status()
            data = response.json()
            for offset, item in enumerate(data["data"]):
                idx = missing_indices[offset]
                vector = item["embedding"]
                results[idx] = vector
                self._set_cached(normalized[idx], vector)

        return results
