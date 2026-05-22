"""Tests for src.lib.embedding — Ollama embedding client with retry."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.lib.embedding import embed_texts


@pytest.mark.unit
def test_embed_texts_returns_vectors():
    """embed_texts should return the embeddings list from ollama response."""
    mock_resp = MagicMock()
    mock_resp.embeddings = [[0.1, 0.2], [0.3, 0.4]]

    with patch("src.lib.embedding.ollama.embed", return_value=mock_resp):
        vecs = embed_texts(["a", "b"])

    assert vecs == [[0.1, 0.2], [0.3, 0.4]]


@pytest.mark.unit
def test_embed_texts_retries_on_connection_error():
    """embed_texts should retry on httpx.ConnectError and eventually succeed."""
    mock_resp = MagicMock()
    mock_resp.embeddings = [[1.0]]

    with patch(
        "src.lib.embedding.ollama.embed",
        side_effect=[httpx.ConnectError("refused"), mock_resp],
    ):
        vecs = embed_texts(["x"])

    assert vecs == [[1.0]]


@pytest.mark.unit
def test_embed_texts_reraises_after_max_retries():
    """embed_texts should re-raise ConnectError after exhausting retries."""
    error = httpx.ConnectError("connection refused")

    with patch(
        "src.lib.embedding.ollama.embed",
        side_effect=error,
    ), pytest.raises(httpx.ConnectError, match="connection refused"):
        embed_texts(["x"])
