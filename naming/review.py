"""Prepare source-backed review batches and compile explicit human decisions."""

import argparse
from datetime import date
import json
from pathlib import Path
import shutil
import tempfile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from knowledge.schema import digest, normalize, write_jsonl
from knowledge.search import KnowledgeSearch
from naming.catalog import Catalog, Name


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name_te: str = Field(min_length=1)
    name_en: str = Field(min_length=1)
    meaning: str = Field(min_length=2)
    gender: Literal["girl", "boy", "unisex"] | None = None
    origin: Literal["telugu", "sanskrit", "other", "unknown"] = "unknown"
    status: Literal["established", "coined"] | None = None
    flags: list[str] = Field(default_factory=list)
    notes: str = Field(min_length=1)
    observations: dict[str, str] = Field(default_factory=dict)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    candidate_id: str
    decision: Literal["pending", "approve", "reject"] = "pending"
    name_en: str
    meaning: str
    gender: Literal["girl", "boy", "unisex"] | None = None
    origin: Literal["telugu", "sanskrit", "other", "unknown"] = "unknown"
    status: Literal["established", "coined"] | None = None
    meaning_checked: bool = False
    name_usage_checked: bool = False
    origin_checked: bool = False
    acknowledged_flags: list[str] = Field(default_factory=list)
    note: str = ""


class Decisions(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    batch_id: str
    knowledge_version: str
    reviewer: str = ""
    reviewed_at: date | None = None
    decisions: list[Decision]


def prepare(shortlist, knowledge):
    """AI proposals remain pending, including fully sourced proposals."""
    items, seen = [], set()
    for raw in shortlist:
        draft = Draft.model_validate(raw)
        draft.name_te = normalize(draft.name_te)
        if draft.name_te in seen:
            raise ValueError("Duplicate shortlist spelling")
        seen.add(draft.name_te)
        records = [r for r in knowledge.records if r.title == draft.name_te]
        if not records:
            raise ValueError(f"No exact source evidence for {draft.name_te}")
        if set(draft.observations) - {r.id for r in records}:
            raise ValueError("Observation cites unknown evidence")
        item = {
            "proposal": draft.model_dump(),
            "evidence": [r.model_dump() for r in records],
        }
        item["candidate_id"] = digest(item)[:24]
        items.append(item)
    if not items:
        raise ValueError("An empty shortlist cannot be reviewed")
    batch = {
        "schema_version": 1,
        "assessment": "AI source comparison; awaiting human review",
        "knowledge_version": knowledge.version,
        "items": items,
    }
    batch["batch_id"] = digest(batch)[:20]
    return batch


def validate_batch(batch, knowledge):
    payload = {k: v for k, v in batch.items() if k != "batch_id"}
    if batch.get("batch_id") != digest(payload)[:20]:
        raise ValueError("Review batch fingerprint mismatch")
    if batch.get("schema_version") != 1:
        raise ValueError("Unsupported review batch schema")
    if batch.get("knowledge_version") != knowledge.version:
        raise ValueError("Review batch uses another knowledge version; prepare again")
    rebuilt = prepare([i["proposal"] for i in batch["items"]], knowledge)
    if rebuilt != batch:
        raise ValueError("Review evidence differs from the current source snapshot")


def decision_template(batch):
    decisions = []
    for item in batch["items"]:
        draft = item["proposal"]
        decisions.append(
            Decision(
                candidate_id=item["candidate_id"],
                **{
                    k: draft[k]
                    for k in ("name_en", "meaning", "gender", "origin", "status")
                },
            ).model_dump()
        )
    return Decisions(
        batch_id=batch["batch_id"],
        knowledge_version=batch["knowledge_version"],
        decisions=decisions,
    ).model_dump(mode="json")


def compile_decisions(batch, document, knowledge):
    validate_batch(batch, knowledge)
    review = Decisions.model_validate(document)
    if (
        review.batch_id != batch["batch_id"]
        or review.knowledge_version != knowledge.version
    ):
        raise ValueError("Decisions belong to another review batch")
    items = {i["candidate_id"]: i for i in batch["items"]}
    approved, seen = [], set()
    for decision in review.decisions:
        key = decision.candidate_id
        if key not in items or key in seen:
            raise ValueError("Unknown or repeated review candidate")
        seen.add(key)
        if decision.decision != "approve":
            continue
        if not review.reviewer or review.reviewed_at is None:
            raise ValueError("Approval requires a reviewer and review date")
        if not all(
            (
                decision.meaning_checked,
                decision.name_usage_checked,
                decision.origin_checked,
            )
        ):
            raise ValueError("Meaning, name usage, and origin need explicit review")
        item = items[key]
        flags = set(item["proposal"]["flags"])
        if not flags.issubset(decision.acknowledged_flags):
            raise ValueError("Reviewer must acknowledge the candidate's open flags")
        approved.append(
            Name(
                name_te=item["proposal"]["name_te"],
                name_en=decision.name_en,
                meaning=decision.meaning,
                gender=decision.gender,
                origin=decision.origin,
                status=decision.status,
                evidence_ids=[r["id"] for r in item["evidence"]],
                reviewed_by=review.reviewer,
                reviewed_at=review.reviewed_at.isoformat(),
            )
        )
    if not approved:
        raise ValueError("No human-approved names; no catalog will be written")
    return approved, review


def write_candidate(output, batch, document, knowledge):
    """Write a new bundle; never overwrite or activate the current catalog."""
    approved, review = compile_decisions(batch, document, knowledge)
    if output.exists():
        raise ValueError("Output already exists; choose a new review bundle")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="review-", dir=output.parent))
    try:
        write_jsonl(staging / "catalog.jsonl", approved)
        catalog = Catalog(staging / "catalog.jsonl", knowledge)
        audit = {
            "batch": batch,
            "review": review.model_dump(mode="json"),
            "catalog_version": catalog.version,
            "approved_names": len(approved),
            "activated": False,
        }
        (staging / "review.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        staging.rename(output)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "catalog": str(output / "catalog.jsonl"),
        **{k: audit[k] for k in ("catalog_version", "approved_names", "activated")},
    }


