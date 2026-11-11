"""Handwritten fake components for two already-seen dev questions. No model client."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from eval.adapter_v1 import WorkflowAdapter
from eval.contract_v1 import TEST_CASE_VERSION
from eval.fingerprints_v1 import write_json
from eval.pipeline_v1 import run_pipeline
from eval.schema import load_eval_dataset
from src.agent_workflow import AgentWorkflow


SOURCE = "城市轨道交通工程设计标准.pdf"
DOC = "LEGACY-FIXTURE"
EDITION = "synthetic-edition-not-verified"


class FixtureRetriever:
    def retrieve(self, query, top_k=10):
        if "上行" in query:
            text = "南向北和西向东为上行，北向南和东向西为下行；环线外环为上行、内环为下行。"
            page, article = 32, "4.3.1"
        else:
            text = "站台有效长度范围内，A型车曲线半径不应小于1500m，B型车不应小于1000m。"
            page, article = 45, "7.2.1"
        return [{"text": text, "source": SOURCE, "page_start": page, "page_end": page,
                 "article_id": article, "chunk_id": page}][:top_k]


class FixtureReranker:
    def rerank(self, query, results, top_n=3):
        return results[:top_n]


class FixtureGrader:
    def grade(self, query, evidences, *, budget=None, scope_business_ids=()):
        return SimpleNamespace(decision="sufficient", missing_requirements=[])


class FixtureGenerator:
    def generate_answer(self, query, evidences, chat_history=None, *, budget=None, scope_business_ids=()):
        return evidences[0].text + " [E1]"


def fixture_workflow():
    return AgentWorkflow(FixtureRetriever(), FixtureReranker(), FixtureGrader(), FixtureGenerator(),
                         model_ids={"generation": "offline-fixture-no-model"}, index_version_id="offline-fixture")


def convert_seen_examples(path, ids):
    """No new independent questions; legacy gold is provisional, unreviewed.

    One legacy key point becomes one provisional fact. Evidence originally listed
    flat is conservatively treated as AND, not silently declared equivalent.
    """
    examples = {e.id: e for e in load_eval_dataset(path)}
    cases = []
    for cid in ids:
        old = examples[cid]
        descriptions = old.key_answer_points or ([old.gold_answer] if old.answerable else [])
        refs = [{"evidence_id": f"legacy-gold-{i}", "document_id": DOC,
                 "document_version": EDITION, "page": ref.page,
                 "article": ref.article, "table": ref.table}
                for i, ref in enumerate(old.gold_evidence)]
        facts = [{"fact_id": f"F{i+1}", "description": text} for i, text in enumerate(descriptions)]
        cases.append({"schema_version": TEST_CASE_VERSION, "case_id": cid,
                      "dataset_role": "historical", "question": old.question,
                      "question_type": old.question_type,
                      "query_scope": {"spec_ids": [DOC], "edition_ids": [EDITION]},
                      "expected_action": "answer" if old.answerable else "refuse",
                      "reference_answer": old.gold_answer, "necessary_facts": facts,
                      "evidence_groups": [{"fact_id": f["fact_id"], "alternatives": [
                          {"scheme_id": "legacy-provisional-and", "all_of": refs}]} for f in facts],
                      "migration_notice": "Seen dev data; provisional fact decomposition and fixture edition; not approved gold or independent data."})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    original = root / "eval/datasets/dev_v0.jsonl"
    converted = args.output.parent / (args.output.name + "-seen-input.json")
    converted.parent.mkdir(parents=True, exist_ok=True)
    write_json(converted, convert_seen_examples(original, ["SEM-001", "SEM-002"]))
    bundle = run_pipeline(converted, WorkflowAdapter(fixture_workflow(), identities={SOURCE: (DOC, EDITION)}),
                          args.output, extra_inputs={"original_seen_dataset": original},
                          execution_mode="offline_injected_workflow", model_ids={"generation": "offline-fixture-no-model"},
                          config={"retrieval_top_k": 10, "evidence_top_n": 3,
                                  "max_model_calls": 6, "total_timeout_seconds": 90.0})
    print(json.dumps({"count": len(bundle["test_cases"]), "conclusion": bundle["report"]["conclusion"]}))


if __name__ == "__main__":
    main()
