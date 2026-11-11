import copy
import socket
from types import SimpleNamespace

import pytest

from eval.decision_v1 import evaluate_decision, sign_assessment, verify_assessment
from eval.fingerprints_v1 import canonical_hash, sha256, write_json
from eval.freeze_v1 import bind, precheck, read_json
from eval.pipeline_v1 import run_pipeline, verify_run
from eval.rehearsal_v1 import (prepare_fixture, execute_fixture, fixture_actor, packet_for,
                              completed_fixture_review)
from eval.review_workflow_v1 import import_reviews, initial_state, load_revision, apply_packet
from eval.usage_v1 import usage_from_response, summarize_usage, usage_report, observe_provider


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def deny(*a, **kw):
        raise AssertionError("real network/model client prohibited")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    import openai
    monkeypatch.setattr(openai, "OpenAI", deny)
    monkeypatch.setattr(openai, "AsyncOpenAI", deny)


@pytest.mark.parametrize("response,expected", [
    (SimpleNamespace(), (None, None)), (SimpleNamespace(usage=None), (None, None)),
    ({"usage": {}}, (None, None)), ({"usage": {"prompt_tokens": 0, "completion_tokens": 0}}, (0, 0)),
    ({"usage": {"input_tokens": 4}}, (4, None)),
    ({"usage": {"prompt_tokens": False, "completion_tokens": -1}}, (None, None)),
    ({"usage": {"prompt_tokens": "5", "completion_tokens": 1.2}}, (None, None)),
])
def test_provider_missing_usage_is_not_zero(response, expected):
    out = usage_from_response(response)
    assert (out["input_tokens"], out["output_tokens"]) == expected


def test_usage_retry_missing_cost_and_observation_ratios():
    events = [{"input_tokens": None, "output_tokens": None}, {"input_tokens": 10, "output_tokens": 2}]
    pricing = {"input_per_million": 1, "output_per_million": 2, "currency": "USD",
               "source": "synthetic fixture price", "effective_at": "2026-01-01"}
    result = summarize_usage(events, 2, pricing)
    assert result["input_tokens"] is None and result["estimated_cost"] is None
    assert result["input_tokens_observed_sum"] == 10
    assert result["input_tokens_observation_ratio"] == .5
    full = summarize_usage(events[1:], 1, pricing)
    assert full["input_tokens"] == 10 and full["estimated_cost"] == 14/1_000_000
    assert summarize_usage(events[1:], 2)["input_tokens"] is None
    assert summarize_usage([], 0)["input_tokens"] is None
    assert summarize_usage([{"input_tokens": 0, "output_tokens": 0}], 1, pricing)["estimated_cost"] == 0
    with pytest.raises(ValueError, match="pricing"):
        summarize_usage(events, 2, {"input_per_million": 1})


def test_provider_wrapper_preserves_response_arguments_and_restores_on_exception():
    calls = []
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=8, completion_tokens=0))
    def create(*args, **kwargs):
        calls.append((args, kwargs))
        return response
    completion = SimpleNamespace(create=create)
    chat = SimpleNamespace(completions=completion)
    workflow = SimpleNamespace(generator=SimpleNamespace(client=SimpleNamespace(chat=chat)))
    with observe_provider(workflow) as events:
        assert chat.completions.create(model="fake", timeout=3) is response
    assert calls == [((), {"model": "fake", "timeout": 3})]
    assert chat.completions is completion and events[0]["input_tokens"] == 8
    with pytest.raises(RuntimeError):
        with observe_provider(workflow):
            raise RuntimeError("outer failure")
    assert chat.completions is completion


def test_request_usage_totals_do_not_fill_missing_with_zero():
    observations = [{"case_id": "a", "measurements": {"input_tokens": 2, "output_tokens": 0}},
                    {"case_id": "b", "measurements": {"input_tokens": None, "output_tokens": None}}]
    report = usage_report(observations)
    assert report["input_tokens"]["observed_sum"] == 2
    assert report["input_tokens"]["full_sum"] is None
    assert report["input_tokens"]["observation_ratio"] == .5
    assert report["estimated_cost"]["observed_sum"] is None


@pytest.fixture
def frozen(tmp_path):
    return prepare_fixture(tmp_path / "fixture")


@pytest.fixture
def executed(frozen):
    run = frozen["directory"] / "run"
    bundle = execute_fixture(frozen, run)
    return frozen, run, bundle


