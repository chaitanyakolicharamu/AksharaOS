"""Train a candidate ranker from reviewed, consented, same-request preference pairs."""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit

from feedback.store import FeedbackStore
from knowledge.schema import digest
from naming.catalog import BASELINE_WEIGHTS, FEATURE_NAMES

MIN_PAIRS = 100
MIN_USERS = 10
MIN_QUERY_GROUPS = 10
MIN_VALIDATION_PAIRS = 20


def preference_pairs(rows):
    requests = defaultdict(list)
    for row in rows:
        requests[(row["actor"], row["impression_id"])].append(row)
    pairs, per_user = [], Counter()
    for (actor, impression), votes in sorted(requests.items()):
        liked = sorted(
            (r for r in votes if r["vote"] == 1), key=lambda r: r["candidate_id"]
        )
        disliked = sorted(
            (r for r in votes if r["vote"] == -1), key=lambda r: r["candidate_id"]
        )
        if not liked or not disliked or per_user[actor] >= 20:
            continue
        good, bad = liked[0], disliked[0]
        difference = np.asarray(json.loads(good["features"])) - np.asarray(
            json.loads(bad["features"])
        )
        if (
            difference.shape != (len(FEATURE_NAMES),)
            or not np.isfinite(difference).all()
        ):
            raise ValueError("Invalid logged features")
        if not np.any(difference):
            continue
        pairs.append(
            {
                "actor": actor,
                "query_group": good["query_group"],
                "difference": difference.tolist(),
                "impression_id": impression,
            }
        )
        per_user[actor] += 1
    return pairs


def train(store, catalog_version, knowledge_version, output: Path):
    pairs = preference_pairs(store.training_rows(catalog_version, knowledge_version))
    users = {r["actor"] for r in pairs}
    groups = [r["query_group"] for r in pairs]
    if (
        len(pairs) < MIN_PAIRS
        or len(users) < MIN_USERS
        or len(set(groups)) < MIN_QUERY_GROUPS
    ):
        raise ValueError(
            f"Not enough reviewed human feedback: {len(pairs)} pairs, {len(users)} sessions, "
            f"{len(set(groups))} query groups. Need {MIN_PAIRS}, {MIN_USERS}, {MIN_QUERY_GROUPS}. "
            "No model written; baseline retained."
        )
    x = np.asarray([r["difference"] for r in pairs])
    split = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(split.split(x, groups=groups))
    if len(test_idx) < MIN_VALIDATION_PAIRS or len(train_idx) < 50:
        raise ValueError(
            "Insufficient independent train/validation groups; baseline retained"
        )
    # Split before mirroring; one pair per impression avoids inflated sample counts.
    x_train = np.concatenate([x[train_idx], -x[train_idx]])
    y_train = np.concatenate([np.ones(len(train_idx)), np.zeros(len(train_idx))])
    counts = Counter(pairs[i]["actor"] for i in train_idx)
    weights = np.asarray([1 / counts[pairs[i]["actor"]] for i in train_idx])
    weights = weights / weights.mean()
    model = LogisticRegression(
        fit_intercept=False, C=1.0, max_iter=1000, random_state=42
    )
    model.fit(x_train, y_train, sample_weight=np.concatenate([weights, weights]))
    learned = model.coef_[0]

    def accuracy(w):
        margins = x[test_idx] @ w
        return float(np.mean((margins > 1e-9) + 0.5 * (np.abs(margins) <= 1e-9)))

    baseline = accuracy(BASELINE_WEIGHTS)
    candidate = accuracy(learned)
    evaluation = {
        "validation_pairs": len(test_idx),
        "train_pairs": len(train_idx),
        "baseline_pairwise_accuracy": baseline,
        "candidate_pairwise_accuracy": candidate,
        "split": "query-group holdout; fixed seed 42; no mirrored-pair leakage",
        "train_query_groups": len({groups[i] for i in train_idx}),
        "validation_query_groups": len({groups[i] for i in test_idx}),
        "passed": candidate >= 0.55 and candidate >= baseline + 0.02,
    }
    result = {
        "feature_names": FEATURE_NAMES,
        "weights": learned.tolist(),
        "catalog_version": catalog_version,
        "knowledge_version": knowledge_version,
        "training_fingerprint": digest(pairs),
        "pairs": len(pairs),
        "sessions": len(users),
        "evaluation": evaluation,
        "promoted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result["version"] = digest(result)[:20]
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2), encoding="utf-8")
    temporary.replace(output)
    return result


def promote(candidate: Path, output: Path):
    model = json.loads(candidate.read_text(encoding="utf-8"))
    if (
        not model.get("evaluation", {}).get("passed")
        or model.get("feature_names") != FEATURE_NAMES
    ):
        raise ValueError("Candidate failed evaluation or has an incompatible schema")
    model["promoted"] = True
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(model, indent=2), encoding="utf-8")
    temporary.replace(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    fit = sub.add_parser("fit")
    fit.add_argument("--db", type=Path, default=Path("data/private/feedback.sqlite3"))
    fit.add_argument("--catalog-version", required=True)
    fit.add_argument("--knowledge-version", required=True)
    fit.add_argument(
        "--output", type=Path, default=Path("models/candidate_ranker.json")
    )
    release = sub.add_parser("promote")
    release.add_argument("--candidate", type=Path, required=True)
    release.add_argument(
        "--output", type=Path, default=Path("models/active_ranker.json")
    )
    args = parser.parse_args()
    if args.action == "fit":
        result = train(
            FeedbackStore(args.db),
            args.catalog_version,
            args.knowledge_version,
            args.output,
        )
        print(json.dumps(result["evaluation"], indent=2))
    else:
        promote(args.candidate, args.output)
        print(
            "Ranker approved for explicit loading; restart the API with AKSHARA_RANKER set to this file."
        )


if __name__ == "__main__":
    main()
