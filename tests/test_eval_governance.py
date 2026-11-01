import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from eval.dataset_manifest import file_sha256, validate_manifest
from eval.provenance import capture_provenance
from eval.review import compare_reports, review_template
from eval.run_agent_test import _validate_dataset, evaluate, write_report
from eval.schema import EvalExample, load_eval_dataset
from src.config import AppConfig


def case(**updates):
    return dict(id="q1", question="question", question_type="lookup", answerable=True,
                gold_answer="answer", gold_evidence=[{"document": "spec.pdf", "page": 1}], **updates)


def test_extended_schema_round_trip_and_strict_boolean():
    example = EvalExample.from_dict(case(
        required_requirements=["maximum"], key_answer_points=["at most 5"],
        numeric_expectations=[{"value": "5", "unit": "m", "conditions": ["condition"]}],
        annotation_review={"status": "approved", "reviewer": "human", "reviewed_at": "2026-10-30"},
    ))
    assert EvalExample.from_dict(example.to_dict()) == example
    data = case()
    data["answerable"] = "false"
    with pytest.raises(ValueError, match="boolean"):
        EvalExample.from_dict(data)


def test_invalid_annotations_and_duplicate_ids(tmp_path):
    with pytest.raises(ValueError, match="reviewer"):
        EvalExample.from_dict(case(annotation_review={"status": "approved"}))
    with pytest.raises(ValueError, match="reviewer"):
        EvalExample.from_dict(case(annotation_review={"status": "source_verified"}))
    with pytest.raises(ValueError, match="required_requirements"):
        EvalExample.from_dict(case(required_requirements="text"))
    path = tmp_path / "data.jsonl"
    path.write_text((json.dumps(case()) + "\n") * 2)
    with pytest.raises(ValueError, match="Duplicate"):
        load_eval_dataset(path)


def manifest_fixture(tmp_path):
    data = tmp_path / "data.jsonl"
    data.write_text(json.dumps(case()) + "\n")
    manifest = dict(dataset_id="new", version="1", role="independent", status="draft",
                    data_file=data.name, sha256=file_sha256(data), count=1,
                    type_distribution={"lookup": 1})
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path, manifest, data


