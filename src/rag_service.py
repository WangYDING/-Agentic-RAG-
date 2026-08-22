from dataclasses import dataclass
from typing import Any, Literal

from src.chat_memory import ChatMemory
from src.evidence import CitationValidation, Evidence, build_evidence_list, validate_citations


EMPTY_DOCUMENT_MESSAGE = "当前文档未提取到可用文本，可能是扫描版 PDF。"
QueryMode = Literal["history", "rewrite"]


class EmptyDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class RAGResponse:
    answer: str
    retrieval_query: str
    results: list[dict[str, Any]]
    evidences: list[Evidence]
    citation_validation: CitationValidation


class RAGService:
    """Shared baseline RAG orchestration for CLI and Web adapters."""

    def __init__(
        self,
        retriever,
        reranker,
        generator,
        rewriter=None,
        *,
        chunk_count: int | None = None,
        embedding_dim: int | None = None,
        cleaned_text_preview: str = "",
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.generator = generator
        self.rewriter = rewriter
        self.chunk_count = chunk_count
        self.embedding_dim = embedding_dim
        self.cleaned_text_preview = cleaned_text_preview

    @classmethod
    def from_pdf(
        cls,
        pdf_path: str,
        *,
        embedder=None,
        reranker=None,
        generator=None,
        rewriter=None,
        chunk_size: int = 300,
        overlap: int = 50,
        index_dir: str = ".rag_index",
        force_rebuild: bool = False,
    ):
        # Keep ML imports local so orchestration tests do not load model dependencies.
        from src.embedder import Embedder
        from src.generator import Generator
        from src.index_manager import EmptyDocumentError as IndexEmptyDocumentError
        from src.index_manager import IndexManager
        from src.reranker import Reranker
        from src.retriever import Retriever

        embedder = embedder or Embedder()
        try:
            managed_index = IndexManager(index_dir).build_or_load(
                pdf_path,
                embedder=embedder,
                chunk_size=chunk_size,
                overlap=overlap,
                force_rebuild=force_rebuild,
            )
        except IndexEmptyDocumentError as exc:
            raise EmptyDocumentError(str(exc)) from exc

        return cls(
            retriever=Retriever(managed_index.vector_store, embedder),
            reranker=reranker or Reranker(),
            generator=generator or Generator(),
            rewriter=rewriter,
            chunk_count=managed_index.manifest.chunk_count,
            embedding_dim=managed_index.manifest.embedding_dim,
            cleaned_text_preview=managed_index.cleaned_text_preview,
        )

    def answer(
        self,
        query: str,
        memory: ChatMemory,
        *,
        query_mode: QueryMode,
        top_k: int = 10,
        top_n: int = 3,
        use_rerank: bool = True,
    ) -> RAGResponse:
        history = memory.get_recent_history()
        retrieval_query = self._build_retrieval_query(query, memory, query_mode)
        retrieved_results = self.retriever.retrieve(retrieval_query, top_k=top_k)

        if use_rerank:
            results = self.reranker.rerank(query, retrieved_results, top_n=top_n)
        else:
            results = retrieved_results[:top_n]

        evidences = build_evidence_list(results)
        answer = self.generator.generate_answer(
            query=query,
            evidences=evidences,
            chat_history=history,
        )
        citation_validation = validate_citations(answer, evidences)
        memory.add_user_message(query)
        memory.add_assistant_message(answer)

        return RAGResponse(
            answer=answer,
            retrieval_query=retrieval_query,
            results=results,
            evidences=evidences,
            citation_validation=citation_validation,
        )

    def _build_retrieval_query(
        self,
        query: str,
        memory: ChatMemory,
        query_mode: QueryMode,
    ) -> str:
        if query_mode == "history":
            return memory.build_context_query(query)
        if query_mode == "rewrite":
            if self.rewriter is None:
                raise RuntimeError("query_mode='rewrite' requires a query rewriter")
            return self.rewriter.rewrite(
                query=query,
                chat_history=memory.get_recent_history(),
            )
        raise ValueError(f"不支持的 query_mode: {query_mode}")
