from src.chat_memory import ChatMemory
from src.evidence import format_evidence_citation
from src.rag_service import EmptyDocumentError, RAGService

if __name__ == "__main__":
    pdf_path = "data/raw/城市轨道交通工程设计标准.pdf"
    try:
        service = RAGService.from_pdf(pdf_path)
    except EmptyDocumentError as exc:
        print(exc)
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
            top_k=10,
            top_n=3,
            use_rerank=True,
        )

        print("\n系统回答：")
        print(response.answer)

        print("\n引用来源：")
        for evidence in response.evidences:
            print(format_evidence_citation(evidence))
        if not response.citation_validation.valid:
            print("引用校验错误:", response.citation_validation.errors)