def test_manifest_hash_and_freeze_gate(tmp_path):
    path, manifest, data = manifest_fixture(tmp_path)
    assert len(validate_manifest(path)[1]) == 1
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps({"gate_id": "g1", "dataset_id": "new",
        "declared_before_independent_run": True}))
    manifest.update(status="frozen", frozen_at="2026-10-30",
        acceptance_criteria={"gate_id": "g1", "path": gate.name,
            "sha256": file_sha256(gate)}, used_for_tuning=False)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="requirements"):
        validate_manifest(path)
    data.write_text(json.dumps(case(required_requirements=["one"], key_answer_points=["answer"],
        annotation_review={"status": "approved", "reviewer": "human", "reviewed_at": "2026-10-30"})) + "\n")
    manifest["sha256"] = file_sha256(data)
    path.write_text(json.dumps(manifest))
    validate_manifest(path)
    manifest["used_for_tuning"] = True
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="tuning"):
        validate_manifest(path)
    manifest["used_for_tuning"] = False
    gate.write_text("{}")
    with pytest.raises(ValueError, match="gate SHA-256"):
        validate_manifest(path)
    data.write_text("tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        validate_manifest(path)


def test_historical_manifests_load_without_rewriting_legacy_data():
    for path in Path("eval/datasets").glob("*.manifest.json"):
        manifest, examples = validate_manifest(path)
        assert len(examples) == manifest["count"]


def test_provenance_excludes_secrets_and_fingerprints_config(tmp_path):
    for name in ("uv.lock", "dataset", "pdf"):
        (tmp_path / name).write_text(name)
    config = AppConfig(api_key="secret-token", api_base_url="https://user:password@example.com")
    args = dict(root=tmp_path, dataset_path=tmp_path / "dataset", pdf_path=tmp_path / "pdf")
    first = capture_provenance(config, **args)
    assert "secret-token" not in json.dumps(first)
    assert "password" not in json.dumps(first)
    assert first["model_revisions"]["generation"] is None
    second = capture_provenance(replace(config, retrieval_top_k=20), **args)
    assert first["configuration_sha256"] != second["configuration_sha256"]
    assert first["release_dependencies"]["real_deployment_latency_baseline"] == "pending"


def test_generic_evaluator_records_service_errors_without_counting_as_refusal(tmp_path):
    path, manifest, data = manifest_fixture(tmp_path)
    manifest['role'] = 'development'
    path.write_text(json.dumps(manifest))
    pdf = tmp_path / 'spec.pdf'
    pdf.write_text('fake pdf; injected workflow does not parse it')
    workflow = SimpleNamespace(index_version_id='snapshot', reranker=object(), grader=SimpleNamespace(model='fake'))
    def run(query):
        return SimpleNamespace(
            request_id='request', error_code='TIMEOUT', answer='service failed',
            state=SimpleNamespace(trace=[], evidences=[], final_action='error', retry_count=0,
                rewritten_query=None, citation_validation=None),
        )
    workflow.run = run
    report = evaluate(data, pdf, tmp_path, manifest_path=path,
        config=AppConfig(pdf_path=str(pdf), index_dir=str(tmp_path)), workflow=workflow)
    assert report['agent_decision']['final_error'] == 1
    assert report['agent_decision']['false_refusal'] == 0
    assert report['agent_decision']['first_insufficient_retry'] == 0
    assert report['cases'][0]['first_grade'] is None
    assert report['provenance']['index_version_id'] == 'snapshot'
    assert review_template(report)['cases'][0]['review']['status'] == 'pending'
    assert report['release_decision'].startswith('blocked')
    write_report(report, tmp_path/'result.json', tmp_path/'result.md')
    with pytest.raises(FileExistsError):
        write_report(report, tmp_path/'result.json', tmp_path/'result.md')


def test_draft_independent_dataset_cannot_run(tmp_path):
    path, manifest, data = manifest_fixture(tmp_path)
    with pytest.raises(ValueError, match='frozen'):
        evaluate(data, tmp_path/'missing.pdf', tmp_path, manifest_path=path)


def test_generic_validation_accepts_non_twenty_sizes():
    _validate_dataset([EvalExample.from_dict(case())])


def test_baseline_comparison_refuses_different_or_unknown_datasets():
    old = dict(report_schema_version=2, evidence_top_n=3,
        provenance=dict(dataset_sha256='a', pdf_sha256='pdf'),
        agent_decision=dict(final_error=1))
    new = dict(old, agent_decision=dict(final_error=0))
    assert compare_reports(old, new)['deltas']['agent_decision']['final_error'] == -1
    new['provenance'] = dict(dataset_sha256='b', pdf_sha256='pdf')
    assert not compare_reports(old, new)['comparable']
    assert not compare_reports({}, {})['comparable']

def test_real_workflow_injected_components_produces_rank_metrics_and_usage(tmp_path):
    from src.agent_workflow import AgentWorkflow
    path, manifest, data = manifest_fixture(tmp_path)
    manifest['role'] = 'development'
    path.write_text(json.dumps(manifest))
    pdf = tmp_path / 'spec.pdf'
    pdf.write_text('fake document for offline pipeline')
    result = dict(text='answer', source='spec.pdf', page_start=1, page_end=1, chunk_id=1)
    workflow = AgentWorkflow(
        SimpleNamespace(retrieve=lambda query, top_k: [result]),
        SimpleNamespace(rerank=lambda query, results, top_n: results[:top_n]),
        SimpleNamespace(model='fake', grade=lambda question, evidences: SimpleNamespace(
            decision='sufficient', missing_requirements=[])),
        SimpleNamespace(generate_answer=lambda query, evidences, chat_history: 'answer [E1]'),
        evidence_top_n=2, index_version_id='fake-index',
    )
    config = AppConfig(pdf_path=str(pdf), index_dir=str(tmp_path), evidence_top_n=2)
    report = evaluate(data,pdf,tmp_path,manifest_path=path,config=config,workflow=workflow)
    assert report['agent_decision']['final_answer'] == 1
    assert report['initial_rank_metrics']['mrr@10'] == 1
    assert report['retrieval_evidence']['final_recall_at_n'] == 1
    assert report['cases'][0]['measurements']['deployment_baseline'] is False
    assert report['cases'][0]['measurements']['model_calls'] == 0
    assert report['input_integrity_at_finish']['dataset_unchanged']
    write_report(report,tmp_path/'report.json',tmp_path/'report.md')
    assert 'Recall@2' in (tmp_path/'report.md').read_text()


def test_manifest_required_before_any_model_calls(tmp_path):
    path, manifest, data=manifest_fixture(tmp_path)
    with pytest.raises(ValueError,match='required'):
        evaluate(data,tmp_path/'missing',tmp_path)

def test_new_split_evidence_disjoint_from_historical_and_each_other():
    root=Path('eval/datasets')
    def evidence_ids(rows):
        return {
            value
            for row in rows
            for ev in row.gold_evidence
            for value in (ev.article, ev.table)
            if value
        }
    old=set()
    for name in ('dev_v0','refusal_dev_v0','test_v1'):
        old |= evidence_ids(load_eval_dataset(root/(name+'.jsonl')))
    old |= {ev.get('article_id') for line in (root/'sufficiency_dev_v0.jsonl').read_text(encoding='utf-8').splitlines()
        for ev in json.loads(line)['evidence'] if ev.get('article_id')}
    dev=load_eval_dataset(root/'regression_v1_draft.jsonl')
    independent=load_eval_dataset(root/'independent_v2_draft.jsonl')
    assert len(dev)==30 and len(independent)==20
    assert not evidence_ids(dev)&evidence_ids(independent)
    assert not (evidence_ids(dev)|evidence_ids(independent))&old
    assert all(row.annotation_review.status=='approved' for row in dev+independent)
    assert all(row.annotation_review.reviewer and row.annotation_review.reviewed_at
               for row in dev+independent)


def test_pdf_content_review_is_complete_and_does_not_freeze_independent_set():
    report = json.loads(
        Path('eval/reviews/candidate_content_review_2026-11-01.json').read_text(
            encoding='utf-8'
        )
    )
    assert report['case_count'] == 50
    assert report['approved'] == 50
    assert report['rejected'] == 0
    assert report['corrected_case_count'] == 6
    assert report['reviewer_type'] == 'AI'
    assert report['licensed_domain_expert'] is False
    assert report['independent_dataset_executed'] is False
    assert report['independent_dataset_frozen'] is False
    assert all(case['verdict'] == 'approved' for case in report['cases'])


def test_source_verification_does_not_satisfy_independent_freeze_gate(tmp_path):
    path, manifest, data = manifest_fixture(tmp_path)
    data.write_text(json.dumps(case(
        required_requirements=["one"],
        key_answer_points=["answer"],
        annotation_review={
            "status": "source_verified",
            "reviewer": "source checker",
            "reviewed_at": "2026-10-31",
        },
    )) + "\n")
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps({"gate_id": "g1", "dataset_id": "new",
        "declared_before_independent_run": True}))
    manifest.update(
        status="frozen",
        frozen_at="2026-10-31",
        acceptance_criteria={"gate_id": "g1", "path": gate.name,
            "sha256": file_sha256(gate)},
        used_for_tuning=False,
        sha256=file_sha256(data),
    )
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approval"):
        validate_manifest(path)
