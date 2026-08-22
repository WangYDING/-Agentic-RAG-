import unittest
from types import SimpleNamespace

from src.agent_workflow import AgentWorkflow, REFUSAL_MESSAGE


def result(chunk_id, text=None):
    return {
        "text": text or f"evidence {chunk_id}",
        "source": "spec.pdf",
        "chunk_id": chunk_id,
        "page_start": chunk_id + 1,
        "article_id": f"1.1.{chunk_id}",
    }


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def retrieve(self, query, top_k):
        self.calls.append((query, top_k))
        offset = 0 if len(self.calls) == 1 else 10
        return [result(offset + index) for index in range(3)]


class FakeReranker:
    def __init__(self):
        self.calls = []

    def rerank(self, query, results, top_n):
        self.calls.append((query, list(results), top_n))
        return results[:top_n]


class FakeGrader:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    def grade(self, query, evidences):
        self.calls.append((query, list(evidences)))
        decision, missing = self.decisions.pop(0)
        return SimpleNamespace(decision=decision, missing_requirements=missing)


class FakeGenerator:
    def __init__(self):
        self.calls = []

    def generate_answer(self, query, evidences, chat_history):
        self.calls.append((query, list(evidences), list(chat_history)))
        return "answer [E1]"


class FakeRewriter:
    def __init__(self):
        self.calls = []

    def rewrite(self, query, chat_history):
        self.calls.append((query, list(chat_history)))
        return "targeted retry query"


class AgentWorkflowTest(unittest.TestCase):
    def build(self, decisions, rewriter=None):
        self.retriever = FakeRetriever()
        self.reranker = FakeReranker()
        self.grader = FakeGrader(decisions)
        self.generator = FakeGenerator()
        return AgentWorkflow(self.retriever, self.reranker, self.grader, self.generator, rewriter)

    def test_first_grade_sufficient_answers_without_retry_and_validates_citations(self):
        response = self.build([("sufficient", [])]).run("question")

        self.assertEqual(response.state.retry_count, 0)
        self.assertEqual(response.state.final_action, "answer")
        self.assertEqual([item["step"] for item in response.state.trace], ["retrieve", "grade", "answer", "citation_validation"])
        self.assertTrue(response.state.citation_validation.valid)
        self.assertEqual(len(self.retriever.calls), 1)
        self.assertEqual(len(self.generator.calls), 1)

    def test_retry_once_then_answer_when_second_grade_is_sufficient(self):
        rewriter = FakeRewriter()
        response = self.build([("insufficient", ["second requirement"]), ("sufficient", [])], rewriter).run("question")

        self.assertEqual(response.state.retry_count, 1)
        self.assertEqual(response.state.rewritten_query, "targeted retry query")
        self.assertEqual(response.state.final_action, "answer")
        self.assertEqual([item["step"] for item in response.state.trace], ["retrieve", "grade", "retry", "retrieve", "grade", "answer", "citation_validation"])
        self.assertIn("second requirement", rewriter.calls[0][0])
        self.assertEqual(len(self.generator.calls), 1)
        self.assertEqual(len(self.reranker.calls[1][1]), 6)

    def test_two_insufficient_grades_refuse_without_generator(self):
        response = self.build([("insufficient", ["cost"]), ("insufficient", ["project cost"])]).run("question")

        self.assertEqual(response.state.retry_count, 1)
        self.assertEqual(response.state.final_action, "refuse")
        self.assertTrue(response.answer.startswith(REFUSAL_MESSAGE))
        self.assertIn("project cost", response.answer)
        self.assertEqual(self.generator.calls, [])
        self.assertEqual(len(self.retriever.calls), 2)
        self.assertEqual(len(self.grader.calls), 2)
        self.assertEqual([item["step"] for item in response.state.trace], ["retrieve", "grade", "retry", "retrieve", "grade", "refuse"])

    def test_retry_limit_cannot_exceed_one(self):
        with self.assertRaisesRegex(ValueError, "max_retries=1"):
            AgentWorkflow(FakeRetriever(), FakeReranker(), FakeGrader([]), FakeGenerator(), max_retries=2)


if __name__ == "__main__":
    unittest.main()
