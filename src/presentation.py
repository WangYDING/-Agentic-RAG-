import sys
from dataclasses import dataclass

from src.agent_workflow import AgentResponse


@dataclass(frozen=True)
class ResultPresentation:
    heading: str
    message: str
    severity: str
    show_evidence: bool
    details: tuple[str, ...]


def present_agent_response(response: AgentResponse) -> ResultPresentation:
    if response.result_type == "answer":
        return ResultPresentation(
            heading="Final Answer",
            message=response.answer,
            severity="success",
            show_evidence=True,
            details=(f"request_id: {response.request_id}",),
        )
    if response.result_type == "refuse":
        return ResultPresentation(
            heading="Refusal",
            message=response.answer,
            severity="info",
            show_evidence=False,
            details=(f"request_id: {response.request_id}",),
        )
    return ResultPresentation(
        heading="Service Error",
        message=response.answer,
        severity="error",
        show_evidence=False,
        details=(
            f"request_id: {response.request_id}",
            f"error_code: {response.error_code or 'INTERNAL_ERROR'}",
            f"retryable: {str(response.retryable).lower()}",
        ),
    )


def configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


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
        elif step == "error":
            lines.append(f"error: {event.get('error_code', 'INTERNAL_ERROR')}")
    return lines
