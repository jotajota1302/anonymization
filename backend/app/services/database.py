"""SQLite database service with async support."""

import aiosqlite
import os
from contextlib import asynccontextmanager
from typing import Optional, List, Any
from datetime import datetime

import structlog

logger = structlog.get_logger()

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS ticket_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system TEXT NOT NULL,
    source_ticket_id TEXT NOT NULL,
    kosin_ticket_id TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    anonymized_description TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    UNIQUE(source_system, source_ticket_id)
);

CREATE TABLE IF NOT EXISTS substitution_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_mapping_id INTEGER NOT NULL REFERENCES ticket_mapping(id),
    encrypted_map BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_mapping_id INTEGER NOT NULL REFERENCES ticket_mapping(id),
    role TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operator_id TEXT NOT NULL,
    action TEXT NOT NULL,
    ticket_mapping_id INTEGER REFERENCES ticket_mapping(id),
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    system_type TEXT NOT NULL DEFAULT 'source',
    connector_type TEXT NOT NULL DEFAULT 'jira',
    base_url TEXT NOT NULL DEFAULT '',
    auth_token TEXT NOT NULL DEFAULT '',
    auth_email TEXT NOT NULL DEFAULT '',
    project_key TEXT NOT NULL DEFAULT '',
    extra_config TEXT NOT NULL DEFAULT '{}',
    is_active INTEGER NOT NULL DEFAULT 1,
    is_mock INTEGER NOT NULL DEFAULT 1,
    polling_interval_sec INTEGER NOT NULL DEFAULT 60,
    last_connection_test TIMESTAMP,
    last_connection_status TEXT,
    last_connection_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
