import argparse
import logging
from uuid import uuid4

from dotenv import load_dotenv

from src.agent_workflow import AgentResponse
from src.application import build_agent_workflow, build_multi_spec_agent_workflow
from src.config import AppConfig, ConfigurationError
from src.evidence import format_evidence_citation
from src.presentation import (
    configure_utf8_output,
    format_agent_trace,
    present_agent_response,
)
from src.observability import configure_json_logging
from src.query_scope import QueryScope, QueryScopeError, SpecEdition


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
    configure_json_logging()
    parser = argparse.ArgumentParser(description="Run the bounded Hybrid RAG Agent demo.")
    parser.add_argument("--pdf", help="覆盖 RAG_PDF_PATH")
    parser.add_argument("--index-dir", help="覆盖 RAG_INDEX_DIR")
    parser.add_argument("--question", help="直接提供问题；省略时进入交互输入。")
    parser.add_argument("--knowledge-base-root", help="使用已发布的多规范知识库目录")
    parser.add_argument("--catalog", default="data/spec_catalog.v1.json")
    parser.add_argument("--all-specs", action="store_true", help="查询当前快照全部规范")
    parser.add_argument(
        "--spec-version",
        action="append",
        default=[],
        metavar="SPEC_ID@EDITION_ID",
        help="限定规范版本；可重复提供",
    )
    parser.add_argument("--expected-snapshot", help="要求活动快照精确匹配此 ID")
    args = parser.parse_args(argv)

    load_dotenv()
    try:
        config = AppConfig.from_sources(
            pdf_path=args.pdf,
            index_dir=args.index_dir,
        )
        if args.knowledge_base_root:
            workflow = build_multi_spec_agent_workflow(
                config,
                knowledge_base_root=args.knowledge_base_root,
                catalog_path=args.catalog,
                expected_snapshot_id=args.expected_snapshot,
            )
        else:
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

    try:
        scope = _query_scope_from_args(args) if args.knowledge_base_root else None
    except QueryScopeError as exc:
        print(f"范围错误：{exc}")
        return 2
    response = workflow.run(question, scope=scope)
    print(render_response(response))
    return 1 if response.result_type == "error" else 0


def _query_scope_from_args(args) -> QueryScope:
    if args.all_specs and args.spec_version:
        raise QueryScopeError("--all-specs 与 --spec-version 不能同时使用")
    if args.all_specs:
        return QueryScope.all_documents()
    if args.spec_version:
        versions = []
        for value in args.spec_version:
            spec_id, separator, edition_id = value.rpartition("@")
            if not separator:
                raise QueryScopeError("--spec-version 必须使用 SPEC_ID@EDITION_ID")
            versions.append(SpecEdition(spec_id, edition_id))
        return QueryScope.exact_versions(versions)
    return QueryScope.unspecified()


if __name__ == "__main__":
    raise SystemExit(main())
