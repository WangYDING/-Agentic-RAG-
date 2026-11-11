"""No-model probe, intended to run in a process importing src from the chosen RAG root."""
import ast
import socket
from pathlib import Path

from eval.adapter_v1 import WorkflowAdapter
from eval.fingerprints_v1 import sha256, source_snapshot, write_json
from eval.freeze_v1 import inspect_knowledge_base


def probe_runtime(rag_root, tooling_root, output):
    def prohibited(*args, **kwargs):
        raise RuntimeError("network/model construction prohibited in binding probe")
    socket.socket.connect = prohibited
    socket.create_connection = prohibited
    import openai
    openai.OpenAI = prohibited
    openai.AsyncOpenAI = prohibited
    from src.agent_workflow import AgentWorkflow
    from src.config import AppConfig
    from src.knowledge_base import KnowledgeBaseManager
    from src.snapshot_retriever import SnapshotRetriever
    from src.spec_catalog import SpecCatalog
    from eval.schema import load_eval_dataset
    from eval.provenance import PUBLIC_CONFIG_FIELDS
    import src.agent_workflow as workflow_module

    rag_root, tooling_root = Path(rag_root).resolve(), Path(tooling_root).resolve()
    if Path(workflow_module.__file__).resolve() != rag_root / "src/agent_workflow.py":
        raise ValueError("probe imported the wrong RAG checkout")
    snapshot = source_snapshot(rag_root, ("src",))
    knowledge = inspect_knowledge_base(rag_root / ".rag_knowledge_base", rag_root / "data/spec_catalog.v1.json")
    # Local file validation only; load_active does not construct an embedding model.
    loaded = KnowledgeBaseManager(rag_root / ".rag_knowledge_base").load_active()
    catalog = SpecCatalog.load(rag_root / "data/spec_catalog.v1.json", repository_root=rag_root)
    retriever = SnapshotRetriever(loaded, catalog, object())
    config = AppConfig()  # defaults only; never loads .env or credentials
    public = {key: getattr(config, key, None) for key in PUBLIC_CONFIG_FIELDS}
    ids = {"embedding": config.embedding_model, "reranker": config.reranker_model, "generation": config.generation_model}
    class MustNotCall:
        def __getattr__(self, name):
            if name in {"grade", "generate_answer", "rerank", "score_candidates", "select_top"}:
                return prohibited
            raise AttributeError(name)
    workflow = AgentWorkflow(retriever, MustNotCall(), MustNotCall(), MustNotCall(),
                             retrieval_top_k=config.retrieval_top_k, evidence_top_n=config.evidence_top_n,
                             max_model_calls=config.max_model_calls, total_timeout_seconds=config.total_timeout_seconds,
                             index_version_id=loaded.snapshot_id, model_ids=ids)
    adapter = WorkflowAdapter(workflow)
    adapter.check_binding({"public_config": public, "models": {k: {"id": v} for k, v in ids.items()}}, knowledge, snapshot)
    old = load_eval_dataset(tooling_root / "eval/datasets/dev_v0.jsonl")[0]
    observation = adapter({"schema_version": "rag-eval.rag-input.v1", "case_id": "OLD-DEV-SCOPE-PROBE",
                           "question": old.question, "query_scope": {}})
    if observation["actual_action"] != "clarify" or observation["generator_invoked"] is not False:
        raise ValueError("unexpected no-scope probe behavior")
    function_names = {}
    for filename in ("agent_workflow.py", "application.py", "query_scope.py"):
        tree = ast.parse((rag_root / "src" / filename).read_text(encoding="utf-8"))
        function_names[filename] = sorted({n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)})
    report = {"notice": "NO-MODEL INTERFACE/SNAPSHOT PROBE, NOT REAL RAG QUALITY ACCEPTANCE",
              "rag_source": snapshot, "knowledge_binding": knowledge, "public_defaults": public,
              "configuration_scope": "defaults only, not effective deployment .env/config",
              "imported_workflow_file": str(Path(workflow_module.__file__).resolve()),
              "interface_functions": function_names,
              "real_snapshot_loaded": True, "actual_model_components_constructed": False,
              "actual_model_weights_or_provider_validated": False, "observation": observation,
              "source_lock_sha256": sha256(rag_root / "uv.lock")}
    write_json(output, report)
    print("latest RAG: bound source + 3-document snapshot + no-model scope clarification verified")