def render_report(batch):
    def cell(value):
        return str(value or "Needs review").replace("|", "\\|").replace("\n", " ")

    lines = [
        "# First Telugu name review batch",
        "",
        "All entries are AI-prepared proposals, pending human review. None is active.",
        "The spelling, intended meaning, naming usage, and origin must be checked separately.",
        "",
        f"Knowledge version: `{batch['knowledge_version']}` · Batch: `{batch['batch_id']}`",
        "",
        "| Candidate | Proposed meaning | Proposed origin | Name usage | Review flags |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in batch["items"]:
        p = item["proposal"]
        lines.append(
            "| "
            + " | ".join(
                map(
                    cell,
                    [
                        f"{p['name_te']} / {p['name_en']}",
                        p["meaning"],
                        p["origin"],
                        p["status"],
                        ", ".join(p["flags"]) or "Human confirmation",
                    ],
                )
            )
            + " |"
        )
    for item in batch["items"]:
        p = item["proposal"]
        lines += ["", f"## {p['name_te']} / {p['name_en']}", "", p["notes"], ""]
        for r in item["evidence"]:
            for ev in r["evidence"]:
                lines.append(
                    f"- [{ev['source_id']}, revision {ev['revision']}]({ev['url']})"
                    f" — {ev['attribution']}; [{ev['license']}]({ev['license_url']})."
                )
            if note := p["observations"].get(r["id"]):
                lines.append(f"  Source observation (AI paraphrase): {note}")
    lines += [
        "",
        "## How to record a decision",
        "",
        "Use `decisions_template.json` with the batch fingerprint. Leave a candidate pending,",
        "reject it, or explicitly approve its final fields after checking the linked evidence.",
        "For approval, supply the reviewer, date, meaning/name-usage/origin confirmations,",
        "and acknowledge every open flag. Unknown origin stays excluded from pure-Telugu results.",
        "The CLI writes a new candidate bundle; it does not activate it or merge existing names.",
        "See [the review instructions](../../docs/name-review.md).",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge", type=Path, default=Path("data/knowledge/index"))
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--shortlist", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    compile_ = commands.add_parser("compile")
    compile_.add_argument("--batch", type=Path, required=True)
    compile_.add_argument("--decisions", type=Path, required=True)
    compile_.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    knowledge = KnowledgeSearch(args.knowledge)
    if args.command == "prepare":
        batch = prepare(
            json.loads(args.shortlist.read_text(encoding="utf-8")), knowledge
        )
        if args.output.exists():
            raise ValueError(
                "Review output already exists; choose a new batch directory"
            )
        args.output.mkdir(parents=True)
        for name, value in [
            ("batch.json", batch),
            ("decisions_template.json", decision_template(batch)),
        ]:
            (args.output / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        (args.output / "README.md").write_text(render_report(batch), encoding="utf-8")
        print(
            json.dumps({"batch_id": batch["batch_id"], "pending": len(batch["items"])})
        )
    else:
        print(
            json.dumps(
                write_candidate(
                    args.output,
                    json.loads(args.batch.read_text(encoding="utf-8")),
                    json.loads(args.decisions.read_text(encoding="utf-8")),
                    knowledge,
                )
            )
        )


if __name__ == "__main__":
    main()
