from dataclasses import dataclass, field
import inspect
import logging
import re
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from src.evidence import CitationValidation, Evidence, build_evidence_list, validate_citations
from src.evidence_retention import (
    ParsedRequirements,
    build_retry_query,
    parse_evidence_requirements,
    select_retained_article_groups,
)
from src.results import ApplicationResult
from src.reliability import CallBudget, ReliabilityError
from src.observability import RequestObserver
from src.retrieval_fusion import chunk_identity
from src.query_scope import (
    QueryScope,
    QueryScopeClarificationRequired,
    QueryScopeError,
)
from src.query_decomposition import decompose_retrieval_targets, focused_query_variants


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
    query_scope: tuple[str, ...] = ()
    evidence_limit: int = 3


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
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
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
        self.input_cost_per_million = input_cost_per_million
        self.output_cost_per_million = output_cost_per_million

    def run(self, query: str, scope: QueryScope | None = None) -> AgentResponse:
        state = AgentState(
            original_query=query,
            retrieval_query=query,
            index_version_id=self.index_version_id,
        )
        budget = CallBudget(
            max_calls=self.max_model_calls,
            total_timeout_seconds=self.total_timeout_seconds,
            input_cost_per_million=self.input_cost_per_million,
            output_cost_per_million=self.output_cost_per_million,
        )
        observer = RequestObserver(state.request_id, self.index_version_id, self.model_ids)
        observer_token = active_observer.set(observer)
        try:
            request_retriever = self.retriever
            bind_scope = getattr(self.retriever, "for_scope", None)
            if bind_scope is not None:
                request_retriever = bind_scope(scope or QueryScope.unspecified())
                state.query_scope = request_retriever.scope.business_ids
                state.index_version_id = request_retriever.scope.snapshot_id
                state.trace.append(
                    {
                        "step": "bind_scope",
                        "snapshot_id": state.index_version_id,
                        "scope": list(state.query_scope),
                    }
                )
                state.evidence_limit = self._request_evidence_limit(
                    query, state.query_scope
                )
            response = self._run(state, query, budget, request_retriever)
        except QueryScopeClarificationRequired as exc:
            response = self._scope_clarification(state, str(exc))
        except QueryScopeError as exc:
            response = self._error(
                state,
                code="INVALID_QUERY_SCOPE",
                message=str(exc),
                retryable=False,
            )
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

    def _run(
        self,
        state: AgentState,
        query: str,
        budget: CallBudget,
        request_retriever,
    ) -> AgentResponse:
        score_cache: dict[tuple, float] = {}
        initial_results, decision = self._retrieve_rerank_grade(
            state,
            query,
            prior_results=[],
            score_cache=score_cache,
            budget=budget,
            request_retriever=request_retriever,
        )
        if decision.decision == "sufficient":
            return self._answer(state, budget)

        parsed_requirements = parse_evidence_requirements(
            query, decision.missing_requirements, state.query_scope
        )
        state.trace.append(self._requirement_trace(parsed_requirements))

        state.final_action = "retry"
        state.trace.append({"step": "retry", "retry_count": 1, "missing_requirements": decision.missing_requirements})
        state.retry_count = 1
        retry_query = self._build_retry_query(
            query,
            decision.missing_requirements,
            budget,
            parsed_requirements=parsed_requirements,
        )
        state.rewritten_query = retry_query
        state.retrieval_query = retry_query
        _, second_decision = self._retrieve_rerank_grade(
            state,
            retry_query,
            prior_results=initial_results,
            score_cache=score_cache,
            budget=budget,
            coverage_requirements=decision.missing_requirements,
            parsed_requirements=parsed_requirements,
            request_retriever=request_retriever,
        )
        if second_decision.decision == "sufficient":
            return self._answer(state, budget)
        with self._stage("grader"):
            confirmation = self._call_with_budget(
                self.grader.grade,
                state.original_query,
                state.evidences,
                budget=budget,
                scope_business_ids=state.query_scope,
            )
        state.trace.append(
            {
                "step": "confirm_grade",
                "decision": confirmation.decision,
                "missing_requirements": list(confirmation.missing_requirements),
            }
        )
        state.missing_requirements = list(confirmation.missing_requirements)
        if confirmation.decision == "sufficient":
            return self._answer(state, budget)
        return self._refuse(state)

    def _retrieve_rerank_grade(
        self,
        state: AgentState,
        retrieval_query: str,
        prior_results: list[dict],
        score_cache: dict[tuple, float],
        budget: CallBudget,
        request_retriever,
        coverage_requirements: list[str] | None = None,
        parsed_requirements: ParsedRequirements | None = None,
    ):
        state.trace.append({"step": "retrieve", "query": retrieval_query, "retry_count": state.retry_count})
        with self._stage("retrieval"):
            retrieved = request_retriever.retrieve(
                retrieval_query, top_k=self.retrieval_top_k
            )
        with self._stage("rerank"):
            focused = []
            if prior_results:
                focused = self._rerank_with_cache(
                    retrieval_query,
                    retrieved,
                    top_n=1,
                    score_cache=score_cache,
                )
                expanded = self._expand_focused_neighbors(focused, request_retriever)
                if len(expanded) > len(focused):
                    focused = self._rerank_with_cache(
                        retrieval_query,
                        expanded,
                        top_n=min(2, len(expanded)),
                        score_cache=score_cache,
                    )
                    retrieved = self._merge_results(retrieved, expanded)
            candidates = self._merge_results(prior_results, retrieved)
            if coverage_requirements:
                candidates = self._expand_complete_article_groups(
                    candidates, request_retriever
                )
                retry_targets = decompose_retrieval_targets(state.original_query)
                if len(state.query_scope) > 1 and len(retry_targets) > 1:
                    reranked = self._select_scope_target_coverage(
                        candidates,
                        focused_query_variants(retry_targets),
                        state.query_scope,
                        top_n=state.evidence_limit,
                        score_cache=score_cache,
                        preferred=focused,
                    )
                    state.trace.append(
                        {
                            "step": "retry_scope_target_preference",
                            "selected": [
                                {
                                    "business_id": (
                                        f"{item.get('spec_id')}@{item.get('edition_id')}"
                                    ),
                                    "article_id": item.get("article_id"),
                                    "chunk_id": item.get("chunk_id"),
                                }
                                for item in reranked
                            ],
                        }
                    )
                else:
                    reranked = self._rerank_with_cache(
                        state.original_query,
                        candidates,
                        top_n=state.evidence_limit,
                        score_cache=score_cache,
                    )
                    reranked = self._preserve_focused_evidence(
                        reranked, focused, top_n=state.evidence_limit
                    )
                retention = select_retained_article_groups(
                    parsed_requirements
                    or parse_evidence_requirements(
                        state.original_query,
                        coverage_requirements,
                        state.query_scope,
                    ),
                    candidates,
                    reranked=reranked,
                    evidence_limit=state.evidence_limit,
                    allowed_business_ids=state.query_scope,
                )
                reranked = list(retention.selected)
                state.trace.append(self._retention_trace(retention, state.evidence_limit))
            else:
                reranked = self._rerank_with_cache(
                    state.original_query,
                    candidates,
                    top_n=state.evidence_limit,
                    score_cache=score_cache,
                )
                reranked = self._preserve_focused_evidence(
                    reranked, focused, top_n=state.evidence_limit
                )
            targets = decompose_retrieval_targets(state.original_query)
            if (
                not coverage_requirements
                and len(state.query_scope) > 1
                and len(targets) > 1
            ):
                reranked = self._select_scope_target_coverage(
                    candidates,
                    focused_query_variants(targets),
                    state.query_scope,
                    top_n=state.evidence_limit,
                    score_cache=score_cache,
                    preferred=reranked,
                )
            elif (
                not coverage_requirements
                and len(state.query_scope) > 1
                and self._requests_per_scope_answer(state.original_query)
            ):
                reranked = self._select_scope_balance(
                    state.original_query,
                    candidates,
                    state.query_scope,
                    top_n=state.evidence_limit,
                    score_cache=score_cache,
                    preferred=reranked,
                )
        evidences = build_evidence_list(reranked)
        if coverage_requirements:
            retained_groups = state.trace[-1].get("retained_groups", [])
            state.trace.append(
                self._verify_final_evidence_context(
                    reranked, state.query_scope, retained_groups
                )
            )
        with self._stage("grader"):
            decision = self._call_with_budget(
                self.grader.grade,
                state.original_query,
                evidences,
                budget=budget,
                scope_business_ids=state.query_scope,
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

    def _rerank_with_cache(
        self,
        query: str,
        candidates: list[dict],
        *,
        top_n: int,
        score_cache: dict[tuple, float],
    ) -> list[dict]:
        score_candidates = getattr(self.reranker, "score_candidates", None)
        select_top = getattr(self.reranker, "select_top", None)
        if (
            not getattr(self.reranker, "supports_score_cache", True)
            or not callable(score_candidates)
            or not callable(select_top)
        ):
            return self.reranker.rerank(query, candidates, top_n=top_n)

        pending: list[dict] = []
        pending_keys: list[tuple] = []
        seen_pending = set()
        for candidate in candidates:
            key = self._rerank_cache_key(query, candidate)
            if key not in score_cache and key not in seen_pending:
                pending.append(candidate)
                pending_keys.append(key)
                seen_pending.add(key)

        if pending:
            newly_scored = score_candidates(query, pending)
            if len(newly_scored) != len(pending_keys):
                raise ValueError("reranker returned a different number of scored candidates")
            for key, scored in zip(pending_keys, newly_scored):
                score_cache[key] = float(scored["rerank_score"])

        scored_candidates = []
        for candidate in candidates:
            scored = candidate.copy()
            scored["rerank_score"] = score_cache[
                self._rerank_cache_key(query, candidate)
            ]
            scored_candidates.append(scored)
        return select_top(scored_candidates, top_n=top_n)

    @staticmethod
    def _requirement_trace(parsed: ParsedRequirements) -> dict[str, Any]:
        def serialize(requirement):
            return {
                "business_id": requirement.business_id,
                "article_id": requirement.article_id,
                "subrequirement": requirement.subrequirement,
                "source": requirement.source.value,
                "authoritative": requirement.authoritative,
                "status": requirement.status,
                "reason": requirement.reason,
            }

        return {
            "step": "parse_evidence_requirements",
            "question_requirements": [
                serialize(item) for item in parsed.question_requirements
            ],
            "grader_requirements": [
                serialize(item) for item in parsed.grader_requirements
            ],
        }

    @staticmethod
    def _retention_trace(retention, evidence_limit: int) -> dict[str, Any]:
        return {
            "step": "retain_article_groups",
            "evidence_limit": evidence_limit,
            "retained_groups": [
                {
                    "business_id": group.business_id,
                    "article_id": group.article_id,
                    "chunk_ids": list(group.chunk_ids),
                    "basis": group.basis,
                    "covered_text": group.covered_text,
                }
                for group in retention.retained_groups
            ],
            "fallbacks": [
                {
                    "subrequirement": item.subrequirement,
                    "reason": item.reason,
                    "candidate_articles": list(item.candidate_articles),
                }
                for item in retention.fallbacks
            ],
        }

    def _expand_complete_article_groups(self, candidates, request_retriever):
        """Expand same-article neighbors to a fixed point before group retention."""
        expand = getattr(request_retriever, "expand_neighbors", None)
        if not callable(expand):
            return candidates
        expanded = list(candidates)
        previous_count = -1
        while len(expanded) != previous_count:
            previous_count = len(expanded)
            expanded = self._merge_results(expanded, expand(expanded))
        return [
            {**item, "article_group_complete": True}
            if item.get("article_id")
            else item
            for item in expanded
        ]

    @staticmethod
    def _verify_final_evidence_context(
        selected: list[dict],
        allowed_business_ids: tuple[str, ...],
        retained_groups: list[dict],
    ) -> dict[str, Any]:
        allowed = set(allowed_business_ids)
        final_groups: dict[tuple[str, str], set] = {}
        out_of_scope = []
        for item in selected:
            business_id = f"{item.get('spec_id')}@{item.get('edition_id')}"
            if allowed and business_id not in allowed:
                out_of_scope.append(
                    {
                        "business_id": business_id,
                        "article_id": item.get("article_id"),
                        "chunk_id": item.get("chunk_id"),
                    }
                )
            if item.get("article_id"):
                final_groups.setdefault(
                    (business_id, str(item["article_id"])), set()
                ).add(item.get("chunk_id"))
        incomplete = []
        for group in retained_groups:
            key = (group["business_id"], group["article_id"])
            expected = set(group["chunk_ids"])
            actual = final_groups.get(key, set())
            if not expected <= actual:
                incomplete.append(
                    {
                        "business_id": key[0],
                        "article_id": key[1],
                        "missing_chunk_ids": sorted(expected - actual),
                    }
                )
        return {
            "step": "verify_final_evidence_context",
            "complete": not incomplete,
            "within_scope": not out_of_scope,
            "incomplete_groups": incomplete,
            "out_of_scope": out_of_scope,
        }

    def _rerank_cache_key(self, query: str, candidate: dict) -> tuple:
        return (
            query,
            self.index_version_id,
            candidate.get("document_id"),
            candidate.get("source"),
            candidate.get("chunk_id"),
            candidate.get("text"),
        )

    def _select_requirement_coverage(
        self,
        original_query: str,
        candidates: list[dict],
        requirements: list[str],
        *,
        top_n: int,
        score_cache: dict[tuple, float],
        preferred: list[dict] | None = None,
        protected: list[dict] | None = None,
        request_retriever=None,
    ) -> list[dict]:
        if top_n <= 0 or not candidates:
            return []

        original_ranked = self._rerank_with_cache(
            original_query,
            candidates,
            top_n=len(candidates),
            score_cache=score_cache,
        )
        coverage_queries = self._coverage_queries(requirements)
        protected_limit = min(
            1,
            max(0, top_n - min(len(coverage_queries), top_n)),
        )
        protected_unique = []
        protected_identities = set()
        for candidate in protected or []:
            identity = self._evidence_content_identity(candidate)
            if (
                identity not in protected_identities
                and len(protected_unique) < protected_limit
            ):
                protected_identities.add(identity)
                protected_unique.append(candidate)

        coverage = []
        coverage_identities = set(protected_identities)
        requirement_rankings = []
        for requirement in coverage_queries:
            requirement_candidates = self._candidates_for_requirement(
                requirement, candidates
            )
            requirement_rankings.append(
                self._rerank_with_cache(
                    requirement,
                    requirement_candidates,
                    top_n=len(requirement_candidates),
                    score_cache=score_cache,
                )
            )

        if len(requirement_rankings) > 1:
            rank_positions = []
            for ranked in requirement_rankings:
                rank_positions.append({
                    self._evidence_content_identity(candidate): index
                    for index, candidate in enumerate(ranked)
                })
            common_identities = set(rank_positions[0])
            for positions in rank_positions[1:]:
                common_identities.intersection_update(positions)
            if common_identities:
                consensus = min(
                    (
                        candidate
                        for candidate in original_ranked
                        if self._evidence_content_identity(candidate)
                        in common_identities
                    ),
                    key=lambda candidate: (
                        max(
                            positions[self._evidence_content_identity(candidate)]
                            for positions in rank_positions
                        ),
                        sum(
                            positions[self._evidence_content_identity(candidate)]
                            for positions in rank_positions
                        ),
                    ),
                )
                consensus_identity = self._evidence_content_identity(consensus)
                if consensus_identity not in coverage_identities:
                    coverage_identities.add(consensus_identity)
                    coverage.append(consensus)

        for ranked in requirement_rankings:
            if len(protected_unique) + len(coverage) >= top_n or not ranked:
                break
            best = ranked[0]
            identity = self._evidence_content_identity(best)
            if identity not in coverage_identities:
                coverage_identities.add(identity)
                coverage.append(best)

        expanded_coverage = self._expand_focused_neighbors(
            coverage, request_retriever or self.retriever
        )
        for candidate in expanded_coverage:
            if len(protected_unique) + len(coverage) >= top_n:
                break
            identity = self._evidence_content_identity(candidate)
            if identity not in coverage_identities:
                coverage_identities.add(identity)
                coverage.append(candidate)

        for candidate in preferred or []:
            if len(protected_unique) + len(coverage) >= top_n:
                break
            identity = self._evidence_content_identity(candidate)
            if identity not in coverage_identities:
                coverage_identities.add(identity)
                coverage.append(candidate)

        remaining = []
        seen = set(coverage_identities)
        for candidate in original_ranked:
            identity = self._evidence_content_identity(candidate)
            if identity in seen:
                continue
            seen.add(identity)
            remaining.append(candidate)

        supplemental = coverage
        remaining_slots = max(
            0,
            top_n - len(protected_unique) - len(supplemental),
        )
        return [
            *protected_unique,
            *remaining[:remaining_slots],
            *supplemental,
        ]

    def _select_scope_target_coverage(
        self,
        candidates: list[dict],
        focused_queries: list[str],
        business_ids: tuple[str, ...],
        *,
        top_n: int,
        score_cache: dict[tuple, float],
        preferred: list[dict],
    ) -> list[dict]:
        del score_cache
        selected = []
        seen = set()
        # A fixed equal quota loses evidence when one specification needs several
        # distinct clauses while another covers all sub-requirements in one clause.
        # The global evidence limit remains the bound; article de-duplication below
        # prevents a verbose document from filling slots with the same provision.
        per_document_limit = top_n
        selected_articles_by_document: dict[str, set[str]] = {
            business_id: set() for business_id in business_ids
        }
        fulfilled_targets: set[tuple[str, str]] = set()
        broad_coverage_documents: set[str] = set()
        normative_occurrences = self._normative_article_occurrences(candidates)
        for business_id in business_ids:
            scoped = [
                candidate
                for candidate in candidates
                if f"{candidate.get('spec_id')}@{candidate.get('edition_id')}"
                == business_id
            ]
            selected_articles = selected_articles_by_document[business_id]
            selected_for_document = 0
            for focused_query in focused_queries:
                if len(selected) >= top_n:
                    return selected
                if (business_id, focused_query) in fulfilled_targets:
                    continue
                if not self._focused_query_applies_to_business_id(
                    focused_query, business_id, candidates
                ):
                    continue
                ranked = sorted(
                    (
                        candidate
                        for candidate in scoped
                        if focused_query in candidate.get("document_query_ranks", {})
                        and self._matches_focused_intent(candidate, focused_query)
                    ),
                    key=lambda candidate: (
                        self._commentary_context_priority(candidate),
                        self._normative_occurrence_priority(
                            candidate, normative_occurrences
                        ),
                        -self._focused_overlap_score(candidate, focused_query),
                        candidate["document_query_ranks"][focused_query],
                        -(candidate.get("rrf_score") or 0.0),
                    ),
                )
                candidate = next(
                    (
                        item
                        for item in ranked
                        if chunk_identity(item) not in seen
                        and not (
                            item.get("article_id")
                            and item.get("article_id") in selected_articles
                        )
                    ),
                    None,
                )
                if candidate is None:
                    continue
                identity = chunk_identity(candidate)
                article_id = candidate.get("article_id")
                seen.add(identity)
                if article_id:
                    selected_articles.add(article_id)
                selected.append(candidate)
                covered_queries = []
                for covered_query in focused_queries:
                    if (
                        self._focused_query_applies_to_business_id(
                            covered_query, business_id, candidates
                        )
                        and covered_query
                        in candidate.get("document_query_ranks", {})
                        and self._matches_focused_intent(candidate, covered_query)
                    ):
                        fulfilled_targets.add((business_id, covered_query))
                        if self._focused_overlap_score(candidate, covered_query) > 0:
                            covered_queries.append(covered_query)
                if len(covered_queries) > 1:
                    broad_coverage_documents.add(business_id)
                selected_for_document += 1
                if selected_for_document >= per_document_limit:
                    break
        for focused_query in focused_queries:
            for business_id in business_ids:
                if len(selected) >= top_n:
                    return selected
                if business_id in broad_coverage_documents:
                    continue
                if not self._focused_query_applies_to_business_id(
                    focused_query, business_id, candidates
                ):
                    continue
                ranked = sorted(
                    (
                        candidate
                        for candidate in candidates
                        if f"{candidate.get('spec_id')}@{candidate.get('edition_id')}"
                        == business_id
                        and focused_query in candidate.get("document_query_ranks", {})
                        and self._matches_focused_intent(candidate, focused_query)
                    ),
                    key=lambda candidate: (
                        self._commentary_context_priority(candidate),
                        self._normative_occurrence_priority(
                            candidate, normative_occurrences
                        ),
                        -self._focused_overlap_score(candidate, focused_query),
                        candidate["document_query_ranks"][focused_query],
                    ),
                )
                candidate = next(
                    (
                        item
                        for item in ranked
                        if chunk_identity(item) not in seen
                        and not (
                            item.get("article_id")
                            and item.get("article_id")
                            in selected_articles_by_document[business_id]
                        )
                    ),
                    None,
                )
                if candidate is None:
                    continue
                seen.add(chunk_identity(candidate))
                if candidate.get("article_id"):
                    selected_articles_by_document[business_id].add(
                        candidate["article_id"]
                    )
                selected.append(candidate)
                fulfilled_targets.add((business_id, focused_query))
        for candidate in preferred:
            if len(selected) >= top_n:
                break
            identity = chunk_identity(candidate)
            if identity in seen:
                continue
            business_id = f"{candidate.get('spec_id')}@{candidate.get('edition_id')}"
            if business_id not in business_ids:
                continue
            article_id = candidate.get("article_id")
            if (
                article_id
                and article_id in selected_articles_by_document[business_id]
            ):
                continue
            if not any(
                focused_query in candidate.get("document_query_ranks", {})
                and self._matches_focused_intent(candidate, focused_query)
                for focused_query in focused_queries
                if self._focused_query_applies_to_business_id(
                    focused_query, business_id, candidates
                )
            ):
                continue
            seen.add(identity)
            if article_id:
                selected_articles_by_document[business_id].add(article_id)
            selected.append(candidate)
        return selected

    @staticmethod
    def _normative_article_occurrences(candidates: list[dict]) -> dict[tuple[str, str], int]:
        earliest: dict[tuple[str, str], int] = {}
        for candidate in candidates:
            article_id = candidate.get("article_id")
            page = candidate.get("pdf_page_start")
            if not article_id or page is None:
                continue
            business_id = f"{candidate.get('spec_id')}@{candidate.get('edition_id')}"
            key = (business_id, str(article_id))
            earliest[key] = min(earliest.get(key, page), page)
        return earliest

    @staticmethod
    def _normative_occurrence_priority(candidate: dict, earliest: dict[tuple[str, str], int]) -> int:
        article_id = candidate.get("article_id")
        page = candidate.get("pdf_page_start")
        if not article_id or page is None:
            return 0
        business_id = f"{candidate.get('spec_id')}@{candidate.get('edition_id')}"
        first_page = earliest.get((business_id, str(article_id)))
        return int(first_page is not None and page > first_page)

    @staticmethod
    def _commentary_context_priority(candidate: dict) -> int:
        """Prefer a direct provision over a commentary paragraph repeating it.

        Commentary remains eligible evidence.  This tie-breaker only affects the
        initial evidence choice when both candidates already match the same
        focused retrieval target.
        """
        text = str(candidate.get("text") or "").strip()
        article_id = re.escape(str(candidate.get("article_id") or ""))
        if article_id:
            text = re.sub(rf"^{article_id}\s*", "", text, count=1)
        return int(
            bool(
                re.match(r"^(?:条文说明|本条(?:文)?|第\s*[一二三四五六七八九十百\d]+\s*款)", text)
            )
        )

    def _select_scope_balance(
        self,
        query: str,
        candidates: list[dict],
        business_ids: tuple[str, ...],
        *,
        top_n: int,
        score_cache: dict[tuple, float],
        preferred: list[dict],
    ) -> list[dict]:
        """Keep the best available evidence for every explicitly compared scope."""
        focus_query = self._scope_balance_focus_query(query)
        ranked = self._rerank_with_cache(
            focus_query, candidates, top_n=len(candidates), score_cache=score_cache
        )
        rank_positions = {
            chunk_identity(candidate): index for index, candidate in enumerate(ranked)
        }
        selected = []
        seen = set()
        selected_articles: dict[str, set[str]] = {
            business_id: set() for business_id in business_ids
        }
        normative_occurrences = self._normative_article_occurrences(candidates)
        for business_id in business_ids:
            scoped = (
                item
                for item in ranked
                if f"{item.get('spec_id')}@{item.get('edition_id')}"
                == business_id
                and chunk_identity(item) not in seen
            )
            candidate = min(
                scoped,
                key=lambda item: (
                    self._commentary_context_priority(item),
                    self._normative_occurrence_priority(
                        item, normative_occurrences
                    ),
                    -self._focused_overlap_score(item, focus_query),
                    rank_positions[chunk_identity(item)],
                ),
                default=None,
            )
            if candidate is not None and len(selected) < top_n:
                seen.add(chunk_identity(candidate))
                selected.append(candidate)
                if candidate.get("article_id"):
                    selected_articles[business_id].add(candidate["article_id"])
        # A comparison request commonly needs both the principal rule and its
        # boundary clause. Before allowing repeated chunks from one provision,
        # give every explicit scope one chance to contribute a second distinct
        # article within the existing request evidence limit.
        for business_id in business_ids:
            if len(selected) >= top_n:
                break
            candidate = next(
                (
                    item
                    for item in ranked
                    if f"{item.get('spec_id')}@{item.get('edition_id')}"
                    == business_id
                    and chunk_identity(item) not in seen
                    and (
                        not item.get("article_id")
                        or item.get("article_id")
                        not in selected_articles[business_id]
                    )
                ),
                None,
            )
            if candidate is not None:
                seen.add(chunk_identity(candidate))
                selected.append(candidate)
                if candidate.get("article_id"):
                    selected_articles[business_id].add(candidate["article_id"])
        for candidate in [*preferred, *ranked]:
            if len(selected) >= top_n:
                break
            identity = chunk_identity(candidate)
            if identity not in seen:
                seen.add(identity)
                selected.append(candidate)
        return selected

    @staticmethod
    def _scope_balance_focus_query(query: str) -> str:
        match = re.search(r"对(.+?)的直接规定", query)
        return match.group(1) if match else query

    @staticmethod
    def _requests_per_scope_answer(query: str) -> bool:
        return bool(
            re.search(
                r"(?:两份|三份|各份|各规范|分别|各自|比较|对比)",
                query,
            )
        )

    def _request_evidence_limit(
        self, query: str, business_ids: tuple[str, ...]
    ) -> int:
        if len(business_ids) <= 1:
            return self.evidence_top_n
        targets = focused_query_variants(decompose_retrieval_targets(query))
        if len(targets) > 1:
            target_count = len(targets)
        elif self._requests_per_scope_answer(query):
            target_count = 2
        else:
            return self.evidence_top_n
        return min(
            8,
            max(self.evidence_top_n, len(business_ids) * target_count),
        )

    @staticmethod
    def _focused_query_applies_to_business_id(
        focused_query: str, business_id: str, candidates: list[dict]
    ) -> bool:
        normalized_query = re.sub(r"[^A-Z0-9]", "", focused_query.upper())
        codes_by_business: dict[str, set[str]] = {}
        for candidate in candidates:
            candidate_business_id = (
                f"{candidate.get('spec_id')}@{candidate.get('edition_id')}"
            )
            code = re.sub(
                r"[^A-Z0-9]", "", str(candidate.get("standard_code", "")).upper()
            )
            if code:
                codes_by_business.setdefault(candidate_business_id, set()).add(code)
        mentioned = {
            candidate_business_id
            for candidate_business_id, codes in codes_by_business.items()
            if any(code in normalized_query for code in codes)
        }
        return not mentioned or business_id in mentioned

    @staticmethod
    def _matches_focused_intent(candidate: dict, focused_query: str) -> bool:
        if "本标准适用于" in focused_query:
            text = str(candidate.get("text", ""))
            return bool(re.search(r"(?:本标准|本规范)适用于|必须执行本规范", text))
        text = str(candidate.get("text", ""))
        if "最高运行速度" in focused_query:
            return bool(
                "最高运行速度" in text
                and re.search(r"最高运行速度.{0,12}(?:应|不应|不得|可|按)", text)
                and not re.search(r"maximum running speed|速度效率", text, re.I)
            )
        if "防止自然灾害" in focused_query:
            return bool(re.search(r"防内涝|防止自然灾害|自然灾害侵害", text))
        if "穿越水域" in focused_query:
            return bool(re.search(r"河流|湖泊|水域|防淹门|防水淹", text))
        if "车辆基地" in focused_query:
            return bool(
                re.search(r"车辆基地|基地", text)
                and re.search(r"防洪|防淹|内涝", text)
            )
        if "设计年限" in focused_query:
            return bool(
                re.search(r"设计年限应", text)
                or all(term in text for term in ("初期", "近期", "远期"))
            )
        if "运能" in focused_query:
            return "运能" in text
        if "人员 新风量" in focused_query:
            if not re.search(r"新风|新鲜空气", text):
                return False
            if "区间" in focused_query:
                return "区间" in text
            if "车站公共区" in focused_query:
                return bool(
                    re.search(r"车站公共区|公共区", text)
                    or (
                        "区间" not in text
                        and re.search(
                        r"每个乘客[\s\S]{0,30}(?:新风|新鲜空气)", text
                        )
                    )
                )
            if "设备管理用房" in focused_query:
                return bool(
                    re.search(r"设备.{0,3}管理用房", text)
                    and re.search(r"工作人员", text)
                )
        return True

    @staticmethod
    def _coverage_queries(requirements: list[str]) -> list[str]:
        queries = []
        seen = set()
        for requirement in requirements:
            parts = [
                part.strip(" ：:")
                for part in re.split(r"[；;、]", requirement)
                if part.strip(" ：:")
            ]
            for part in parts or [requirement.strip()]:
                if part and part not in seen:
                    seen.add(part)
                    queries.append(part)
        return queries

    @staticmethod
    def _candidates_for_requirement(
        requirement: str, candidates: list[dict]
    ) -> list[dict]:
        """Honor an explicit specification/version or article named by a requirement."""
        normalized_requirement = re.sub(r"[^A-Z0-9]", "", requirement.upper())
        scoped = []
        for candidate in candidates:
            identifiers = (
                candidate.get("standard_code"),
                f"{candidate.get('spec_id')}@{candidate.get('edition_id')}",
            )
            if any(
                (normalized := re.sub(r"[^A-Z0-9]", "", str(identifier).upper()))
                and normalized in normalized_requirement
                for identifier in identifiers
            ):
                scoped.append(candidate)
        narrowed = scoped or candidates
        requested_articles = set(
            re.findall(r"(?<!\d)(\d+(?:\.\d+){2,})(?!\d)", requirement)
        )
        article_matches = [
            candidate
            for candidate in narrowed
            if candidate.get("article_id") in requested_articles
        ]
        if article_matches:
            return article_matches
        phrase = requirement
        for standard_code in {
            str(candidate.get("standard_code", "")).strip()
            for candidate in candidates
        }:
            if standard_code:
                phrase = re.sub(re.escape(standard_code), "", phrase, flags=re.I)
        phrase = re.sub(r"^(?:关于|对)", "", phrase.strip(" ：:，,"))
        phrase = re.sub(
            r"的?(?:具体)?(?:直接)?(?:要求|规定)(?:.*)$", "", phrase
        ).strip(" ：:，,")
        if not scoped:
            return narrowed
        phrase_matches = [
            candidate
            for candidate in narrowed
            if len(phrase) >= 4 and phrase in str(candidate.get("text", ""))
        ]
        if phrase_matches:
            return phrase_matches
        phrase_bigrams = {
            phrase[index : index + 2]
            for index in range(max(0, len(phrase) - 1))
            if re.fullmatch(r"[\u4e00-\u9fff]{2}", phrase[index : index + 2])
        }
        overlap = [
            (
                sum(bigram in str(candidate.get("text", "")) for bigram in phrase_bigrams),
                candidate,
            )
            for candidate in narrowed
        ]
        best_overlap = max((score for score, _ in overlap), default=0)
        if best_overlap >= 2:
            return [candidate for score, candidate in overlap if score == best_overlap]
        return narrowed

    @staticmethod
    def _focused_overlap_score(candidate: dict, focused_query: str) -> int:
        query_bigrams = {
            focused_query[index : index + 2]
            for index in range(max(0, len(focused_query) - 1))
            if re.fullmatch(
                r"[\u4e00-\u9fff]{2}", focused_query[index : index + 2]
            )
        }
        text = str(candidate.get("text", ""))
        return sum(bigram in text for bigram in query_bigrams)

    @staticmethod
    def _evidence_content_identity(candidate: dict) -> tuple:
        normalized_text = " ".join(str(candidate.get("text", "")).split())
        return (
            candidate.get("source"),
            normalized_text,
        )

    def _build_retry_query(
        self,
        query: str,
        missing_requirements: list[str],
        budget: CallBudget,
        parsed_requirements: ParsedRequirements | None = None,
    ) -> str:
        missing = "；".join(
            item.strip() for item in missing_requirements if item.strip()
        )
        if missing:
            return build_retry_query(parsed_requirements, missing) if parsed_requirements else missing
        if self.rewriter is None:
            return query
        with self._stage("rewrite"):
            return self._call_with_budget(
                self.rewriter.rewrite,
                query=query,
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
                scope_business_ids=state.query_scope,
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

    def _scope_clarification(self, state: AgentState, message: str) -> AgentResponse:
        state.final_action = "clarify_scope"
        state.missing_requirements = [message]
        state.trace.append({"step": "clarify_scope", "message": message})
        return AgentResponse(
            answer=message,
            state=state,
            result=ApplicationResult(
                result_type="refuse",
                message=message,
                missing_requirements=(message,),
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
        parameters = inspect.signature(method).parameters
        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        if "scope_business_ids" in kwargs and not (
            "scope_business_ids" in parameters or accepts_kwargs
        ):
            kwargs.pop("scope_business_ids")
        if "budget" in parameters:
            kwargs["budget"] = budget
        return method(*args, **kwargs)

    @staticmethod
    def _merge_results(existing: list[dict], added: list[dict]) -> list[dict]:
        merged = []
        seen = set()
        for result in [*existing, *added]:
            identity = chunk_identity(result)
            if identity not in seen:
                seen.add(identity)
                merged.append(result)
        return merged

    @staticmethod
    def _preserve_focused_evidence(
        reranked: list[dict], focused: list[dict], *, top_n: int
    ) -> list[dict]:
        if not focused or top_n <= 0:
            return reranked[:top_n]
        focused_unique = []
        focused_identities = set()
        for item in focused[:top_n]:
            identity = chunk_identity(item)
            if identity not in focused_identities:
                focused_identities.add(identity)
                focused_unique.append(item)
        remaining = [
            item
            for item in reranked
            if chunk_identity(item)
            not in focused_identities
        ]
        return [
            *remaining[: max(0, top_n - len(focused_unique))],
            *focused_unique,
        ]

    def _expand_focused_neighbors(
        self, focused: list[dict], request_retriever=None
    ) -> list[dict]:
        expand = getattr(request_retriever or self.retriever, "expand_neighbors", None)
        if expand is None:
            return focused
        return expand(focused)

    def _stage(self, name: str):
        observer = active_observer.get()
        if observer is None:
            from contextlib import nullcontext

            return nullcontext()
        return observer.stage(name)
