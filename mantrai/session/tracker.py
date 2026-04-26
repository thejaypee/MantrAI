from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

from mantrai.core.config import get_db_path
from mantrai.core.schema import Confirmation

INIT_SQL = """
CREATE TABLE IF NOT EXISTS confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    agent_id TEXT,
    action_context TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_session ON confirmations(session_id, timestamp);

CREATE TABLE IF NOT EXISTS injection_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    prompt_preview TEXT,
    total_principles INTEGER NOT NULL,
    selected_count INTEGER NOT NULL,
    matched_keywords TEXT,
    fallback INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_audit_session ON injection_audit(session_id, timestamp);
"""


class SessionTracker:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executescript(INIT_SQL)

    def log_confirmation(
        self,
        session_id: str,
        agent_id: Optional[str] = None,
        action_context: Optional[str] = None,
        acknowledged: bool = True,
    ) -> Confirmation:
        ts = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO confirmations (session_id, timestamp, agent_id, action_context, acknowledged) VALUES (?, ?, ?, ?, ?)",
                (session_id, ts, agent_id, action_context, int(acknowledged)),
            )
            conn.commit()
        return Confirmation(
            session_id=session_id,
            timestamp=datetime.fromisoformat(ts),
            agent_id=agent_id,
            action_context=action_context,
            acknowledged=acknowledged,
        )

    def last_confirmation(self, session_id: str) -> Optional[Confirmation]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM confirmations WHERE session_id = ? ORDER BY timestamp DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return Confirmation(
            session_id=row["session_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            agent_id=row["agent_id"],
            action_context=row["action_context"],
            acknowledged=bool(row["acknowledged"]),
        )

    def compliance_window(self, session_id: str, window_minutes: int = 5) -> bool:
        last = self.last_confirmation(session_id)
        if last is None:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        return last.timestamp >= cutoff

    def session_stats(self, session_id: str) -> dict:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT COUNT(*) as count,
                       MIN(timestamp) as first,
                       MAX(timestamp) as last
                FROM confirmations
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return {
            "count": row["count"] if row else 0,
            "first": datetime.fromisoformat(row["first"]) if row and row["first"] else None,
            "last": datetime.fromisoformat(row["last"]) if row and row["last"] else None,
        }

    def log_injection_audit(self, session_id: str, audit: dict) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO injection_audit
                (session_id, timestamp, prompt_preview, total_principles, selected_count, matched_keywords, fallback)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    ts,
                    audit.get("prompt_preview", ""),
                    audit.get("total_principles", 0),
                    audit.get("selected_count", 0),
                    json.dumps(audit.get("matched_keywords", {})),
                    1 if audit.get("fallback") else 0,
                ),
            )
            conn.commit()

    def audit_log(self, session_id: str, limit: int = 20) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM injection_audit WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [
            {
                "session_id": r["session_id"],
                "timestamp": datetime.fromisoformat(r["timestamp"]),
                "prompt_preview": r["prompt_preview"],
                "total_principles": r["total_principles"],
                "selected_count": r["selected_count"],
                "matched_keywords": json.loads(r["matched_keywords"]) if r["matched_keywords"] else {},
                "fallback": bool(r["fallback"]),
            }
            for r in rows
        ]

    def compliance_log(self, session_id: str, limit: int = 20) -> List[Confirmation]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM confirmations WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [
            Confirmation(
                session_id=r["session_id"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                agent_id=r["agent_id"],
                action_context=r["action_context"],
                acknowledged=bool(r["acknowledged"]),
            )
            for r in rows
        ]
