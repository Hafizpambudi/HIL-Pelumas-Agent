import hashlib
import math
import re

import httpx

from pelumas_agent.config import get_settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    def __init__(self, dim: int | None = None):
        self.dim = dim or get_settings().embed_dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = _TOKEN_RE.findall(text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class OpenAIEmbedder:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        from openai import OpenAI

        settings = get_settings()
        self.client = OpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or None,
        )
        self.model = model or settings.openai_embed_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in response.data]


class GeminiEmbedder:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_embed_model
        self.dim = settings.embed_dim
        self.url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:embedContent"
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            response = httpx.post(
                self.url,
                headers={"x-goog-api-key": self.api_key},
                json={
                    "content": {"parts": [{"text": text}]},
                    "output_dimensionality": self.dim,
                },
                timeout=30,
            )
            response.raise_for_status()
            vectors.append(response.json()["embedding"]["values"])
        return vectors


def get_embedder():
    settings = get_settings()
    if settings.gemini_api_key:
        return GeminiEmbedder()
    return HashEmbedder()
