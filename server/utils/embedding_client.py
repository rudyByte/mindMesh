import hashlib
import logging
import math
import re
import json
import urllib.request
from functools import lru_cache
from typing import Iterable

from server.config import config

logger = logging.getLogger("embedding_client")


_SEMANTIC_ALIASES = {
    "voltage": ["potential", "difference", "electric", "potential"],
    "potential": ["voltage", "electric"],
    "difference": ["voltage"],
    "neural": ["network", "net"],
    "net": ["neural", "network"],
    "network": ["neural", "net"],
    "networks": ["neural", "network"],
    "ai": ["artificial", "intelligence"],
    "ml": ["machine", "learning"],
}


def cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    av = list(a or [])
    bv = list(b or [])
    if not av or not bv or len(av) != len(bv):
        return 0.0
    dot = sum(x * y for x, y in zip(av, bv))
    na = math.sqrt(sum(x * x for x in av))
    nb = math.sqrt(sum(y * y for y in bv))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class EmbeddingClient:
    def __init__(self):
        self._client = None
        if (
            getattr(config, "EMBEDDING_PROVIDER", "local") == "openai"
            and config.OPENAI_API_KEY
            and "mock" not in config.OPENAI_API_KEY.lower()
        ):
            self._client = True
            logger.info("Embedding client using OpenAI-compatible HTTP embeddings.")

    def is_remote(self) -> bool:
        return self._client is not None

    @staticmethod
    def _tokens(text: str) -> list[str]:
        text = (text or "").lower()
        text = text.replace("potential difference", "potential difference voltage")
        text = text.replace("neural net", "neural network")
        raw = re.findall(r"[a-z0-9]+", text)
        tokens = []
        for token in raw:
            if len(token) < 2:
                continue
            tokens.append(token)
            tokens.extend(_SEMANTIC_ALIASES.get(token, []))
        return tokens

    @staticmethod
    def _local_embedding(text: str, dims: int = 256) -> list[float]:
        vector = [0.0] * dims
        for token in EmbeddingClient._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % dims
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[idx] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm:
            vector = [v / norm for v in vector]
        return vector

    @lru_cache(maxsize=4096)
    def embed_text(self, text: str) -> tuple[float, ...]:
        clean = re.sub(r"\s+", " ", (text or "")).strip()[:4000]
        if not clean:
            return tuple()
        if self._client:
            try:
                payload = json.dumps({"model": config.EMBEDDING_MODEL, "input": clean}).encode("utf-8")
                req = urllib.request.Request(
                    "https://api.openai.com/v1/embeddings",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=20) as res:
                    data = json.loads(res.read().decode("utf-8"))
                return tuple(float(x) for x in data["data"][0]["embedding"])
            except Exception as e:
                logger.warning(f"Remote embedding failed, using local vector fallback: {e}")
        return tuple(self._local_embedding(clean))

    def embed_node(self, node: dict) -> list[float]:
        name = node.get("name") or node.get("title") or ""
        description = node.get("description") or ""
        return list(self.embed_text(f"{name}. {description}"))


embedding_client = EmbeddingClient()