def packet_with_reviews(run, bundle, *, kind="human", prior=None):
    packet = packet_for(bundle, sha256(run / "bundle.json"), kind=kind, prior=prior)
    prior_rows = {r["case_id"]: r for r in (prior or initial_state(bundle, sha256(run / "bundle.json")))["reviews"]}
    for case, obs in zip(bundle["test_cases"], bundle["observations"]):
        review = completed_fixture_review(case, obs, packet["actor"])
        review["reviewer"]["rubric_version"] = bundle["run"]["evaluation_snapshot"]["rubric_version"]
        packet["changes"].append({"case_id": case["case_id"], "previous_review_sha256": canonical_hash(prior_rows[case["case_id"]]),
                                  "review": review, "reason": "synthetic review test only"})
    return packet


def test_freeze_precheck_and_end_to_end_unknown_review(executed):
    fixture, run, bundle = executed
    assert precheck(fixture["freeze"], allow_claimed_attempt=True)["eligible"] is True
    assert precheck(fixture["freeze"])["eligible"] is False
    assert verify_run(run)["run"]["admission"]["after"]["eligible"] is True
    state = initial_state(bundle, sha256(run / "bundle.json"))
    result = evaluate_decision(bundle, state, fixture["policy"], fixture["freeze"])
    assert result["conclusion"] == "inconclusive"
    assert any(r["code"] == "UNREVIEWED_OR_AI_ONLY" for r in result["reasons"])


@pytest.mark.parametrize("kind", ["missing", "hash", "role", "review", "facts", "index", "source", "late", "revision", "config", "environment"])
def test_freeze_blocks_invalid_bindings_and_annotations(frozen, kind):
    freeze = copy.deepcopy(frozen["freeze"])
    def replace(name, value):
        path = frozen["directory"] / ("changed-" + name + ".json")
        write_json(path, value)
        freeze["bindings"][name] = bind(path)
    if kind == "missing":
        del freeze["bindings"]["rules"]
    elif kind == "hash":
        freeze["bindings"]["rules"]["sha256"] = "0"*64
    elif kind in {"role", "review", "facts"}:
        descriptor = read_json(frozen["bindings"]["dataset_descriptor"])
        if kind == "role":
            descriptor["role"] = "independent"
        elif kind == "review":
            descriptor["case_approvals"][0]["status"] = "pending"
        else:
            descriptor["case_approvals"][0]["schemes_sha256"] = "0"*64
        replace("dataset_descriptor", descriptor)
    elif kind == "index":
        (frozen["directory"] / "knowledge/documents/fixture/index.faiss").write_bytes(b"changed")
    elif kind == "source":
        source = read_json(frozen["bindings"]["rag_source"])
        source["source_hashes"]["src/agent_workflow.py"] = "0"*64
        replace("rag_source", source)
    elif kind == "late":
        policy = copy.deepcopy(frozen["policy"])
        policy["declared_at"] = "2099-01-01T00:00:00Z"
        replace("thresholds", policy)
    elif kind in {"revision", "config"}:
        cfg = read_json(frozen["bindings"]["configuration"])
        if kind == "revision":
            cfg["models"]["embedding"]["revision_status"] = "unknown"
        else:
            cfg["public_config"]["generation_model"] = "other"
        replace("configuration", cfg)
    else:
        env = read_json(frozen["bindings"]["environment"])
        env["lock_sha256"] = "0"*64
        replace("environment", env)
    assert precheck(freeze)["eligible"] is False


def test_invalid_precheck_blocks_before_adapter(frozen):
    freeze = copy.deepcopy(frozen["freeze"])
    del freeze["bindings"]["rules"]
    bad = frozen["directory"] / "bad-freeze.json"
    write_json(bad, freeze)
    called = []
    with pytest.raises(ValueError, match="admission blocked"):
        run_pipeline(frozen["dataset"], lambda _: called.append(1), frozen["directory"] / "bad-run",
                     freeze_path=bad, config=frozen["config"], model_ids=frozen["models"])
    assert not called


def test_formal_role_dirty_environment_and_ai_approval_rejected(frozen):
    formal = copy.deepcopy(frozen["freeze"])
    formal["purpose"] = "independent"
    checked = precheck(formal)
    codes = {r["code"] for r in checked["reasons"]}
    assert {"FREEZE_APPROVAL", "DIRTY_SOURCE", "ENVIRONMENT_UNVERIFIED", "DATASET_INVALID"} <= codes


