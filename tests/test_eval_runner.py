import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eval.report import write_json_report, write_markdown_report
from eval.run_retrieval import evaluate_retrieval


class FakeRetriever:
    calls = []

    def __init__(self, vector_store, embedder):
        pass

    def retrieve(self, query, top_k):
        FakeRetriever.calls.append((query, top_k))
        return [
            {
                "text": "wrong",
                "source": "spec.pdf",
                "page_start": 1,
                "page_end": 1,
                "chunk_id": 1,
                "score": 0.9,
            },
            {
                "text": "gold article",
                "source": "spec.pdf",
                "page_start": 61,
                "page_end": 61,
                "article_id": "10.3.3",
                "chunk_id": 2,
                "score": 0.8,
            },
            {
                "text": "gold table",
                "source": "spec.pdf",
                "page_start": 62,
                "page_end": 62,
                "table_id": "表10.3.5",
                "chunk_id": 3,
                "score": 0.7,
            },
        ][:top_k]


class FakeReranker:
    calls = []

    def rerank(self, query, results, top_n):
        FakeReranker.calls.append((query, len(results), top_n))
        reranked = sorted(
            [item.copy() for item in results],
            key=lambda item: 0 if item.get("article_id") == "10.3.3" else 1,
        )
        for index, item in enumerate(reranked):
            item["rerank_score"] = float(10 - index)
        return reranked[:top_n]


class FakeIndexManager:
    def __init__(self, index_dir):
        pass

    def build_or_load(self, pdf_path, embedder):
        return type("Managed", (), {"vector_store": type("Store", (), {"chunk_records": []})()})()


class FakeBM25Retriever:
    def __init__(self, chunk_records):
        pass

    def retrieve(self, query, top_k):
        return [
            {
                "text": "bm25 only",
                "source": "spec.pdf",
                "page_start": 70,
                "page_end": 70,
                "chunk_id": 20,
                "score": 5.0,
            }
        ]


