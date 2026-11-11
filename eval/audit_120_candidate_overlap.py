"""Conservative lexical overlap triage, not a semantic independence decision."""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "eval/datasets"


def grams(value: str) -> Counter[str]:
    compact = "".join(c for c in value.lower() if c.isalnum() or "\u4e00" <= c <= "\u9fff")
    return Counter(compact[i:i+3] for i in range(max(0, len(compact)-2)))


def cosine(a: Counter, b: Counter) -> float:
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    norm = math.sqrt(sum(v*v for v in a.values()) * sum(v*v for v in b.values()))
    return dot / norm if norm else 0.0


def main() -> None:
    paths = sorted(DATA.glob("independent_120_*batch*.jsonl"))
    cases = [json.loads(line) for path in paths for line in path.read_text(encoding="utf-8").splitlines()]
    seen = json.loads((DATA / "independent_120_seen_inventory.json").read_text(encoding="utf-8"))["records"]
    rows = []
    for case in cases:
        q, a = grams(case["question"]), grams(case["reference_answer"] or "")
        ranked = []
        for previous in seen:
            score = max(cosine(q, grams(previous["question"] or "")), cosine(a, grams(previous["known_answer"] or "")))
            ranked.append((score, previous))
        ranked.sort(key=lambda item: item[0], reverse=True)
        rows.append({"case_id": case["case_id"], "fact_group_id": case["fact_group_id"],
                     "lexical_neighbors": [{"score": round(score, 3), "source_file": item["source_file"],
                                           "id": item["id"], "question": item["question"]}
                                          for score, item in ranked[:5]],
                     "decision": "pending_human_semantic_review"})
    path = DATA / "independent_120_overlap_triage_all.json"
    path.write_text(json.dumps({"warning": "Lexical similarity cannot establish semantic novelty; review fact, value, table row and conditions manually.", "cases": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