def test_review_import_pass_sign_and_no_overwrite_are_simulation_only(executed):
    fixture, run, bundle = executed
    original = sha256(run / "bundle.json")
    packet = packet_with_reviews(run, bundle)
    path = fixture["directory"] / "packet.json"
    write_json(path, packet)
    revision = fixture["directory"] / "revision"
    state = import_reviews(run, path, revision)
    assert load_revision(revision)[1] == state
    decision_path = fixture["directory"] / "assessment"
    decision = sign_assessment(run, decision_path, signer=fixture_actor("human"), revision=revision)
    assert decision["conclusion"] == "pass" and decision["purpose"] == "rehearsal"
    assert "REHEARSAL ONLY" in decision["notice"]
    assert verify_assessment(decision_path) == decision
    assert sha256(run / "bundle.json") == original
    with pytest.raises(FileExistsError):
        import_reviews(run, path, revision)
    with pytest.raises(FileExistsError):
        sign_assessment(run, decision_path, signer=fixture_actor("human"), revision=revision)


@pytest.mark.parametrize("kind", ["stale", "unknown_fact", "unknown_evidence", "ai_approval", "pending_approval", "wrong_actor", "unknown_field", "wrong_rules"])
def test_review_import_validates_fields_and_never_alters_original(executed, kind):
    fixture, run, bundle = executed
    original = sha256(run / "bundle.json")
    packet = packet_with_reviews(run, bundle)
    change = packet["changes"][0]
    if kind == "stale":
        change["previous_review_sha256"] = "0"*64
    elif kind == "unknown_fact":
        change["review"]["fact_reviews"][0]["fact_id"] = "unknown"
    elif kind == "unknown_evidence":
        change["review"]["claim_reviews"][0]["evidence_ids"] = ["unknown"]
    elif kind == "ai_approval":
        packet["actor"]["type"] = "ai"
        for c in packet["changes"]:
            c["review"]["reviewer"]["reviewer_type"] = "ai"
    elif kind == "pending_approval":
        change["review"]["fact_reviews"][0]["correct"] = None
    elif kind == "wrong_actor":
        change["review"]["reviewer"]["identity"] = "other"
    elif kind == "wrong_rules":
        change["review"]["reviewer"]["rubric_version"] = "other"
    else:
        change["review"]["unrecognized_field"] = True
    path = fixture["directory"] / "packet-invalid.json"
    write_json(path, packet)
    with pytest.raises(ValueError):
        import_reviews(run, path, fixture["directory"] / "invalid-revision")
    assert sha256(run / "bundle.json") == original


def test_dispute_adjudication_and_parent_history_are_replayable(executed):
    fixture, run, bundle = executed
    packet = packet_with_reviews(run, bundle)
    bh = sha256(run / "bundle.json")
    prior = initial_state(bundle, bh)
    state = apply_packet(bundle, prior, packet)
    open_packet = packet_for(bundle, bh, prior=state)
    row = state["reviews"][0]
    open_packet["disputes"] = [{"dispute_id": "D1", "case_id": row["case_id"], "field": "/fact_reviews/0/correct",
                                "reason": "synthetic disagreement", "review_sha256": canonical_hash(row)}]
    disputed = apply_packet(bundle, state, open_packet)
    result = evaluate_decision(bundle, disputed, fixture["policy"], fixture["freeze"])
    assert result["conclusion"] == "inconclusive" and any(r["code"] == "OPEN_DISPUTE" for r in result["reasons"])
    resolve = packet_for(bundle, bh, kind="human", prior=disputed)
    resolve["adjudications"] = [{"dispute_id": "D1", "decision": "uphold", "reason": "synthetic adjudication", "review_sha256": canonical_hash(row)}]
    resolved = apply_packet(bundle, disputed, resolve)
    assert resolved["disputes"][0]["resolution"]["decision"] == "uphold"
    assert state["disputes"] == [] and disputed["disputes"][0]["resolution"] is None
    assert evaluate_decision(bundle, resolved, fixture["policy"], fixture["freeze"])["conclusion"] == "pass"


