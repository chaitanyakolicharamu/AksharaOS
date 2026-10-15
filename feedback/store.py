from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time

from knowledge.schema import digest


def actor_id(token):
    return hashlib.sha256(token.encode()).hexdigest()


class FeedbackStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS impressions (
                    id TEXT PRIMARY KEY, actor TEXT NOT NULL, query_group TEXT NOT NULL,
                    catalog_version TEXT NOT NULL, knowledge_version TEXT NOT NULL,
                    model_version TEXT NOT NULL, created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shown (
                    impression_id TEXT REFERENCES impressions(id) ON DELETE CASCADE,
                    candidate_id TEXT NOT NULL, features TEXT NOT NULL, position INTEGER NOT NULL,
                    PRIMARY KEY (impression_id, candidate_id)
                );
                CREATE TABLE IF NOT EXISTS votes (
                    id TEXT PRIMARY KEY, impression_id TEXT NOT NULL, candidate_id TEXT NOT NULL,
                    vote INTEGER NOT NULL CHECK(vote IN (-1,1)), reason TEXT NOT NULL,
                    consent INTEGER NOT NULL, moderation TEXT NOT NULL DEFAULT 'pending',
                    reviewed_by TEXT, updated_at REAL NOT NULL,
                    UNIQUE(impression_id, candidate_id),
                    FOREIGN KEY(impression_id,candidate_id) REFERENCES shown(impression_id,candidate_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS impressions_actor_time ON impressions(actor, created_at);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def record_impression(self, token, query, candidates, catalog):
        actor = actor_id(token)
        impression = secrets.token_urlsafe(24)
        context = query.model_dump(exclude={"top_k"})
        context["query"] = context["query"].casefold()
        context["starts_with"] = context["starts_with"].casefold()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute(
                "SELECT COUNT(*) FROM impressions WHERE actor=? AND created_at>?",
                (actor, time.time() - 3600),
            ).fetchone()[0]
            if count >= 60:
                raise ValueError("Session limit reached; try again later")
            db.execute(
                "INSERT INTO impressions VALUES (?,?,?,?,?,?,?)",
                (
                    impression,
                    actor,
                    digest(context),
                    catalog.version,
                    catalog.knowledge.version,
                    catalog.model_version,
                    time.time(),
                ),
            )
            db.executemany(
                "INSERT INTO shown VALUES (?,?,?,?)",
                [
                    (
                        impression,
                        row["candidate_id"],
                        json.dumps(row["features"]),
                        position,
                    )
                    for position, row in enumerate(candidates, 1)
                ],
            )
        return impression

    def vote(self, token, impression, candidate, value, reason, consent):
        if value not in {-1, 1}:
            raise ValueError("Vote must be like or dislike")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            shown = db.execute(
                """SELECT i.created_at FROM shown s JOIN impressions i ON i.id=s.impression_id
                WHERE s.impression_id=? AND s.candidate_id=? AND i.actor=?""",
                (impression, candidate, actor_id(token)),
            ).fetchone()
            if not shown or shown[0] < time.time() - 30 * 86400:
                raise ValueError("Unknown or expired suggestion for this session")
            vote_id = secrets.token_urlsafe(18)
            db.execute(
                """INSERT INTO votes (id,impression_id,candidate_id,vote,reason,consent,updated_at)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(impression_id,candidate_id) DO UPDATE SET
                vote=excluded.vote,reason=excluded.reason,consent=excluded.consent,
                moderation='pending',reviewed_by=NULL,updated_at=excluded.updated_at""",
                (
                    vote_id,
                    impression,
                    candidate,
                    value,
                    reason,
                    int(consent),
                    time.time(),
                ),
            )
            row = db.execute(
                "SELECT id FROM votes WHERE impression_id=? AND candidate_id=?",
                (impression, candidate),
            ).fetchone()
        return row[0]

    def moderate(self, vote_id, status, reviewer):
        if status not in {"approved", "rejected"} or not reviewer.strip():
            raise ValueError("Review requires approved/rejected status and reviewer")
        with self.connect() as db:
            result = db.execute(
                "UPDATE votes SET moderation=?,reviewed_by=? WHERE id=?",
                (status, reviewer, vote_id),
            )
            if result.rowcount != 1:
                raise ValueError("Unknown feedback ID")

    def withdraw(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM impressions WHERE actor=?", (actor_id(token),))

    def prune(self, days=90):
        if days < 1:
            raise ValueError("Retention must be positive")
        with self.connect() as db:
            result = db.execute(
                "DELETE FROM impressions WHERE created_at<?",
                (time.time() - days * 86400,),
            )
            return result.rowcount

    def training_rows(self, catalog_version, knowledge_version):
        with self.connect() as db:
            # Select the latest vote FIRST, then filter consent/moderation. A newer
            # withdrawal or pending edit must not resurrect an older approved vote.
            rows = [
                dict(row)
                for row in db.execute(
                    """SELECT v.*, i.actor, i.query_group,
                i.catalog_version, i.knowledge_version, s.features FROM votes v
                JOIN impressions i ON i.id=v.impression_id
                JOIN shown s ON s.impression_id=v.impression_id AND s.candidate_id=v.candidate_id
                WHERE i.catalog_version=? AND i.knowledge_version=?
                ORDER BY v.updated_at DESC, v.id""",
                    (catalog_version, knowledge_version),
                )
            ]
        latest = {}
        for row in rows:
            key = (row["actor"], row["query_group"], row["candidate_id"])
            latest.setdefault(key, row)
        return [
            row
            for row in latest.values()
            if row["consent"]
            and row["moderation"] == "approved"
            and row["reason"] != "meaning_incorrect"
        ]
