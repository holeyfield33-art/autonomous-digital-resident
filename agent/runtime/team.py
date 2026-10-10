"""Shared broadcast channel for a team of residents.

One SQLite file the whole team opens; every message a member posts is visible to every
teammate. Each member keeps a durable cursor so it is shown each teammate message exactly
once (on its next wake), while the full history stays queryable. WAL + a busy timeout make
concurrent access from the separate resident processes safe.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def _now():
    return datetime.now(timezone.utc).isoformat()


class TeamChannel:
    """A member's handle on the shared team bus. `member` is this resident's name."""

    def __init__(self, db_path, member):
        if not member:
            raise ValueError("team member name required")
        self.db_path = str(db_path)
        self.member = member
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(
                "CREATE TABLE IF NOT EXISTS team_messages("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT NOT NULL, "
                "summary TEXT NOT NULL, body TEXT NOT NULL, at TEXT NOT NULL);"
                "CREATE TABLE IF NOT EXISTS team_cursor("
                "member TEXT PRIMARY KEY, last_id INTEGER NOT NULL);"
            )
            db.execute(
                "INSERT OR IGNORE INTO team_cursor(member,last_id) VALUES(?,0)", (self.member,)
            )

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=5000")
            db.row_factory = sqlite3.Row
            yield db
            db.commit()
        finally:
            db.close()

    def post(self, summary, body=""):
        """Broadcast a message to every teammate. They see it on their next wake.
        Name a teammate in the text if it is meant mainly for them; everyone still sees it."""
        if not str(summary).strip():
            raise ValueError("summary required")
        with self._db() as db:
            cur = db.execute(
                "INSERT INTO team_messages(sender,summary,body,at) VALUES (?,?,?,?)",
                (self.member, str(summary), str(body or ""), _now()),
            )
            return {"posted": cur.lastrowid, "to": "team"}

    def unseen(self, limit=20):
        """Teammate messages this member has not been shown yet (newest `limit`), oldest-first.
        Advances this member's cursor past everything that currently exists, so each message is
        shown once. Own messages are never returned. Full history remains in `recent`."""
        with self._db() as db:
            row = db.execute(
                "SELECT last_id FROM team_cursor WHERE member=?", (self.member,)
            ).fetchone()
            last = row["last_id"] if row else 0
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT id,sender,summary,body,at FROM team_messages "
                    "WHERE id>? AND sender!=? ORDER BY id DESC LIMIT ?",
                    (last, self.member, limit),
                )
            ]
            top = db.execute("SELECT MAX(id) AS m FROM team_messages").fetchone()["m"] or 0
            db.execute(
                "INSERT INTO team_cursor(member,last_id) VALUES(?,?) "
                "ON CONFLICT(member) DO UPDATE SET last_id=excluded.last_id",
                (self.member, top),
            )
            rows.reverse()
            return rows

    def recent(self, limit=30):
        """Recent team messages (any sender), newest-first — the full shared history to pull on demand."""
        with self._db() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,sender,summary,body,at FROM team_messages ORDER BY id DESC LIMIT ?",
                    (limit,),
                )
            ]

    def members(self):
        """Every teammate known to the bus (each registers itself on startup)."""
        with self._db() as db:
            return [r["member"] for r in db.execute("SELECT member FROM team_cursor ORDER BY member")]
