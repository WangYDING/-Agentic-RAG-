import pytest


@pytest.mark.model
def test_default_embedding_model_can_encode_text():
    """Explicit smoke test: downloads/loads the real embedding model."""
    from src.embedder import Embedder

    vector = Embedder().embed_text("城市轨道交通")

    assert vector
    assert all(isinstance(value, float) for value in vector)