class EvalRunnerTest(unittest.TestCase):
    def test_hybrid_rerank_passes_full_deduplicated_union_to_reranker(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset.jsonl"
            dataset.write_text(json.dumps({
                "id": "q1",
                "question": "问题",
                "question_type": "article_lookup",
                "answerable": True,
                "gold_answer": "答案",
                "gold_evidence": [{"document": "spec.pdf", "page": 61, "article": "10.3.3"}],
            }, ensure_ascii=False), encoding="utf-8")
            FakeReranker.calls = []

            with patch("eval.run_retrieval.IndexManager", FakeIndexManager), patch(
                "eval.run_retrieval.Retriever", FakeRetriever
            ), patch("eval.run_retrieval.BM25Retriever", FakeBM25Retriever):
                report = evaluate_retrieval(
                    dataset_path=dataset,
                    pdf_path="spec.pdf",
                    embedder=object(),
                    reranker=FakeReranker(),
                    mode="hybrid_rerank",
                )

            self.assertEqual(report["cases"][0]["fused_candidate_count"], 4)
            self.assertEqual(FakeReranker.calls[0][1:], (4, 10))
            self.assertEqual(report["cases"][0]["gold_ranks_before_rerank"], [{"gold_index": 0, "rank": 3}])

    def test_dense_and_rerank_modes_report_per_case_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            FakeRetriever.calls = []
            FakeReranker.calls = []
            dataset = Path(tmp) / "dataset.jsonl"
            dataset.write_text(json.dumps({
                "id": "q1",
                "question": "问题",
                "question_type": "article_lookup",
                "answerable": True,
                "gold_answer": "答案",
                "gold_evidence": [{"document": "spec.pdf", "page": 61, "article": "10.3.3"}],
            }, ensure_ascii=False), encoding="utf-8")

            with patch("eval.run_retrieval.IndexManager", FakeIndexManager), patch(
                "eval.run_retrieval.Retriever", FakeRetriever
            ):
                dense = evaluate_retrieval(
                    dataset_path=dataset,
                    pdf_path="spec.pdf",
                    embedder=object(),
                    mode="dense",
                    top_k=2,
                )
                reranked = evaluate_retrieval(
                    dataset_path=dataset,
                    pdf_path="spec.pdf",
                    embedder=object(),
                    reranker=FakeReranker(),
                    mode="dense_rerank",
                    top_k=2,
                    rerank_top_n=2,
                )

            self.assertAlmostEqual(dense["overall"]["recall@1"], 0.0)
            self.assertAlmostEqual(dense["overall"]["recall@3"], 1.0)
            self.assertEqual(dense["cases"][0]["retrieved"][1]["rank"], 2)
            self.assertTrue(dense["cases"][0]["retrieved"][1]["hit"])
            self.assertEqual(FakeRetriever.calls[0], ("问题", 10))
            self.assertEqual(FakeReranker.calls[0], ("问题", 3, 10))
            self.assertAlmostEqual(reranked["overall"]["recall@1"], 1.0)
            self.assertIn("rerank_score", reranked["cases"][0]["retrieved"][0])

    def test_multi_gold_recall_and_unanswerable_cases_are_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset = Path(tmp) / "dataset.jsonl"
            lines = [
                {
                    "id": "q1",
                    "question": "多证据问题",
                    "question_type": "multi",
                    "answerable": True,
                    "gold_answer": "答案",
                    "gold_evidence": [
                        {"document": "spec.pdf", "page": 61, "article": "10.3.3"},
                        {"document": "spec.pdf", "page": 62, "table": "表10.3.5"},
                    ],
                },
                {
                    "id": "q2",
                    "question": "无答案问题",
                    "question_type": "unanswerable",
                    "answerable": False,
                    "gold_answer": "",
                    "gold_evidence": [],
                },
            ]
            dataset.write_text(
                "\n".join(json.dumps(item, ensure_ascii=False) for item in lines),
                encoding="utf-8",
            )

            with patch("eval.run_retrieval.IndexManager", FakeIndexManager), patch(
                "eval.run_retrieval.Retriever", FakeRetriever
            ):
                report = evaluate_retrieval(
                    dataset_path=dataset,
                    pdf_path="spec.pdf",
                    embedder=object(),
                    mode="dense",
                    top_k=3,
                )

            self.assertEqual(len(report["cases"]), 2)
            self.assertFalse(report["cases"][1]["metric_eligible"])
            self.assertEqual(report["overall"]["count"], 1)
            self.assertAlmostEqual(report["overall"]["recall@1"], 0.0)
            self.assertAlmostEqual(report["overall"]["recall@3"], 1.0)
            self.assertAlmostEqual(report["overall"]["hitrate@3"], 1.0)
            self.assertEqual(report["cases"][0]["gold_hit_ids_by_rank"][1], [0])
            self.assertEqual(report["cases"][0]["gold_hit_ids_by_rank"][2], [1])

    def test_writes_json_and_markdown_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = {
                "dataset_path": "dataset.jsonl",
                "mode": "dense",
                "overall": {"count": 1, "recall@1": 1, "recall@3": 1, "recall@5": 1, "recall@10": 1, "mrr@10": 1, "hitrate@1": 1, "hitrate@3": 1, "hitrate@5": 1, "hitrate@10": 1},
                "by_question_type": {"article": {"count": 1, "recall@1": 1, "recall@3": 1, "recall@5": 1, "recall@10": 1, "mrr@10": 1, "hitrate@1": 1, "hitrate@3": 1, "hitrate@5": 1, "hitrate@10": 1}},
                "cases": [{"id": "q1", "question_type": "article", "retrieved": [{"rank": 1, "hit": True}]}],
            }
            json_path = Path(tmp) / "report.json"
            md_path = Path(tmp) / "report.md"

            write_json_report(report, json_path)
            write_markdown_report(report, md_path)

            self.assertTrue(json_path.exists())
            self.assertIn("Retrieval Evaluation Report", md_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
