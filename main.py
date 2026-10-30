from dotenv import load_dotenv

from src.chat_memory import ChatMemory
from src.config import AppConfig, ConfigurationError
from src.embedder import Embedder
from src.evidence import format_evidence_citation
from src.generator import Generator
from src.rag_service import EmptyDocumentError, RAGService
from src.reranker import Reranker

if __name__ == "__main__":
    load_dotenv()
    config = AppConfig.from_sources()
    try:
        config.validate_for_agent()
        service = RAGService.from_pdf(
            config.pdf_path,
            index_dir=config.index_dir,
            embedder=Embedder(config.embedding_model),
            reranker=Reranker(config.reranker_model),
            generator=Generator(
                api_key=config.api_key,
                base_url=config.api_base_url,
                model=config.generation_model,
            ),
        )
    except (ConfigurationError, EmptyDocumentError) as exc:
        print(f"配置错误：{exc}")
        exit()

    print(f"chunks数量: {service.chunk_count}")
    print("embedding完成")
    print("向量维度:", service.embedding_dim)
    memory = ChatMemory(max_turns=3)

    print(service.cleaned_text_preview)

    print("\n请输入问题（输入 exit 退出）")

    while True:
        query = input("\n用户：").strip()
        if query.lower() == "exit":
            print("已退出。")
            break

        response = service.answer(
            query=query,
            memory=memory,
            query_mode="history",
            top_k=config.retrieval_top_k,
            top_n=config.evidence_top_n,
            use_rerank=True,
        )

        print("\n系统回答：")
        print(response.answer)

        print("\n引用来源：")
        for evidence in response.evidences:
            print(format_evidence_citation(evidence))
        if not response.citation_validation.valid:
            print("引用校验错误:", response.citation_validation.errors)
