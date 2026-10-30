import argparse
import logging
from uuid import uuid4

from dotenv import load_dotenv

from src.agent_workflow import AgentResponse
from src.application import build_agent_workflow
from src.config import AppConfig, ConfigurationError
from src.evidence import format_evidence_citation
from src.presentation import (
    configure_utf8_output,
    format_agent_trace,
    present_agent_response,
)


logger = logging.getLogger(__name__)


def render_response(response: AgentResponse) -> str:
    state = response.state
    public = present_agent_response(response)
    lines = [f"### {public.heading}", "", public.message]
    lines.extend(["", *public.details])
    if public.show_evidence:
        lines.extend(["", "### Evidence", ""])
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
    except Exception:
        request_id = uuid4().hex
        logger.exception("application initialization failed request_id=%s", request_id)
        print(f"初始化失败，请检查本地文件和服务配置。 request_id: {request_id}")
        return 1

    question = args.question or input("请输入问题：").strip()
    if not question:
        print("问题不能为空。")
        return 2

    response = workflow.run(question)
    print(render_response(response))
    return 1 if response.result_type == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
