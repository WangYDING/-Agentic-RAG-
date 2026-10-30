import pytest

from src.config import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EVIDENCE_TOP_N,
    DEFAULT_GENERATION_MODEL,
    DEFAULT_INDEX_DIR,
    DEFAULT_PDF_PATH,
    DEFAULT_RERANKER_MODEL,
    DEFAULT_RETRIEVAL_TOP_K,
    DEFAULT_MAX_MODEL_CALLS,
    DEFAULT_MAX_NETWORK_RETRIES,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_TOTAL_TIMEOUT_SECONDS,
    AppConfig,
    ConfigurationError,
)


def test_defaults_are_stable_without_environment():
    config = AppConfig.from_sources(environ={})

    assert config.pdf_path == DEFAULT_PDF_PATH
    assert config.index_dir == DEFAULT_INDEX_DIR
    assert config.embedding_model == DEFAULT_EMBEDDING_MODEL
    assert config.reranker_model == DEFAULT_RERANKER_MODEL
    assert config.generation_model == DEFAULT_GENERATION_MODEL
    assert config.retrieval_top_k == DEFAULT_RETRIEVAL_TOP_K
    assert config.evidence_top_n == DEFAULT_EVIDENCE_TOP_N
    assert config.request_timeout_seconds == DEFAULT_REQUEST_TIMEOUT_SECONDS
    assert config.max_network_retries == DEFAULT_MAX_NETWORK_RETRIES
    assert config.total_timeout_seconds == DEFAULT_TOTAL_TIMEOUT_SECONDS
    assert config.max_model_calls == DEFAULT_MAX_MODEL_CALLS


def test_explicit_values_override_environment():
    environ = {
        "RAG_PDF_PATH": "env.pdf",
        "RAG_INDEX_DIR": "env-index",
        "RAG_EMBEDDING_MODEL": "env-embedding",
        "RAG_RERANKER_MODEL": "env-reranker",
        "DEEPSEEK_MODEL": "env-generation",
        "DEEPSEEK_BASE_URL": "https://env.test",
        "DEEPSEEK_API_KEY": "env-secret",
        "RAG_RETRIEVAL_TOP_K": "12",
        "RAG_EVIDENCE_TOP_N": "4",
        "RAG_REQUEST_TIMEOUT_SECONDS": "20",
        "RAG_MAX_NETWORK_RETRIES": "2",
        "RAG_TOTAL_TIMEOUT_SECONDS": "60",
        "RAG_MAX_MODEL_CALLS": "8",
    }

    config = AppConfig.from_sources(
        environ=environ,
        pdf_path="explicit.pdf",
        index_dir="explicit-index",
        embedding_model="explicit-embedding",
        reranker_model="explicit-reranker",
        generation_model="explicit-generation",
        api_base_url="https://explicit.test",
        api_key="explicit-secret",
        retrieval_top_k=20,
        evidence_top_n=5,
        request_timeout_seconds=15,
        max_network_retries=0,
        total_timeout_seconds=45,
        max_model_calls=7,
    )

    assert config.pdf_path == "explicit.pdf"
    assert config.index_dir == "explicit-index"
    assert config.embedding_model == "explicit-embedding"
    assert config.reranker_model == "explicit-reranker"
    assert config.generation_model == "explicit-generation"
    assert config.api_base_url == "https://explicit.test"
    assert config.api_key == "explicit-secret"
    assert config.retrieval_top_k == 20
    assert config.evidence_top_n == 5
    assert config.request_timeout_seconds == 15
    assert config.max_network_retries == 0
    assert config.total_timeout_seconds == 45
    assert config.max_model_calls == 7


def test_environment_overrides_defaults():
    config = AppConfig.from_sources(
        environ={
            "RAG_PDF_PATH": "env.pdf",
            "RAG_RETRIEVAL_TOP_K": "8",
            "RAG_EVIDENCE_TOP_N": "2",
        }
    )

    assert config.pdf_path == "env.pdf"
    assert config.retrieval_top_k == 8
    assert config.evidence_top_n == 2


def test_missing_agent_configuration_names_fields_without_secret_values():
    config = AppConfig.from_sources(
        environ={"DEEPSEEK_API_KEY": "super-secret-value"},
        api_key="",
    )

    with pytest.raises(ConfigurationError) as error:
        config.validate_for_agent()

    message = str(error.value)
    assert "DEEPSEEK_API_KEY" in message
    assert "DEEPSEEK_BASE_URL" in message
    assert "super-secret-value" not in message


@pytest.mark.parametrize(
    "name",
    [
        "RAG_RETRIEVAL_TOP_K",
        "RAG_EVIDENCE_TOP_N",
        "RAG_REQUEST_TIMEOUT_SECONDS",
        "RAG_TOTAL_TIMEOUT_SECONDS",
        "RAG_MAX_MODEL_CALLS",
    ],
)
def test_numeric_configuration_must_be_positive(name):
    with pytest.raises(ConfigurationError, match=name):
        AppConfig.from_sources(environ={name: "0"})


def test_network_retries_must_be_nonnegative():
    with pytest.raises(ConfigurationError, match="RAG_MAX_NETWORK_RETRIES"):
        AppConfig.from_sources(environ={"RAG_MAX_NETWORK_RETRIES": "-1"})
