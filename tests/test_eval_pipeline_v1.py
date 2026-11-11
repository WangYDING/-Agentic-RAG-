import json
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval.adapter_v1 import WorkflowAdapter
from eval.contract_v1 import make_rag_input, validate_bundle
from eval.fingerprints_v1 import sha256, verify_artifacts, source_snapshot, verify_source
from eval.offline_workflow_v1 import (fixture_workflow, convert_seen_examples, SOURCE, DOC, EDITION)
from eval.pipeline_v1 import ReplayAdapter, run_pipeline, verify_run
from eval.scoring_v1 import aggregate, case_quality, pending_review, score


@pytest.fixture(autouse=True)
def no_network_or_model(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("offline tests cannot open sockets or build model clients")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    import openai
    monkeypatch.setattr(openai, "OpenAI", denied)


def synthetic():
    return json.loads(Path("eval/examples/synthetic_contract_v1.json").read_text(encoding="utf-8"))


def test_adapter_preserves_real_workflow_behavior_and_records_generator():
    case = convert_seen_examples("eval/datasets/dev_v0.jsonl", ["SEM-001"])[0]
    baseline = fixture_workflow().run(case["question"])
    workflow = fixture_workflow()
    originals = (workflow.retriever, workflow.reranker, workflow.generator)
    obs = WorkflowAdapter(workflow, identities={SOURCE: (DOC, EDITION)})(make_rag_input(case))
    assert obs["answer_text"] == baseline.answer
    assert obs["actual_action"] == baseline.state.final_action
    assert (workflow.retriever, workflow.reranker, workflow.generator) == originals
    assert obs["generator_context"][0]["page"] == 32
    assert obs["extensions"]["generator_calls"][0]["input"]["evidences"][0]["text"] in obs["answer_text"]
    assert obs["extensions"]["generator_calls"][0]["input_sha256"] == canonical_hash_adapter(obs)
    assert obs["citations"][0]["scope_valid"] is True
    assert obs["measurements"]["input_tokens"] is None
    assert obs["actual_scope"] is None  # unscoped fake retriever never bound an actual scope
    retrieve = next(e for e in obs["extensions"]["raw_events"] if e["method"] == "retrieve")
    rerank = next(e for e in obs["extensions"]["raw_events"] if e["method"] == "rerank")
    assert retrieve["arguments"]["top_k"] == workflow.retrieval_top_k
    assert rerank["arguments"]["top_n"] == workflow.evidence_top_n


def canonical_hash_adapter(obs):
    from eval.adapter_v1 import digest
    return digest(obs["extensions"]["generator_calls"][0]["input"])


def test_scope_private_fields_rejected_before_call():
    called = []
    public = {"schema_version": "rag-eval.rag-input.v1", "case_id": "x", "question": "q",
              "query_scope": {"reference_answer": "secret"}}
    with pytest.raises(ValueError, match="scope"):
        WorkflowAdapter(SimpleNamespace(run=lambda *a, **kw: called.append(kw)))(public)
    assert not called


def test_adapter_only_passes_question_and_typed_scope_and_restores_after_error():
    seen = []
    def run(question, *, scope):
        seen.append((question, scope))
        raise RuntimeError("simulated failure")
    case = convert_seen_examples("eval/datasets/dev_v0.jsonl", ["SEM-001"])[0]
    obs = WorkflowAdapter(SimpleNamespace(run=run))(make_rag_input(case))
    assert seen[0][0] == case["question"]
    assert seen[0][1].versions[0].spec_id == DOC
    assert obs["actual_action"] == "error"
    assert obs["error"]["code"] == "ADAPTER_SYSTEM_EXCEPTION"


def test_partial_review_never_becomes_full_rate():
    metric = aggregate({"a": True, "b": None})
    assert metric["rate"] is None
    assert metric["observed_rate"] == 1
    assert metric["confirmed_lower_bound"] == .5
    assert aggregate({})["rate"] is None
    assert aggregate({"a": None})["observed_rate"] is None


def test_behavior_matrix_errors_and_denominators():
    data = synthetic()
    obs = {o["case_id"]: o for o in data["observations"]}
    reviews = {r["case_id"]: r for r in data["reviews"]}
    scored = score(data["test_cases"], obs, reviews)
    assert scored["metrics"]["service_error"]["rate"] == 1/7
    assert scored["metrics"]["false_refuse"]["rate"] == 0
    assert scored["metrics"]["complete_correct_answer"]["rate"] is None
    assert scored["confusion_matrix"]["answer"]["error"] == 1
    assert scored["performance"]["all"]["latency_ms"]["p95"] == 1000
    assert scored["performance"]["all"]["input_tokens"]["observed_count"] == 1


def test_equivalent_and_composite_recall_and_missing():
    data = synthetic()
    ids = {"SYN-EQUIVALENT", "SYN-COMPOSITE"}
    cases = [c for c in data["test_cases"] if c["case_id"] in ids]
    obs = {o["case_id"]: o for o in data["observations"] if o["case_id"] in ids}
    reviews = {c["case_id"]: pending_review(c) for c in cases}
    metrics = score(cases, obs, reviews)["metrics"]
    assert metrics["initial_candidates.recall@1"]["rate"] == .25
    assert metrics["initial_candidates.recall@3"]["rate"] == .75
    assert metrics["initial_candidates.mrr@10"]["rate"] == 1
    obs["SYN-EQUIVALENT"]["initial_candidates"] = None
    metrics = score(cases, obs, reviews)["metrics"]
    assert metrics["initial_candidates.recall@3"]["rate"] is None


def test_quality_requires_exhaustive_claim_review_and_numeric_conditions():
    data = synthetic()
    case, obs, review = data["test_cases"][0], data["observations"][0], data["reviews"][0]
    review["answer_review"] = dict.fromkeys(("claims_exhaustive", "no_contradictions", "no_material_outside_conclusions", "citations_support_claims"), True)
    assert case_quality(case, obs, review)["complete_correct_answer"] is None
    review["fact_reviews"][0]["numeric_conditions_correct"] = True
    assert case_quality(case, obs, review)["complete_correct_answer"] is True
    review["claim_reviews"][0]["support"] = "contradicted"
    assert case_quality(case, obs, review)["complete_correct_answer"] is False
    review["claim_reviews"] = []
    assert case_quality(case, obs, review)["evidence_support"] == 0
    assert case_quality(case, obs, review)["complete_correct_answer"] is False


def test_pipeline_replay_and_tamper_detection(tmp_path):
    source = Path("eval/examples/synthetic_contract_v1.json")
    data = synthetic()
    out = tmp_path / "run"
    bundle = run_pipeline(source, ReplayAdapter(data["observations"]), out, reviews=data["reviews"])
    validate_bundle(bundle)
    assert verify_run(out)["report"]["conclusion"] == "not_applicable"
    with pytest.raises(FileExistsError):
        run_pipeline(source, ReplayAdapter(data["observations"]), out)
    path = out / "observations.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_run(out)


def test_report_recomputation_rejects_forged_success(tmp_path):
    source = Path("eval/examples/synthetic_contract_v1.json")
    data = synthetic()
    bundle = run_pipeline(source, ReplayAdapter(data["observations"]), tmp_path / "run")
    bundle["report"]["case_quality"]["SYN-ANSWER"]["task_success"] = True
    with pytest.raises(ValueError, match="does not match"):
        validate_bundle(bundle)


def test_seen_old_questions_end_to_end_actual_workflow_with_fakes(tmp_path):
    converted = tmp_path / "seen.json"
    cases = convert_seen_examples("eval/datasets/dev_v0.jsonl", ["SEM-001", "SEM-002"])
    converted.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    adapter = WorkflowAdapter(fixture_workflow(), identities={SOURCE: (DOC, EDITION)})
    bundle = run_pipeline(converted, adapter, tmp_path / "run", execution_mode="offline_injected_workflow")
    assert len(bundle["observations"]) == 2
    assert all(o["actual_action"] == "answer" for o in bundle["observations"])
    assert bundle["report"]["metrics"]["complete_correct_answer"]["rate"] is None
    assert bundle["report"]["metrics"]["initial_candidates.recall@1"]["rate"] == 1
    assert sha256(converted) == bundle["run"]["artifacts"]["dataset_sha256"]


def test_artifact_paths_cannot_escape_run(tmp_path):
    with pytest.raises(ValueError, match="escapes"):
        verify_artifacts(tmp_path, {"schema_version": "rag-eval.artifacts.v1", "hash_mode": "sha256-raw-bytes", "files": {"../outside": "x"}})


def test_independent_datasets_blocked_before_adapter(tmp_path):
    case = synthetic()["test_cases"][0]
    case["dataset_role"] = "independent"
    data = tmp_path / "independent.json"
    data.write_text(json.dumps([case]), encoding="utf-8")
    with pytest.raises(ValueError, match="does not run independent"):
        run_pipeline(data, lambda _: pytest.fail("must not be called"), tmp_path / "run")


def test_sources_detect_changes_and_added_files(tmp_path):
    (tmp_path / "src").mkdir()
    code = tmp_path / "src/model.py"
    code.write_text("value = 1\n", encoding="utf-8")
    snap = source_snapshot(tmp_path, ("src",))
    verify_source(snap)
    code.write_text("value = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source hash mismatch"):
        verify_source(snap)
    code.write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "src/added.py").write_text("pass\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inventory changed"):
        verify_source(snap)


