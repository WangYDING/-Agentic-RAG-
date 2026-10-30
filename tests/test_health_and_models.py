import json

from src.config import AppConfig
from src.health_cli import check_readiness
from src.model_cli import model_marker_path, models_are_prepared


def test_model_marker_requires_exact_model_identity(tmp_path):
    config = AppConfig(model_cache_dir=str(tmp_path), embedding_revision="rev-1")
    marker = model_marker_path(config)
    marker.parent.mkdir(parents=True)
    marker.write_text(
        json.dumps(
            {
                "embedding_model": config.embedding_model,
                "embedding_revision": config.embedding_revision,
                "reranker_model": config.reranker_model,
            }
        ),
        encoding="utf-8",
    )
    assert models_are_prepared(config)
    assert not models_are_prepared(
        AppConfig(model_cache_dir=str(tmp_path), embedding_revision="rev-2")
    )


def test_readiness_is_false_when_api_configuration_is_missing(tmp_path):
    config = AppConfig(
        pdf_path=str(tmp_path / "missing.pdf"),
        index_dir=str(tmp_path / "index"),
        model_cache_dir=str(tmp_path / "models"),
    )
    result = check_readiness(config)
    assert result["status"] == "not_ready"
    assert result["checks"] == {
        "configuration": False,
        "models": False,
        "index": False,
    }
    assert "DEEPSEEK_API_KEY" in result["reason"]
    assert "DEEPSEEK_BASE_URL" in result["reason"]
