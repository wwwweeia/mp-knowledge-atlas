"""Ollama embedding client with exponential backoff retry."""

import httpx
import ollama
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

MODEL = "nomic-embed-text:v1.5"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.ConnectError),
    reraise=True,
)
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using Ollama.

    Retries up to 3 times with exponential backoff on connection errors.
    Re-raises the last exception if all attempts fail.
    """
    resp = ollama.embed(model=MODEL, input=texts)
    return resp.embeddings
