import json
from pathlib import Path

import pytest

from src.query_scope import (
    QueryScope,
    QueryScopeClarificationRequired,
    QueryScopeError,
    SpecEdition,
    resolve_query_scope,
    versions_from_catalog,
    versions_from_snapshot,
)


SNAPSHOT_ID = "39c3e07c109c07cb1dc331db3055cf041a33498aafb9dde6c2eb022421dd3020"
VERSIONS = (
    SpecEdition("cn.beijing.db11t995", "2025"),
    SpecEdition("cn.gb55033", "2022"),
    SpecEdition("cn.gb50157", "2013"),
)


def _resolve(scope, *, catalog=VERSIONS, snapshot=VERSIONS):
    return resolve_query_scope(
        scope,
        snapshot_id=SNAPSHOT_ID,
        snapshot_versions=snapshot,
        catalog_versions=catalog,
    )


def test_all_documents_resolves_to_the_bound_snapshot():
    resolved = _resolve(QueryScope.all_documents())
    assert resolved.snapshot_id == SNAPSHOT_ID
    assert set(resolved.business_ids) == {item.business_id for item in VERSIONS}


def test_exact_version_must_exist_in_catalog_and_snapshot():
    requested = QueryScope.exact_versions([SpecEdition("cn.gb55033", "2022")])
    assert _resolve(requested).business_ids == ("cn.gb55033@2022",)

    with pytest.raises(QueryScopeError, match="尚未发布"):
        _resolve(requested, snapshot=(VERSIONS[0], VERSIONS[2]))
    with pytest.raises(QueryScopeError, match="不在文档目录"):
        _resolve(
            QueryScope.exact_versions([SpecEdition("cn.gb55033", "1999")])
        )


def test_unspecified_and_spec_without_edition_require_clarification():
    with pytest.raises(QueryScopeClarificationRequired, match="选择查询范围"):
        _resolve(QueryScope.unspecified())
    with pytest.raises(QueryScopeClarificationRequired, match="明确版本"):
        _resolve(QueryScope.specifications(["cn.gb50157"]))


def test_request_payload_does_not_guess_mismatched_versions():
    with pytest.raises(QueryScopeError, match="matching lengths"):
        QueryScope.from_request_payload(
            {"spec_ids": ["cn.gb55033", "cn.gb50157"], "edition_ids": ["2022"]}
        )


def test_phase1_examples_have_the_expected_scope_contract():
    dataset = Path("eval/datasets/phase1_query_examples_v0.jsonl")
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 18
    for row in rows:
        scope = QueryScope.from_request_payload(row["requested_scope"])
        if row["expected_behavior"].startswith("ask_for_"):
            with pytest.raises(QueryScopeClarificationRequired):
                _resolve(scope)
        else:
            resolved = _resolve(scope)
            assert set(resolved.business_ids) == set(row["expected_spec_editions"])


def test_catalog_and_snapshot_adapters_use_business_identity():
    class Item:
        def __init__(self, spec_id, edition_id):
            self.spec_id = spec_id
            self.edition_id = edition_id

    class Indexed:
        def __init__(self, item):
            self.manifest = item

    catalog = type("Catalog", (), {"documents": [Item("cn.example", "2025")]})()
    snapshot = type(
        "Snapshot", (), {"documents": [Indexed(Item("cn.example", "2025"))]}
    )()

    assert versions_from_catalog(catalog) == (SpecEdition("cn.example", "2025"),)
    assert versions_from_snapshot(snapshot) == (SpecEdition("cn.example", "2025"),)
