"""Controller-owned durable events, continuity, memory outbox and spend claims."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


class BudgetExceeded(RuntimeError):
    pass


class State:
    def __init__(self, root: Path, cap_micro: int = 500_000):
        if type(cap_micro) is not int or cap_micro < 0:
            raise ValueError("Nonnegative integer budget required")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "resident.sqlite"
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cycles(id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started TEXT NOT NULL, ended TEXT, mode TEXT NOT NULL, status TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '', direction TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle INTEGER NOT NULL, at TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS memories(key TEXT PRIMARY KEY, value TEXT NOT NULL,
                    synced INTEGER NOT NULL DEFAULT 0, error TEXT);
                CREATE TABLE IF NOT EXISTS spend(id TEXT PRIMARY KEY, cycle INTEGER NOT NULL,
                    reserved INTEGER NOT NULL, charged INTEGER, provider TEXT);
            """)
            for key, value in (
                ("resident_id", uuid.uuid4().hex),
                ("cap_micro", str(cap_micro)),
                ("budget_halted", "false"),
            ):
                db.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (key, value))
            # Explicit configuration may raise a stale cap, but never lower it.
            current = int(db.execute("SELECT value FROM settings WHERE key='cap_micro'").fetchone()[0])
            if cap_micro < current:
                raise ValueError("Budget cap cannot be lowered below the durable value")
            if cap_micro > current:
                db.execute("UPDATE settings SET value=? WHERE key='cap_micro'", (str(cap_micro),))

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @property
    def resident_id(self):
        with self.db() as db:
            return db.execute("SELECT value FROM settings WHERE key='resident_id'").fetchone()[0]

    def begin(self, mode):
        with self.db() as db:
            return db.execute(
                "INSERT INTO cycles(started,mode,status) VALUES (?,?,'running')", (now(), mode)
            ).lastrowid

    def recover(self):
        with self.db() as db:
            db.execute("UPDATE cycles SET status='interrupted',ended=? WHERE status='running'", (now(),))

    def event(self, cycle, kind, payload):
        encoded = json.dumps(payload, ensure_ascii=False)
        if len(encoded.encode()) > 300_000:
            raise ValueError("Event exceeds record limit")
        with self.db() as db:
            db.execute(
                "INSERT INTO events(cycle,at,kind,payload) VALUES (?,?,?,?)", (cycle, now(), kind, encoded)
            )

    def finish(self, cycle, status, summary, direction):
        with self.db() as db:
            db.execute(
                "UPDATE cycles SET ended=?,status=?,summary=?,direction=? WHERE id=?",
                (now(), status, summary, direction, cycle),
            )

    def recent(self, limit=8):
        with self.db() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM cycles ORDER BY id DESC LIMIT ?", (min(limit, 100),))
            ]

    def events(self, cycle):
        with self.db() as db:
            return [
                {**dict(row), "payload": json.loads(row["payload"])}
                for row in db.execute("SELECT * FROM events WHERE cycle=? ORDER BY id", (cycle,))
            ]

    def remember(self, key, value):
        if not key.startswith(f"resident/{self.resident_id}/") or len(value.encode()) > 16000:
            raise ValueError("Invalid resident memory")
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO memories(key,value) VALUES (?,?)", (key, value))

    def pending(self):
        with self.db() as db:
            return [
                dict(r) for r in db.execute("SELECT * FROM memories WHERE synced=0 ORDER BY rowid LIMIT 5")
            ]

    def memory_result(self, key, error=None):
        with self.db() as db:
            db.execute("UPDATE memories SET synced=?,error=? WHERE key=?", (int(error is None), error, key))

    def recall(self, query="", limit=5):
        if not isinstance(query, str) or len(query) > 200:
            raise ValueError("Invalid memory query")
        with self.db() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT key,value,synced FROM memories WHERE instr(lower(value),lower(?))>0 ORDER BY rowid DESC LIMIT ?",
                    (query, min(max(int(limit), 1), 10)),
                )
            ]

    def reserve(self, cycle, amount):
        if type(amount) is not int or amount <= 0:
            raise ValueError("Positive integer reservation required")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            settings = dict(db.execute("SELECT key,value FROM settings"))
            used = db.execute("SELECT coalesce(sum(coalesce(charged,reserved)),0) FROM spend").fetchone()[0]
            if settings["budget_halted"] == "true" or used + amount > int(settings["cap_micro"]):
                raise BudgetExceeded("Durable spend cap reached")
            ident = uuid.uuid4().hex
            db.execute("INSERT INTO spend(id,cycle,reserved) VALUES (?,?,?)", (ident, cycle, amount))
            return ident

    def settle(self, ident, amount, provider):
        if type(amount) is not int or amount < 0:
            raise ValueError("Invalid usage charge")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM spend WHERE id=?", (ident,)).fetchone()
            if row is None or row["charged"] is not None:
                raise ValueError("Unknown or settled reservation")
            db.execute("UPDATE spend SET charged=?,provider=? WHERE id=?", (amount, provider, ident))
            if amount > row["reserved"]:
                db.execute("UPDATE settings SET value='true' WHERE key='budget_halted'")

    def budget(self):
        with self.db() as db:
            settings = dict(db.execute("SELECT key,value FROM settings"))
            row = db.execute(
                "SELECT count(*),coalesce(sum(coalesce(charged,reserved)),0),count(*)-count(charged) FROM spend"
            ).fetchone()
            return {
                "calls": row[0],
                "accounted_usd": row[1] / 1e6,
                "unresolved": row[2],
                "cap_usd": int(settings["cap_micro"]) / 1e6,
                "halted": settings["budget_halted"] == "true",
                "billing_receipt": False,
            }

    def heartbeat(self, active):
        import os

        with self.db() as db:
            db.execute(
                "INSERT OR REPLACE INTO settings VALUES ('runtime',?)",
                (json.dumps({"active": active, "pid": os.getpid(), "at": now()}),),
            )

    def runtime(self):
        with self.db() as db:
            row = db.execute("SELECT value FROM settings WHERE key='runtime'").fetchone()
        info = json.loads(row[0]) if row else {"active": False}
        fresh = (
            bool(info.get("at"))
            and (datetime.now(timezone.utc) - datetime.fromisoformat(info["at"])).total_seconds() < 45
        )
        return {**info, "healthy": bool(info.get("active") and fresh)}


@contextmanager
def single_runner(root: Path):
    """OS releases this lock after a crash; stale cycles stay interrupted, not replayed."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / "runner.lock").open("a+b") as handle:
        if handle.seek(0, 2) == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        import os

        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("A resident is already running for this state directory") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
