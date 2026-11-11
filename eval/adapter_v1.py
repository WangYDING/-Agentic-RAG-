"""Serial, observation-only adapter. Never builds a workflow or model client."""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import logging
import re
import time
from functools import wraps

from eval.contract_v1 import OBSERVATION_VERSION, validate_rag_input, validate_observation
from src.query_scope import QueryScope
from eval.usage_v1 import observe_provider, summarize_usage


def plain(value):
    if hasattr(value, "to_dict"):
        return plain(value.to_dict())
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    return {"unserializable_type": type(value).__name__}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


class _Proxy:
    def __init__(self, inner, events, methods):
        self._inner, self._events, self._methods = inner, events, methods

    def __getattr__(self, name):
        method = getattr(self._inner, name)  # preserve missing attributes/capabilities
        if name not in self._methods or not callable(method):
            return method

        @wraps(method)  # preserve signature; workflow inspects budget/scope parameters
        def call(*args, **kwargs):
            bound = inspect.signature(method).bind(*args, **kwargs)
            event = {"method": name, "arguments": plain(copy.deepcopy({
                key: val for key, val in bound.arguments.items() if key != "budget"
            })), "output": None, "completed": False}
            self._events.append(event)
            try:
                result = method(*args, **kwargs)
                if name == "for_scope":
                    event["completed"] = True
                    return _Proxy(result, self._events, self._methods)
                event["output"] = copy.deepcopy(plain(result))
                event["completed"] = True
                return result
            except Exception as exc:
                event["exception_type"] = type(exc).__name__
                raise
        return call


class _Metrics(logging.Handler):
    def __init__(self):
        super().__init__()
        self.rows = []

    def emit(self, record):
        if getattr(record, "event", None) == "request_completed":
            self.rows.append(copy.deepcopy(record.fields))


