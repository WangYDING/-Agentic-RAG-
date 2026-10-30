from dataclasses import dataclass, field
import inspect
import logging
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from src.evidence import CitationValidation, Evidence, build_evidence_list, validate_citations
from src.results import ApplicationResult
from src.reliability import CallBudget, ReliabilityError
from src.observability import RequestObserver


REFUSAL_MESSAGE = "当前规范及已检索证据不足以完整回答该问题。"
logger = logging.getLogger(__name__)
active_observer: ContextVar[RequestObserver | None] = ContextVar(
    "active_request_observer", default=None
)


@dataclass
class AgentState:
    original_query: str
    retrieval_query: str
    rewritten_query: str | None = None
    retry_count: int = 0
    evidences: list[Evidence] = field(default_factory=list)
    sufficiency_decision: str | None = None
    missing_requirements: list[str] = field(default_factory=list)
    final_action: str | None = None
    citation_validation: CitationValidation | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    request_id: str = field(default_factory=lambda: uuid4().hex)
    index_version_id: str | None = None


@dataclass(frozen=True)
class AgentResponse:
    answer: str
    state: AgentState
    result: ApplicationResult

    @property
    def result_type(self) -> str:
        return self.result.result_type

    @property
    def request_id(self) -> str:
        return self.result.request_id

    @property
    def error_code(self) -> str | None:
        return self.result.error_code

    @property
    def retryable(self) -> bool:
        return self.result.retryable