def test_document_changed_during_run_is_detected(tmp_path):
    document = tmp_path / "document.pdf"
    document.write_bytes(b"before")
    replay = ReplayAdapter(synthetic()["observations"])
    def mutate(public):
        document.write_bytes(b"after")
        return replay(public)
    with pytest.raises(ValueError, match="document changed during run"):
        run_pipeline(Path("eval/examples/synthetic_contract_v1.json"), mutate,
                     tmp_path / "run", documents=[document])


def test_reviewer_identity_and_human_approval_not_interchangeable():
    from eval.contract_v1 import validate_review
    data = synthetic()
    review = data["reviews"][0]
    review["human_approved"] = True
    with pytest.raises(ValueError, match="AI reviewer"):
        validate_review(review, data["test_cases"][0], data["observations"][0])


def test_generator_retry_records_each_input_without_extra_calls():
    case = convert_seen_examples("eval/datasets/dev_v0.jsonl", ["SEM-001"])[0]
    workflow = fixture_workflow()
    class Generator:
        def __init__(self):
            self.count = 0
        def generate_answer(self, query, evidences, chat_history=None, *, budget=None, scope_business_ids=()):
            self.count += 1
            return "invalid [E99]" if self.count == 1 else "valid [E1]"
    generator = Generator()
    workflow.generator = generator
    obs = WorkflowAdapter(workflow, identities={SOURCE: (DOC, EDITION)})(make_rag_input(case))
    assert obs["actual_action"] == "answer"
    assert generator.count == 2
    assert len(obs["extensions"]["generator_calls"]) == 2
    assert obs["extensions"]["generator_calls"][0]["output"] == "invalid [E99]"


