from src.agent_workflow import AgentResponse


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