def test_ai_cannot_adjudicate_and_unknown_dispute_field_rejected(executed):
    fixture, run, bundle = executed
    bh = sha256(run / "bundle.json")
    prior = initial_state(bundle, bh)
    packet = packet_for(bundle, bh)
    packet["disputes"] = [{"dispute_id": "D", "case_id": prior["reviews"][0]["case_id"], "field": "/missing", "reason": "x",
                           "review_sha256": canonical_hash(prior["reviews"][0])}]
    with pytest.raises(ValueError, match="field does not exist"):
        apply_packet(bundle, prior, packet)
    packet["disputes"][0]["field"] = "/fact_reviews/0/correct"
    state = apply_packet(bundle, prior, packet)
    resolution = packet_for(bundle, bh, prior=state)
    resolution["adjudications"] = [{"dispute_id": "D", "decision": "uphold", "reason": "x", "review_sha256": canonical_hash(state["reviews"][0])}]
    with pytest.raises(ValueError, match="human actor"):
        apply_packet(bundle, state, resolution)


def test_decision_missing_observations_service_error_and_late_policy(executed):
    fixture, run, original = executed
    bundle = copy.deepcopy(original)
    bh = sha256(run / "bundle.json")
    state = initial_state(bundle, bh)
    bundle["observations"][0]["actual_action"] = "error"
    bundle["observations"][0]["measurements"]["latency_ms"] = None
    result = evaluate_decision(bundle, state, fixture["policy"], fixture["freeze"])
    assert result["conclusion"] == "fail"
    assert {"SERVICE_ERROR", "MISSING_OBSERVATION"} <= {r["code"] for r in result["reasons"]}
    policy = copy.deepcopy(fixture["policy"])
    policy["on_service_error"] = "inconclusive"
    result = evaluate_decision(bundle, state, policy, fixture["freeze"])
    assert result["conclusion"] == "inconclusive"
    policy["declared_at"] = "2099-01-01T00:00:00Z"
    assert any(r["code"] == "LATE_FREEZE_OR_POLICY" for r in evaluate_decision(original, state, policy, fixture["freeze"])["reasons"])


def test_runtime_snapshot_binding_mismatch_prevents_execution(frozen):
    frozen["workflow"].index_version_id = "wrong"
    with pytest.raises(ValueError, match="index snapshot"):
        execute_fixture(frozen, frozen["directory"] / "run")