def test_score_cache_capability_and_scope_clarification_preserved():
    case = convert_seen_examples("eval/datasets/dev_v0.jsonl", ["SEM-001"])[0]
    workflow = fixture_workflow()
    class Cached:
        supports_score_cache = True
        def score_candidates(self, query, results):
            return [dict(r, rerank_score=1.0) for r in results]
        def select_top(self, results, top_n=3):
            return results[:top_n]
    workflow.reranker = Cached()
    obs = WorkflowAdapter(workflow, identities={SOURCE: (DOC, EDITION)})(make_rag_input(case))
    methods = [e["method"] for e in obs["extensions"]["raw_events"]]
    assert "score_candidates" in methods and "select_top" in methods
    assert "rerank" not in methods
    assert obs["actual_action"] == "answer"
    from src.query_scope import QueryScopeClarificationRequired
    class Scoped:
        def for_scope(self, scope):
            raise QueryScopeClarificationRequired("select version")
    workflow.retriever = Scoped()
    obs = WorkflowAdapter(workflow)(make_rag_input(case))
    assert obs["actual_action"] == "clarify"
    assert obs["generator_invoked"] is False
    assert obs["actual_scope"] is None


def test_retrieval_retry_rounds_remain_distinct_even_if_results_equal():
    case = convert_seen_examples("eval/datasets/dev_v0.jsonl", ["SEM-001"])[0]
    workflow = fixture_workflow()
    class Grader:
        def __init__(self):
            self.calls = 0
        def grade(self, query, evidences, *, budget=None, scope_business_ids=()):
            self.calls += 1
            return SimpleNamespace(decision="insufficient" if self.calls == 1 else "sufficient", missing_requirements=[])
    workflow.grader = Grader()
    obs = WorkflowAdapter(workflow, identities={SOURCE: (DOC, EDITION)})(make_rag_input(case))
    assert len(obs["retrieval_rounds"]) == 2
    assert obs["retrieval_rounds"][0]["round_id"] != obs["retrieval_rounds"][1]["round_id"]
    assert all(row["reranked"] is not None for row in obs["retrieval_rounds"])
    assert obs["actual_action"] == "answer"
