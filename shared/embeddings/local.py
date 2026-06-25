from __future__ import annotations

import hashlib
import math


class LocalHashEmbeddingProvider:
    name = "local_hash_embeddings"
    version = "local-v0.1.0"

    def embed(self, text: str, dimensions: int = 32) -> list[float]:
        vector = [0.0] * dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = digest[0] % dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 6) for value in vector]