class AgentWorkflow:
    """Bounded retrieve-grade-retry workflow with at most one retry."""

    def __init__(
        self,
        retriever,
        reranker,
        grader,
        generator,
        rewriter=None,
        *,
        max_retries: int = 1,
        retrieval_top_k: int = 10,
        evidence_top_n: int = 3,
        max_model_calls: int = 6,
        total_timeout_seconds: float = 90.0,
        index_version_id: str | None = None,
        model_ids: dict[str, str] | None = None,
    ):
        if max_retries != 1:
            raise ValueError("AgentWorkflow requires max_retries=1")
        self.retriever = retriever
        self.reranker = reranker
        self.grader = grader
        self.generator = generator
        self.rewriter = rewriter
        self.max_retries = max_retries
        self.retrieval_top_k = retrieval_top_k
        self.evidence_top_n = evidence_top_n
        self.max_model_calls = max_model_calls
        self.total_timeout_seconds = total_timeout_seconds
        self.index_version_id = index_version_id
        self.model_ids = dict(model_ids or {})

    def run(self, query: str) -> AgentResponse:
        state = AgentState(
            original_query=query,
            retrieval_query=query,
            index_version_id=self.index_version_id,
        )
        budget = CallBudget(
            max_calls=self.max_model_calls,
            total_timeout_seconds=self.total_timeout_seconds,
        )
        observer = RequestObserver(state.request_id, self.index_version_id, self.model_ids)
        observer_token = active_observer.set(observer)
        try:
            response = self._run(state, query, budget)
        except ReliabilityError as exc:
            logger.warning("request failed request_id=%s code=%s", state.request_id, exc.code)
            response = self._error(state, code=exc.code, message=exc.public_message, retryable=exc.retryable)
        except Exception:
            logger.exception("unexpected request failure request_id=%s", state.request_id)
            response = self._error(
                state,
                code="INTERNAL_ERROR",
                message="请求处理失败，请稍后重试。",
                retryable=True,
            )
        observer.finish(response, budget)
        active_observer.reset(observer_token)
        return response

    def _run(self, state: AgentState, query: str, budget: CallBudget) -> AgentResponse:
        initial_results, decision = self._retrieve_rerank_grade(
            state, query, prior_results=[], budget=budget
        )
        if decision.decision == "sufficient":
            return self._answer(state, budget)

        state.final_action = "retry"
        state.trace.append({"step": "retry", "retry_count": 1, "missing_requirements": decision.missing_requirements})
        state.retry_count = 1
        retry_query = self._build_retry_query(query, decision.missing_requirements, budget)
        state.rewritten_query = retry_query
        state.retrieval_query = retry_query
        _, second_decision = self._retrieve_rerank_grade(
            state, retry_query, prior_results=initial_results, budget=budget
        )
        if second_decision.decision == "sufficient":
            return self._answer(state, budget)
        return self._refuse(state)

    def _retrieve_rerank_grade(
        self,
        state: AgentState,
        retrieval_query: str,
        prior_results: list[dict],
        budget: CallBudget,
    ):
        state.trace.append({"step": "retrieve", "query": retrieval_query, "retry_count": state.retry_count})
        with self._stage("retrieval"):
            retrieved = self.retriever.retrieve(
                retrieval_query, top_k=self.retrieval_top_k
            )
        candidates = self._merge_results(prior_results, retrieved)
        with self._stage("rerank"):
            reranked = self.reranker.rerank(
                state.original_query, candidates, top_n=self.evidence_top_n
            )
        evidences = build_evidence_list(reranked)
        with self._stage("grader"):
            decision = self._call_with_budget(
                self.grader.grade, state.original_query, evidences, budget=budget
            )
        state.evidences = evidences
        state.sufficiency_decision = decision.decision
        state.missing_requirements = list(decision.missing_requirements)
        state.trace.append({
            "step": "grade",
            "decision": decision.decision,
            "missing_requirements": list(decision.missing_requirements),
            "retry_count": state.retry_count,
        })
        return candidates, decision

    def _build_retry_query(
        self, query: str, missing_requirements: list[str], budget: CallBudget
    ) -> str:
        missing = "；".join(missing_requirements) if missing_requirements else "完整回答所需的缺失信息"
        targeted_query = f"{query}\n补充检索目标：{missing}"
        if self.rewriter is None:
            return targeted_query
        with self._stage("rewrite"):
            return self._call_with_budget(
                self.rewriter.rewrite,
                query=targeted_query,
                chat_history=[],
                budget=budget,
            )

    def _answer(self, state: AgentState, budget: CallBudget) -> AgentResponse:
        with self._stage("generation"):
            answer = self._call_with_budget(
                self.generator.generate_answer,
                query=state.original_query,
                evidences=state.evidences,
                chat_history=[],
                budget=budget,
            )
        state.trace.append({"step": "answer"})
        state.citation_validation = validate_citations(answer, state.evidences)
        state.trace.append({"step": "citation_validation", "valid": state.citation_validation.valid})
        if not state.citation_validation.valid:
            state.final_action = "error"
            state.trace.append({
                "step": "error",
                "error_code": "INVALID_CITATION",
            })
            message = "生成结果未通过引用校验，已阻止返回。"
            return AgentResponse(
                answer=message,
                state=state,
                result=ApplicationResult(
                    result_type="error",
                    message=message,
                    error_code="INVALID_CITATION",
                    retryable=False,
                    request_id=state.request_id,
                    index_version_id=state.index_version_id,
                    trace=tuple(state.trace),
                ),
            )
        state.final_action = "answer"
        return AgentResponse(
            answer=answer,
            state=state,
            result=ApplicationResult(
                result_type="answer",
                message=answer,
                request_id=state.request_id,
                index_version_id=state.index_version_id,
                trace=tuple(state.trace),
            ),
        )

    def _refuse(self, state: AgentState) -> AgentResponse:
        detail = ""
        if state.missing_requirements:
            detail = " 缺少的信息：" + "；".join(state.missing_requirements) + "。"
        state.final_action = "refuse"
        state.trace.append({"step": "refuse", "missing_requirements": list(state.missing_requirements)})
        message = REFUSAL_MESSAGE + detail
        return AgentResponse(
            answer=message,
            state=state,
            result=ApplicationResult(
                result_type="refuse",
                message=message,
                missing_requirements=tuple(state.missing_requirements),
                request_id=state.request_id,
                index_version_id=state.index_version_id,
                trace=tuple(state.trace),
            ),
        )

    def _error(
        self,
        state: AgentState,
        *,
        code: str,
        message: str,
        retryable: bool,
    ) -> AgentResponse:
        state.final_action = "error"
        state.trace.append({"step": "error", "error_code": code})
        return AgentResponse(
            answer=message,
            state=state,
            result=ApplicationResult(
                result_type="error",
                message=message,
                request_id=state.request_id,
                index_version_id=state.index_version_id,
                error_code=code,
                retryable=retryable,
                trace=tuple(state.trace),
            ),
        )

    @staticmethod
    def _call_with_budget(method, *args, budget: CallBudget, **kwargs):
        if "budget" in inspect.signature(method).parameters:
            kwargs["budget"] = budget
        return method(*args, **kwargs)

    @staticmethod
    def _merge_results(existing: list[dict], added: list[dict]) -> list[dict]:
        merged = []
        seen = set()
        for result in [*existing, *added]:
            identity = (result.get("source"), result.get("chunk_id"))
            if identity not in seen:
                seen.add(identity)
                merged.append(result)
        return merged

    def _stage(self, name: str):
        observer = active_observer.get()
        if observer is None:
            from contextlib import nullcontext

            return nullcontext()
        return observer.stage(name)