class WorkflowAdapter:
    """Use on an exclusively owned workflow, one request at a time.

    identities maps legacy source -> (stable document ID, edition); never use gold
    to infer identity. Missing mapping yields null normalized stage plus raw data.
    """
    def __init__(self, workflow, *, identities=None, pricing=None):
        self.workflow = workflow
        self.identities = identities or {}
        self.pricing = pricing

    def check_binding(self, configuration, knowledge, source, *, require_provider_policy=False):
        from pathlib import Path
        from eval.fingerprints_v1 import sha256
        import src.agent_workflow as implementation
        if sha256(implementation.__file__) != source["source_hashes"].get("src/agent_workflow.py"):
            raise ValueError("imported workflow code differs from bound RAG source")
        for name, expected in source["source_hashes"].items():
            if name.startswith("src/"):
                imported = Path(implementation.__file__).parent / name[4:]
                if not imported.is_file() or sha256(imported) != expected:
                    raise ValueError("imported RAG source differs from bound snapshot: " + name)
        workflow = self.workflow
        if workflow.index_version_id != knowledge["snapshot_id"]:
            raise ValueError("workflow index snapshot differs from freeze")
        cfg = configuration["public_config"]
        for key in ("retrieval_top_k", "evidence_top_n", "max_model_calls", "total_timeout_seconds"):
            if key not in cfg or getattr(workflow, key, None) != cfg[key]:
                raise ValueError("workflow configuration mismatch: " + key)
        if workflow.model_ids != {k: v["id"] for k, v in configuration["models"].items()}:
            raise ValueError("workflow model IDs mismatch")
        if configuration.get("api_endpoint_sha256"):
            from eval.fingerprints_v1 import endpoint_hash
            for name in ("grader", "generator", "rewriter"):
                component = getattr(workflow, name, None)
                if component is not None:
                    client = getattr(component, "client", None)
                    if client is None or endpoint_hash(getattr(client, "base_url", "")) != configuration["api_endpoint_sha256"]:
                        raise ValueError("provider endpoint differs from freeze: " + name)
        if require_provider_policy:
            embedder = getattr(workflow.retriever, "embedder", None)
            if (getattr(embedder, "model_name", None) != cfg["embedding_model"]
                    or getattr(embedder, "model_revision", None) != cfg["embedding_revision"]):
                raise ValueError("actual embedding model/revision differs from freeze")
            for name in ("grader", "generator", "rewriter"):
                component = getattr(workflow, name, None)
                if component is None:
                    continue
                policy = getattr(component, "call_policy", None)
                client = getattr(component, "client", None)
                if getattr(component, "model", None) != cfg["generation_model"]:
                    raise ValueError("component model differs from freeze: " + name)
                if (getattr(policy, "request_timeout_seconds", None) != cfg["request_timeout_seconds"]
                        or getattr(policy, "max_network_retries", None) != cfg["max_network_retries"]):
                    raise ValueError("provider retry/timeout policy differs from freeze: " + name)
                if getattr(client, "max_retries", None) != 0:
                    raise ValueError("hidden SDK retry policy prevents complete usage observation: " + name)

    def _refs(self, rows, prefix):
        if rows is None:
            return None
        refs = []
        for i, row in enumerate(rows):
            doc = row.get("spec_id") or row.get("document_id")
            version = row.get("edition_id") or row.get("document_version")
            if not (doc and version):
                doc, version = self.identities.get(row.get("source"), (None, None))
            page = row.get("pdf_page_start") or row.get("page_start") or row.get("page")
            if not (doc and version and type(page) is int and page >= 1):
                return None
            refs.append({"evidence_id": row.get("evidence_id") or f"{prefix}-{i+1}",
                         "document_id": doc, "document_version": version, "page": page,
                         "page_end": row.get("pdf_page_end") or row.get("page_end") or page,
                         "article": row.get("article_id") or row.get("article"),
                         "table": row.get("table_id") or row.get("table"),
                         "locator": row.get("display_ref") or row.get("locator"),
                         "quote": row.get("text") or row.get("quote"),
                         "chunk_id": row.get("chunk_id")})
            if not any(refs[-1].get(key) for key in ("article", "table", "locator", "quote")):
                return None
        return refs

    def __call__(self, public):
        validate_rag_input(public)
        scope = public["query_scope"]
        if set(scope) - {"spec_ids", "edition_ids"}:
            raise ValueError("scope accepts only spec_ids/edition_ids; no private annotations")
        parsed_scope = QueryScope.from_request_payload(copy.deepcopy(scope))
        workflow = self.workflow
        events, originals = [], {}
        handler = _Metrics()
        logger = logging.getLogger("rag.request")
        old_level = logger.level
        response, failure = None, None
        started = time.monotonic()
        try:
            for attr, methods in {
                "retriever": {"for_scope", "retrieve", "expand_neighbors"},
                "reranker": {"rerank", "score_candidates", "select_top"},
                "generator": {"generate_answer"},
            }.items():
                if hasattr(workflow, attr):
                    originals[attr] = getattr(workflow, attr)
                    setattr(workflow, attr, _Proxy(originals[attr], events, methods))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            started = time.monotonic()
            try:
                with observe_provider(workflow) as provider_events:
                    response = workflow.run(public["question"], scope=parsed_scope)
            except Exception as exc:
                failure = {"code": "ADAPTER_SYSTEM_EXCEPTION", "exception_type": type(exc).__name__}
        finally:
            elapsed = (time.monotonic() - started) * 1000
            logger.removeHandler(handler)
            logger.setLevel(old_level)
            for attr, original in originals.items():
                setattr(workflow, attr, original)
        state = getattr(response, "state", None)
        action = getattr(state, "final_action", None) or getattr(response, "result_type", "error")
        action = {"clarify_scope": "clarify", "evidence_insufficient": "refuse"}.get(action, action)
        if action not in {"answer", "refuse", "clarify", "error"}:
            failure = {"code": "UNMAPPED_ACTION", "raw_action": action}
            action = "error"
        request_id = getattr(response, "request_id", None)
        measurements = next((r for r in handler.rows if r.get("request_id") == request_id), {})
        usage = summarize_usage(locals().get("provider_events", []), measurements.get("model_calls"), self.pricing)
        retrievals = [e for e in events if e["method"] == "retrieve"]
        selections = [e for e in events if e["method"] in {"rerank", "select_top"}]
        generators = [e for e in events if e["method"] == "generate_answer"]
        rounds = []
        for i, event in enumerate(retrievals):
            start = next(j for j, e in enumerate(events) if e is event)
            stop = next(j for j, e in enumerate(events) if e is retrievals[i+1]) if i+1 < len(retrievals) else len(events)
            selected = [e for e in events[start+1:stop]
                        if e["method"] in {"rerank", "select_top"}]
            rounds.append({"round_id": f"retrieve-{i+1}",
                           "candidates": self._refs(event["output"], f"R{i+1}"),
                           "reranked": self._refs(selected[-1]["output"], f"S{i+1}") if selected else None})
        final_raw = plain(getattr(state, "evidences", None))
        final_refs = self._refs(final_raw, "F")
        context = self._refs(generators[-1]["arguments"].get("evidences"), "G") if generators else None
        scope_values = list(getattr(state, "query_scope", ())) if state is not None else None
        scope_bound = bool(scope_values) or any(step.get("step") == "bind_scope" for step in getattr(state, "trace", []))
        bound_scope = scope_values if scope_bound else None
        answer = getattr(response, "answer", None)
        citations = []
        available = {ref["evidence_id"]: ref for ref in (context or [])}
        for cid in sorted(set(re.findall(r"\[(E\d+)\]", answer or ""))):
            ref = available.get(cid)
            allowed = None
            if ref is not None:
                if scope.get("edition_ids"):
                    allowed = (ref["document_id"], ref["document_version"]) in set(zip(scope["spec_ids"], scope["edition_ids"]))
                elif scope.get("spec_ids"):
                    allowed = ref["document_id"] in scope["spec_ids"]
            citations.append({"citation_id": cid, "evidence_id": cid,
                              "parse_valid": None if context is None else ref is not None,
                              "scope_valid": allowed})
        observation = {
            "schema_version": OBSERVATION_VERSION, "case_id": public["case_id"],
            "actual_action": "error" if failure else action, "answer_text": answer,
            "error": failure or ({"code": getattr(response, "error_code", None) or "SYSTEM_ERROR"} if action == "error" else None),
            "initial_candidates": rounds[0]["candidates"] if rounds else None,
            "reranked_results": self._refs(selections[0]["output"], "S1") if selections else None,
            "final_decision_evidence": final_refs, "generator_invoked": bool(generators) if "generator" in originals else None,
            "generator_context": context, "citations": citations,
            "retrieval_rounds": rounds or None,
            "actual_scope": {"business_ids": bound_scope} if bound_scope is not None else None,
            "measurements": {"latency_ms": elapsed, "model_calls": measurements.get("model_calls"),
                             "input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"]},
            "extensions": {"request_id": request_id, "index_snapshot": getattr(state, "index_version_id", None),
                           "raw_events": events, "raw_final_evidence": final_raw,
                           "trace": plain(getattr(state, "trace", None)),
                           "raw_request_metrics": measurements,
                           "provider_usage": usage,
                           "usage_note": "full totals require all SDK attempts and observed response usage; legacy totals are not inferred",
                           "generator_calls": [{"input": e["arguments"], "input_sha256": digest(e["arguments"]),
                                                "output": e["output"], "completed": e["completed"]} for e in generators]},
        }
        validate_observation(observation)
        return observation