"""


class DatabaseService:
    """Async SQLite database service."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_dir()

    def _ensure_dir(self):
        dir_path = os.path.dirname(self.db_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

    async def init(self):
        """Initialize database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.executescript(DB_SCHEMA)
            await db.commit()
        logger.info("database_initialized", path=self.db_path)

    @asynccontextmanager
    async def _connect(self):
        """Create a connection with WAL mode and busy timeout for Azure Files compatibility."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            yield db

    async def execute(self, query: str, params: tuple = ()) -> Optional[int]:
        """Execute a write query. Returns lastrowid for inserts."""
        async with self._connect() as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor.lastrowid

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Fetch a single row as dict."""
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetchall(self, query: str, params: tuple = ()) -> List[dict]:
        """Fetch all rows as list of dicts."""
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # --- Ticket Mapping ---

    async def create_ticket_mapping(
        self, source_system: str, source_ticket_id: str,
        kosin_ticket_id: str, summary: str, anonymized_description: str,
        priority: str = "medium"
    ) -> int:
        return await self.execute(
            """INSERT INTO ticket_mapping
               (source_system, source_ticket_id, kosin_ticket_id, summary, anonymized_description, priority)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (source_system, source_ticket_id, kosin_ticket_id, summary, anonymized_description, priority)
        )

    async def get_ticket(self, ticket_id: int) -> Optional[dict]:
        return await self.fetchone(
            "SELECT * FROM ticket_mapping WHERE id = ?", (ticket_id,)
        )

    async def get_all_tickets(self) -> List[dict]:
        return await self.fetchall(
            "SELECT * FROM ticket_mapping ORDER BY created_at DESC"
        )

    async def get_ingested_ticket_keys(self) -> set:
        """Get set of source_ticket_id values already ingested."""
        rows = await self.fetchall(
            "SELECT source_ticket_id FROM ticket_mapping"
        )
        return {row["source_ticket_id"] for row in rows}

    async def get_ticket_by_source_key(self, source_key: str) -> Optional[dict]:
        """Find a ticket mapping by its source ticket key."""
        return await self.fetchone(
            "SELECT * FROM ticket_mapping WHERE source_ticket_id = ?",
            (source_key,)
        )

    async def update_ticket_status(self, ticket_id: int, status: str):
        closed_at = datetime.utcnow().isoformat() if status in ("resolved", "closed") else None
        await self.execute(
            "UPDATE ticket_mapping SET status = ?, closed_at = ? WHERE id = ?",
            (status, closed_at, ticket_id)
        )

    async def get_all_ticket_mappings_with_kosin(self) -> List[dict]:
        """Get all ticket mappings with KOSIN key info for admin view."""
        return await self.fetchall(
            "SELECT id, source_system, source_ticket_id, kosin_ticket_id, summary, status, priority, created_at FROM ticket_mapping ORDER BY created_at DESC"
        )

    async def get_ticket_by_kosin_key(self, kosin_key: str) -> Optional[dict]:
        """Find a ticket mapping by its KOSIN ticket key."""
        return await self.fetchone(
            "SELECT * FROM ticket_mapping WHERE kosin_ticket_id = ?",
            (kosin_key,)
        )

    async def delete_ticket_mapping(self, ticket_id: int):
        """Delete a ticket mapping and all related data (cascade)."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM chat_history WHERE ticket_mapping_id = ?", (ticket_id,))
            await db.execute("DELETE FROM substitution_map WHERE ticket_mapping_id = ?", (ticket_id,))
            await db.execute("DELETE FROM audit_log WHERE ticket_mapping_id = ?", (ticket_id,))
            await db.execute("DELETE FROM ticket_mapping WHERE id = ?", (ticket_id,))
            await db.commit()

    # --- Substitution Map ---

    async def save_substitution_map(self, ticket_mapping_id: int, encrypted_map: bytes):
        existing = await self.fetchone(
            "SELECT id FROM substitution_map WHERE ticket_mapping_id = ?",
            (ticket_mapping_id,)
        )
        if existing:
            await self.execute(
                "UPDATE substitution_map SET encrypted_map = ?, updated_at = ? WHERE ticket_mapping_id = ?",
                (encrypted_map, datetime.utcnow().isoformat(), ticket_mapping_id)
            )
        else:
            await self.execute(
                "INSERT INTO substitution_map (ticket_mapping_id, encrypted_map) VALUES (?, ?)",
                (ticket_mapping_id, encrypted_map)
            )

    async def get_substitution_map(self, ticket_mapping_id: int) -> Optional[bytes]:
        row = await self.fetchone(
            "SELECT encrypted_map FROM substitution_map WHERE ticket_mapping_id = ?",
            (ticket_mapping_id,)
        )
        return row["encrypted_map"] if row else None

    async def delete_substitution_map(self, ticket_mapping_id: int):
        await self.execute(
            "DELETE FROM substitution_map WHERE ticket_mapping_id = ?",
            (ticket_mapping_id,)
        )

    # --- Chat History ---

    async def add_chat_message(self, ticket_mapping_id: int, role: str, message: str):
        await self.execute(
            "INSERT INTO chat_history (ticket_mapping_id, role, message) VALUES (?, ?, ?)",
            (ticket_mapping_id, role, message)
        )

    async def get_chat_history(self, ticket_mapping_id: int) -> List[dict]:
        return await self.fetchall(
            "SELECT role, message, created_at FROM chat_history WHERE ticket_mapping_id = ? ORDER BY created_at",
            (ticket_mapping_id,)
        )

    # --- Audit Log ---

    async def add_audit_log(
        self, operator_id: str, action: str,
        ticket_mapping_id: int, details: str = None
    ):
        await self.execute(
            "INSERT INTO audit_log (operator_id, action, ticket_mapping_id, details) VALUES (?, ?, ?, ?)",
            (operator_id, action, ticket_mapping_id, details)
        )

    async def get_audit_log(self, ticket_mapping_id: int = None) -> List[dict]:
        if ticket_mapping_id:
            return await self.fetchall(
                "SELECT * FROM audit_log WHERE ticket_mapping_id = ? ORDER BY created_at DESC",
                (ticket_mapping_id,)
            )
        return await self.fetchall("SELECT * FROM audit_log ORDER BY created_at DESC")

    # --- System Config ---

    async def get_all_system_configs(self) -> List[dict]:
        return await self.fetchall(
            "SELECT * FROM system_config ORDER BY system_name"
        )

    async def get_system_config(self, name: str) -> Optional[dict]:
        return await self.fetchone(
            "SELECT * FROM system_config WHERE system_name = ?", (name,)
        )

    async def upsert_system_config(self, name: str, **fields) -> None:
        existing = await self.get_system_config(name)
        if existing:
            sets = []
            vals = []
            for k, v in fields.items():
                if v is not None:
                    sets.append(f"{k} = ?")
                    vals.append(v)
            if not sets:
                return
            sets.append("updated_at = ?")
            vals.append(datetime.utcnow().isoformat())
            vals.append(name)
            await self.execute(
                f"UPDATE system_config SET {', '.join(sets)} WHERE system_name = ?",
                tuple(vals)
            )
        else:
            cols = ["system_name"]
            vals = [name]
            for k, v in fields.items():
                if v is not None:
                    cols.append(k)
                    vals.append(v)
            placeholders = ", ".join(["?"] * len(cols))
            await self.execute(
                f"INSERT INTO system_config ({', '.join(cols)}) VALUES ({placeholders})",
                tuple(vals)
            )

    async def update_connection_status(self, name: str, status: str, error: Optional[str] = None) -> None:
        await self.execute(
            "UPDATE system_config SET last_connection_test = ?, last_connection_status = ?, last_connection_error = ? WHERE system_name = ?",
            (datetime.utcnow().isoformat(), status, error, name)
        )