def test_review_and_assessment_tamper_detection(executed):
    fixture, run, bundle = executed
    packet = packet_with_reviews(run, bundle)
    packet_path = fixture["directory"] / "packet.json"
    write_json(packet_path, packet)
    revision = fixture["directory"] / "revision"
    import_reviews(run, packet_path, revision)
    output = fixture["directory"] / "assessment"
    sign_assessment(run, output, signer=fixture_actor("human"), revision=revision)
    (revision / "packet.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_revision(revision)
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_assessment(output)


def test_formal_precheck_positive_with_only_temporary_mock_approvals(frozen, monkeypatch):
    # This tests gate logic, NOT an independently authored dataset or real human approval.
    import eval.fingerprints_v1 as fingerprints
    actual_git = fingerprints.git
    def clean_status(root, *args):
        return "" if args and args[0] == "status" else actual_git(root, *args)
    monkeypatch.setattr(fingerprints, "git", clean_status)
    formal = copy.deepcopy(frozen["freeze"])
    formal["purpose"] = "independent"
    formal["approved_by"]["type"] = "human"
    configuration = read_json(frozen["bindings"]["configuration"])
    configuration["api_endpoint_sha256"] = "a"*64
    configuration["public_config"].update(embedding_revision=None, request_timeout_seconds=30.0, max_network_retries=1)
    config_path = frozen["directory"] / "mock-configuration.json"
    write_json(config_path, configuration)
    formal["bindings"]["configuration"] = bind(config_path)
    for name in ("rag_source", "evaluation_source", "dataset_descriptor", "environment"):
        payload = read_json(frozen["bindings"][name])
        if name.endswith("source"):
            payload["git_dirty"] = False
            payload["git_status"] = ""
        elif name == "dataset_descriptor":
            payload["role"], payload["used_for_tuning"] = "independent", False
            for a in payload["case_approvals"]:
                a["reviewer"]["type"] = "human"
        else:
            payload["locked_sync_verified"] = True
            payload["sync_record"] = {"exit_code": 0, "command": "SYNTHETIC TEST RECORD: uv sync --locked", "lock_sha256": payload["lock_sha256"]}
        path = frozen["directory"] / ("mock-formal-" + name + ".json")
        write_json(path, payload)
        formal["bindings"][name] = bind(path)
    cases = copy.deepcopy(frozen["cases"])
    for c in cases:
        c["dataset_role"] = "independent"
    dataset = frozen["directory"] / "temporary-mock-role-cases.json"
    write_json(dataset, cases)
    descriptor_path = frozen["directory"] / "mock-formal-dataset_descriptor.json"
    descriptor = read_json(descriptor_path)
    descriptor["sha256"] = sha256(dataset)
    # Test fixture only: do not persist a real independent-role copy in project datasets.
    updated = frozen["directory"] / "mock-descriptor-rebound.json"
    write_json(updated, descriptor)
    formal["bindings"]["dataset_descriptor"] = bind(updated)
    formal["bindings"]["dataset"] = bind(dataset)
    assert precheck(formal)["eligible"] is True
    path = frozen["directory"] / "mock-formal-freeze.json"
    write_json(path, formal)
    with pytest.raises(ValueError, match="not authorized"):
        run_pipeline(dataset, lambda _: pytest.fail("independent executor must not run"), frozen["directory"] / "no-formal-run",
                     freeze_path=path, config=frozen["config"], model_ids=frozen["models"], execution_mode="frozen_independent")


def test_multi_revision_dispute_chain_is_preserved_on_disk(executed):
    fixture, run, bundle = executed
    first = packet_with_reviews(run, bundle)
    p1 = fixture["directory"] / "packet-1.json"
    write_json(p1, first)
    r1 = fixture["directory"] / "revision-1"
    state1 = import_reviews(run, p1, r1)
    second = packet_for(bundle, sha256(run / "bundle.json"), prior=state1)
    row = state1["reviews"][0]
    second["disputes"] = [{"dispute_id": "D", "case_id": row["case_id"], "field": "/fact_reviews/0/correct",
                             "reason": "synthetic conflict", "review_sha256": canonical_hash(row)}]
    p2 = fixture["directory"] / "packet-2.json"
    write_json(p2, second)
    r2 = fixture["directory"] / "revision-2"
    state2 = import_reviews(run, p2, r2, parent=r1)
    third = packet_for(bundle, sha256(run / "bundle.json"), kind="human", prior=state2)
    third["adjudications"] = [{"dispute_id": "D", "decision": "uphold", "reason": "synthetic resolution", "review_sha256": canonical_hash(row)}]
    p3 = fixture["directory"] / "packet-3.json"
    write_json(p3, third)
    r3 = fixture["directory"] / "revision-3"
    state3 = import_reviews(run, p3, r3, parent=r2)
    assert load_revision(r3)[1] == state3
    assert load_revision(r1)[1]["disputes"] == []
    assert load_revision(r2)[1]["disputes"][0]["resolution"] is None


def test_ai_only_import_signs_inconclusive_and_threshold_failure_signs_fail(executed):
    fixture, run, bundle = executed
    packet = packet_with_reviews(run, bundle, kind="ai")
    path = fixture["directory"] / "ai-packet.json"
    write_json(path, packet)
    revision = fixture["directory"] / "ai-revision"
    import_reviews(run, path, revision)
    decision = sign_assessment(run, fixture["directory"] / "pending-assessment", signer=fixture_actor("human"), revision=revision)
    assert decision["conclusion"] == "inconclusive"
    with pytest.raises(ValueError, match="human actor"):
        sign_assessment(run, fixture["directory"] / "ai-cannot-sign", signer=fixture_actor("ai"), revision=revision)
    # Explicitly incorrect answer-review label exercises a hard failure despite missing human approval.
    prior = load_revision(revision)[1]
    changed = packet_with_reviews(run, bundle, kind="ai", prior=prior)
    changed["changes"][0]["review"]["answer_review"]["no_material_outside_conclusions"] = False
    cpath = fixture["directory"] / "failed-packet.json"
    write_json(cpath, changed)
    r2 = fixture["directory"] / "failed-revision"
    import_reviews(run, cpath, r2, parent=revision)
    failed = sign_assessment(run, fixture["directory"] / "failed-assessment", signer=fixture_actor("human"), revision=r2)
    assert failed["conclusion"] == "fail"
    assert any(r["code"] == "MATERIAL_OUTSIDE_CONCLUSIONS" for r in failed["reasons"])


@pytest.mark.parametrize("usage,expected", [(None, None), (SimpleNamespace(prompt_tokens=0, completion_tokens=0), 0),
                                           (SimpleNamespace(prompt_tokens=8, completion_tokens=2), 8)])
def test_adapter_integrates_provider_presence_without_changing_workflow(usage, expected):
    from eval.adapter_v1 import WorkflowAdapter
    from eval.contract_v1 import make_rag_input
    from eval.offline_workflow_v1 import fixture_workflow, convert_seen_examples, SOURCE, DOC, EDITION
    workflow = fixture_workflow()
    calls = []
    response = SimpleNamespace(usage=usage, choices=[SimpleNamespace(message=SimpleNamespace(content="fake answer [E1]"))])
    def create(**kwargs):
        calls.append(kwargs)
        return response
    completions = SimpleNamespace(create=create)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    class FakeProviderGenerator:
        def __init__(self):
            self.client = client
        def generate_answer(self, query, evidences, chat_history=None, *, budget=None, scope_business_ids=()):
            budget.consume()
            returned = self.client.chat.completions.create(model="fixture", messages=[{"content": query}])
            budget.record_usage(returned)
            return returned.choices[0].message.content
    workflow.generator = FakeProviderGenerator()
    case = convert_seen_examples("eval/datasets/dev_v0.jsonl", ["SEM-001"])[0]
    obs = WorkflowAdapter(workflow, identities={SOURCE: (DOC, EDITION)})(make_rag_input(case))
    assert obs["actual_action"] == "answer"
    assert obs["measurements"]["input_tokens"] == expected
    assert len(calls) == 1 and client.chat.completions is completions
    assert obs["extensions"]["provider_usage"]["estimated_cost"] is None
    assert obs["extensions"]["provider_usage"]["inventory_complete"] is True


def test_single_attempt_registry_prevents_reexecution_before_adapter(executed):
    fixture, run, bundle = executed
    called = []
    with pytest.raises(ValueError, match="admission blocked"):
        run_pipeline(fixture["dataset"], lambda _: called.append(True), fixture["directory"] / "second-run",
                     freeze_path=fixture["freeze_path"], config=fixture["config"], model_ids=fixture["models"], execution_mode="frozen_rehearsal")
    assert not called
    record = read_json(bundle["run"]["admission"]["attempt"]["path"])
    assert record["retain_failed_attempts"] is True and record["output"] == str(run.resolve())


def test_exported_review_template_needs_real_actor_and_frozen_rubric(executed):
    from eval.review_workflow_v1 import export_review_template
    fixture, run, bundle = executed
    path = fixture["directory"] / "human-edit-draft.json"
    packet = export_review_template(run, path)
    assert packet["changes"][0]["review"]["reviewer"]["rubric_version"] == bundle["run"]["evaluation_snapshot"]["rubric_version"]
    with pytest.raises(ValueError, match="identity"):
        import_reviews(run, path, fixture["directory"] / "cannot-import-blank-template")
    with pytest.raises(FileExistsError):
        export_review_template(run, path)


def test_formal_binding_checks_real_component_timeout_and_hidden_sdk_retries(frozen):
    from eval.adapter_v1 import WorkflowAdapter
    workflow = frozen["workflow"]
    configuration = read_json(frozen["bindings"]["configuration"])
    configuration["public_config"].update(embedding_revision=None, request_timeout_seconds=30.0, max_network_retries=1)
    workflow.retriever.embedder = SimpleNamespace(model_name="offline-embedding", model_revision=None)
    for component in (workflow.grader, workflow.generator):
        component.model = "offline-generation"
        component.call_policy = SimpleNamespace(request_timeout_seconds=30.0, max_network_retries=1)
        component.client = SimpleNamespace(max_retries=0)
    adapter = WorkflowAdapter(workflow)
    source = read_json(frozen["bindings"]["rag_source"])
    adapter.check_binding(configuration, frozen["knowledge"], source, require_provider_policy=True)
    workflow.grader.call_policy.request_timeout_seconds = 99
    with pytest.raises(ValueError, match="retry/timeout"):
        adapter.check_binding(configuration, frozen["knowledge"], source, require_provider_policy=True)
    workflow.grader.call_policy.request_timeout_seconds = 30.0
    workflow.grader.client.max_retries = 1
    with pytest.raises(ValueError, match="hidden SDK retry"):
        adapter.check_binding(configuration, frozen["knowledge"], source, require_provider_policy=True)
