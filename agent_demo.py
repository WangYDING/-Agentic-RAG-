import argparse
import os
from collections.abc import Mapping

from dotenv import load_dotenv

from src.agent_workflow import AgentResponse, AgentWorkflow
from src.evidence import format_evidence_citation


REQUIRED_ENV_VARS = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
)


class DemoConfigurationError(RuntimeError):
    pass


def validate_environment(environ: Mapping[str, str] | None = None) -> None:
    values = os.environ if environ is None else environ
    missing = [name for name in REQUIRED_ENV_VARS if not values.get(name, "").strip()]
    if missing:
        names = ", ".join(missing)
        raise DemoConfigurationError(
            f"缺少 DeepSeek 配置：{names}。请复制 .env.example 为 .env 并填写有效值。"
        )


def build_agent_workflow(
    pdf_path: str = "data/raw/城市轨道交通工程设计标准.pdf",
    index_dir: str = ".rag_index",
) -> AgentWorkflow:
    validate_environment()

    # Keep model imports local so formatting/configuration tests stay lightweight.
    from eval.bm25 import BM25Retriever
    from eval.run_agent_test import HybridRetriever
    from src.embedder import Embedder
    from src.evidence_sufficiency import EvidenceSufficiencyGrader
    from src.generator import Generator
    from src.index_manager import IndexManager
    from src.query_rewriter import QueryRewriter
    from src.reranker import Reranker
    from src.retriever import Retriever

    embedder = Embedder()
    managed = IndexManager(index_dir).build_or_load(pdf_path, embedder=embedder)
    hybrid_retriever = HybridRetriever(
        Retriever(managed.vector_store, embedder),
        BM25Retriever(managed.vector_store.chunk_records),
    )
    return AgentWorkflow(
        retriever=hybrid_retriever,
        reranker=Reranker(),
        grader=EvidenceSufficiencyGrader(),
        generator=Generator(),
        rewriter=QueryRewriter(),
    )


def format_agent_trace(response: AgentResponse) -> list[str]:
    lines = []
    for event in response.state.trace:
        step = event.get("step")
        if step == "retrieve":
            lines.append("retrieve")
        elif step == "grade":
            lines.append(f"grade: {event.get('decision', 'unknown')}")
        elif step == "retry":
            lines.append("retry")
        elif step == "answer":
            lines.append("generate")
        elif step == "citation_validation":
            valid = str(bool(event.get("valid"))).lower()
            lines.append(f"citation_validate: {valid}")
        elif step == "refuse":
            lines.append("refuse")
    return lines


def render_response(response: AgentResponse) -> str:
    state = response.state
    lines = ["### Final Answer", "", response.answer, "", "### Evidence", ""]
    if state.evidences:
        lines.extend(
            format_evidence_citation(evidence)
            for evidence in state.evidences
        )
    else:
        lines.append("无")

    lines.extend(["", "### Agent Trace", ""])
    lines.extend(format_agent_trace(response))
    lines.extend(
        [
            "",
            f"retry_count: {state.retry_count}",
            f"final_action: {state.final_action}",
        ]
    )
    if state.missing_requirements:
        lines.append("missing_requirements:")
        lines.extend(f"- {item}" for item in state.missing_requirements)
    else:
        lines.append("missing_requirements: []")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the bounded Hybrid RAG Agent demo.")
    parser.add_argument("--pdf", default="data/raw/城市轨道交通工程设计标准.pdf")
    parser.add_argument("--index-dir", default=".rag_index")
    parser.add_argument("--question", help="直接提供问题；省略时进入交互输入。")
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        workflow = build_agent_workflow(args.pdf, args.index_dir)
    except DemoConfigurationError as exc:
        print(f"配置错误：{exc}")
        return 2

    question = args.question or input("请输入问题：").strip()
    if not question:
        print("问题不能为空。")
        return 2

    response = workflow.run(question)
    print(render_response(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
