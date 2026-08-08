"""Embedding providers.

Primary hackathon provider: Amazon Bedrock (Titan Text Embeddings V2, 1024
dimensions by default).

Fallback: deterministic lexical hashing that never requires a network call,
used in local mode and when Bedrock credentials are unavailable. The same
interface is used by the worker, MCP server, and CLI, so retrieval stays
consistent regardless of the provider.
"""

from __future__ import annotations

import hashlib
import math
import os
from typing import List, Optional, Sequence

DEFAULT_DIM = 512


class EmbeddingProvider:
    name = "base"

    def embed(self, text: str, dim: int = DEFAULT_DIM) -> List[float]:
        raise NotImplementedError


class LexicalEmbeddingProvider(EmbeddingProvider):
    """Deterministic hashing-based embedding: zero network, zero cost.

    This is intentionally simple. Its only contract is that equal text
    yields equal vectors and similar text yields nearby vectors for the
    local fallback path. Replace with a real embedding model (Bedrock,
    Ollama, sentence-transformers) when the environment provides one.
    """

    name = "lexical"

    def embed(self, text: str, dim: int = DEFAULT_DIM) -> List[float]:
        vec = [0.0] * dim
        tokens = text.lower().split()
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "little") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[index] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class BedrockEmbeddingProvider(EmbeddingProvider):
    """Amazon Bedrock Titan Text Embeddings V2 via boto3."""

    name = "bedrock"

    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None):
        import boto3  # noqa: F401

        self.model_id = model_id or os.getenv(
            "HANDOFF_BEDROCK_EMBED_MODEL",
            "amazon.titan-embed-text-v2:0",
        )
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("bedrock-runtime", region_name=self.region)

    def embed(self, text: str, dim: int = DEFAULT_DIM) -> List[float]:
        body = {
            "inputText": text[:8192],
            "dimensions": dim,
            "normalize": True,
        }
        resp = self._client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=__import__("json").dumps(body),
        )
        payload = __import__("json").loads(resp["body"].read())
        return list(payload["embedding"])


def embedding_provider_from_env() -> EmbeddingProvider:
    provider = os.getenv("HANDOFF_EMBEDDING_PROVIDER", "lexical").lower()
    if provider == "bedrock":
        try:
            return BedrockEmbeddingProvider()
        except Exception:
            # The lexical fallback is the documented failure mode; the app
            # must never break because the model provider is unavailable.
            return LexicalEmbeddingProvider()
    return LexicalEmbeddingProvider()