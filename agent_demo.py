import argparse

from dotenv import load_dotenv

from src.agent_workflow import AgentResponse
from src.application import build_agent_workflow
from src.config import AppConfig, ConfigurationError
from src.evidence import format_evidence_citation
from src.presentation import configure_utf8_output, format_agent_trace


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
    configure_utf8_output()
    parser = argparse.ArgumentParser(description="Run the bounded Hybrid RAG Agent demo.")
    parser.add_argument("--pdf", help="覆盖 RAG_PDF_PATH")
    parser.add_argument("--index-dir", help="覆盖 RAG_INDEX_DIR")
    parser.add_argument("--question", help="直接提供问题；省略时进入交互输入。")
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        config = AppConfig.from_sources(
            pdf_path=args.pdf,
            index_dir=args.index_dir,
        )
        workflow = build_agent_workflow(config)
    except ConfigurationError as exc:
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
