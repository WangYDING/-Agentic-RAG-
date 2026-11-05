from types import SimpleNamespace

from src.agent_workflow import AgentWorkflow
from src.query_scope import QueryScope, SpecEdition
from src.snapshot_retriever import SnapshotRetriever


class FakeEmbedder:
    def embed_text(self, text):
        return [1.0, 0.0]


class FakeStore:
    def __init__(self, records):
        self.chunk_records = records
        self.search_calls = []

    def search(self, query_embedding, top_k):
        self.search_calls.append(top_k)
        return [{**item, "score": 1.0} for item in self.chunk_records[:top_k]]


def _record(spec_id, edition_id, chunk_id, article="6.1.1"):
    return {
        "text": f"{spec_id} evidence {chunk_id}",
        "source": "same-name.pdf",
        "spec_id": spec_id,
        "edition_id": edition_id,
        "document_id": f"{spec_id}@{edition_id}",
        "chunk_id": chunk_id,
        "page_start": chunk_id + 1,
        "page_end": chunk_id + 1,
        "article_id": article,
    }


def _facade():
    identities = [
        ("cn.first", "2025"),
        ("cn.second", "2022"),
        ("cn.third", "2013"),
    ]
    documents = []
    catalog_documents = []
    for spec_id, edition_id in identities:
        records = [_record(spec_id, edition_id, index) for index in range(3)]
        manifest = SimpleNamespace(
            spec_id=spec_id,
            edition_id=edition_id,
            business_id=f"{spec_id}@{edition_id}",
        )
        documents.append(SimpleNamespace(manifest=manifest, vector_store=FakeStore(records)))
        catalog_documents.append(
            SimpleNamespace(
                spec_id=spec_id,
                edition_id=edition_id,
                business_id=f"{spec_id}@{edition_id}",
                standard_code=spec_id.upper(),
                title=f"Title {edition_id}",
            )
        )
    snapshot = SimpleNamespace(snapshot_id="a" * 64, documents=documents)
    catalog = SimpleNamespace(documents=catalog_documents)
    return SnapshotRetriever(snapshot, catalog, FakeEmbedder()), documents


def test_existing_request_facade_keeps_old_snapshot_when_new_facade_is_created():
    old, _ = _facade()
    old_scoped = old.for_scope(QueryScope.all_documents())
    new, _ = _facade()
    new.snapshot_id = "b" * 64
    new.snapshot.snapshot_id = "b" * 64
    new_scoped = new.for_scope(QueryScope.all_documents())

    assert old_scoped.scope.snapshot_id == "a" * 64
    assert new_scoped.scope.snapshot_id == "b" * 64


def test_exact_scope_searches_only_selected_document_in_both_routes():
    facade, documents = _facade()
    scoped = facade.for_scope(
        QueryScope.exact_versions([SpecEdition("cn.second", "2022")])
    )

    results = scoped.retrieve("evidence", top_k=2)

    assert {item["spec_id"] for item in results} == {"cn.second"}
    assert documents[0].vector_store.search_calls == []
    assert documents[1].vector_store.search_calls == [2]
    assert documents[2].vector_store.search_calls == []
    assert scoped.calls[0]["scope"] == ["cn.second@2022"]


def test_all_scope_keeps_same_chunk_ids_distinct_across_documents():
    facade, _ = _facade()
    results = facade.for_scope(QueryScope.all_documents()).retrieve("evidence", top_k=1)

    assert len(results) == 3
    assert {(item["spec_id"], item["chunk_id"]) for item in results} == {
        ("cn.first", 0),
        ("cn.second", 0),
        ("cn.third", 0),
    }


def test_exact_article_lookup_is_applied_inside_each_selected_document():
    facade, _ = _facade()
    results = facade.for_scope(QueryScope.all_documents()).retrieve(
        "分别说明三份规范第 6.1.1 条", top_k=1
    )

    exact = [item for item in results if item.get("match_type") == "exact_article"]
    assert {item["spec_id"] for item in exact} == {
        "cn.first",
        "cn.second",
        "cn.third",
    }


def test_neighbor_expansion_cannot_cross_scope_or_document():
    facade, _ = _facade()
    scoped = facade.for_scope(
        QueryScope.exact_versions([SpecEdition("cn.first", "2025")])
    )
    seed = scoped.retrieve("evidence", top_k=1)

    expanded = scoped.expand_neighbors(seed)

    assert {(item["spec_id"], item["chunk_id"]) for item in expanded} == {
        ("cn.first", 0),
        ("cn.first", 1),
    }


class _Reranker:
    def rerank(self, query, results, top_n):
        return results[:top_n]


class _Grader:
    def __init__(self):
        self.calls = 0

    def grade(self, query, evidences, *, budget=None):
        self.calls += 1
        if budget:
            budget.consume()
        return SimpleNamespace(
            decision="insufficient",
            missing_requirements=["missing"],
            supported_evidence_ids=[],
        )


class _Rewriter:
    def rewrite(self, query, history, *, budget=None):
        if budget:
            budget.consume()
        return "retry"


class _Generator:
    def generate_answer(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("generator must not run")


def test_agent_first_and_retry_retrieval_share_the_same_scope():
    facade, documents = _facade()
    workflow = AgentWorkflow(
        facade,
        _Reranker(),
        _Grader(),
        _Generator(),
        _Rewriter(),
        index_version_id=facade.snapshot_id,
    )
    scope = QueryScope.exact_versions([SpecEdition("cn.third", "2013")])

    response = workflow.run("question", scope=scope)

    assert response.result_type == "refuse"
    assert response.state.query_scope == ("cn.third@2013",)
    assert documents[0].vector_store.search_calls == []
    assert documents[1].vector_store.search_calls == []
    assert documents[2].vector_store.search_calls == [10, 10]


def test_agent_ambiguous_scope_clarifies_without_retrieval():
    facade, documents = _facade()
    grader = _Grader()
    workflow = AgentWorkflow(facade, _Reranker(), grader, _Generator(), _Rewriter())

    response = workflow.run("第 6.1.1 条是什么？")

    assert response.result_type == "refuse"
    assert response.state.final_action == "clarify_scope"
    assert "选择查询范围" in response.answer
    assert grader.calls == 0
    assert all(item.vector_store.search_calls == [] for item in documents)
