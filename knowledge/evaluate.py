"""Small development retrieval checks, not a held-out measure of name quality."""

import argparse
import json
from pathlib import Path

from knowledge.search import KnowledgeSearch


def evaluate(index, cases):
    details = []
    for case in cases:
        found = [r.title for r, score in index.find(case["query"], 5)]
        first = next(
            (i for i, title in enumerate(found, 1) if title in case["expected_titles"]),
            None,
        )
        details.append(
            {**case, "retrieved_titles": found, "first_relevant_rank": first}
        )
    n = len(details)
    return {
        "knowledge_version": index.version,
        "records": len(index.records),
        "queries": n,
        "hit_at_1": sum(d["first_relevant_rank"] == 1 for d in details),
        "hit_at_5": sum(d["first_relevant_rank"] is not None for d in details),
        "mrr": sum(
            1 / d["first_relevant_rank"] if d["first_relevant_rank"] else 0
            for d in details
        )
        / n,
        "scope": "Development smoke queries used during implementation; not held-out evaluation or human name-quality ratings.",
        "details": details,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=Path("data/knowledge/index"))
    parser.add_argument(
        "--cases", type=Path, default=Path("configs/knowledge_eval.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        KnowledgeSearch(args.index), json.loads(args.cases.read_text(encoding="utf-8"))
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))


if __name__ == "__main__":
    main()
