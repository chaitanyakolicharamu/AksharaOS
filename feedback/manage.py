"""Offline moderation only; these actions are deliberately absent from the public API."""

import argparse
import json
from pathlib import Path

from feedback.store import FeedbackStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", type=Path, default=Path("data/private/feedback.sqlite3")
    )
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("pending")
    for verb in ("approve", "reject"):
        command = sub.add_parser(verb)
        command.add_argument("--id", required=True)
        command.add_argument("--reviewer", required=True)
    prune = sub.add_parser("prune")
    prune.add_argument("--days", type=int, default=90)
    args = parser.parse_args()
    store = FeedbackStore(args.db)
    if args.action == "pending":
        with store.connect() as db:
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT id,candidate_id,vote,reason,consent FROM votes WHERE moderation='pending' LIMIT 100"
                )
            ]
        print(json.dumps(rows, indent=2))
    elif args.action == "prune":
        print(json.dumps({"deleted_impressions": store.prune(args.days)}))
    else:
        store.moderate(
            args.id,
            "approved" if args.action == "approve" else "rejected",
            args.reviewer,
        )
        print("Feedback reviewed.")


if __name__ == "__main__":
    main()
