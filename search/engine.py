"""Search engine — indexes events from all domains and supports natural language queries.

Uses SQLite FTS5 for full-text search of events, with AI-powered natural
language query translation via the configured AI provider.
"""

import json
import sqlite3
import time
from pathlib import Path

SEARCH_DB = Path(__file__).parent.parent / ".search.db"


def _get_db() -> sqlite3.Connection:
    """Get or create search database with FTS5."""
    db = sqlite3.connect(str(SEARCH_DB))
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            timestamp REAL,
            domain TEXT,
            event_type TEXT,
            source TEXT,
            camera_id TEXT,
            track_id TEXT,
            person_name TEXT,
            description TEXT,
            severity TEXT,
            confidence REAL,
            data TEXT,
            indexed_at REAL
        )
    """)
    # FTS5 virtual table for full-text search
    db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
            event_id, domain, event_type, person_name, description, severity,
            content='events',
            content_rowid='rowid'
        )
    """)
    # Triggers to keep FTS in sync
    db.executescript("""
        CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
            INSERT INTO events_fts(rowid, event_id, domain, event_type, person_name, description, severity)
            VALUES (new.rowid, new.event_id, new.domain, new.event_type, new.person_name, new.description, new.severity);
        END;
        CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
            INSERT INTO events_fts(events_fts, rowid, event_id, domain, event_type, person_name, description, severity)
            VALUES ('delete', old.rowid, old.event_id, old.domain, old.event_type, old.person_name, old.description, old.severity);
        END;
    """)
    db.commit()
    return db


def index_event(event: dict):
    """Index a single event for search."""
    db = _get_db()
    try:
        db.execute("""
            INSERT OR REPLACE INTO events
            (event_id, timestamp, domain, event_type, source, camera_id,
             track_id, person_name, description, severity, confidence, data, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.get("event_id", f"evt_{int(time.time() * 1000)}"),
            event.get("timestamp", time.time()),
            event.get("domain", ""),
            event.get("event_type", event.get("type", "")),
            event.get("source", ""),
            event.get("camera_id", ""),
            event.get("track_id", ""),
            event.get("person_name", event.get("name", "")),
            event.get("description", ""),
            event.get("severity", ""),
            event.get("confidence", 0),
            json.dumps(event.get("data", {})),
            time.time(),
        ))
        db.commit()
    finally:
        db.close()


def index_events(events: list[dict]):
    """Index multiple events."""
    for event in events:
        index_event(event)


def search_text(query: str, domain: str = "", limit: int = 50) -> list[dict]:
    """Full-text search across all indexed events."""
    db = _get_db()
    try:
        # FTS5 search
        if domain:
            rows = db.execute("""
                SELECT e.* FROM events e
                JOIN events_fts f ON e.rowid = f.rowid
                WHERE events_fts MATCH ? AND e.domain = ?
                ORDER BY e.timestamp DESC LIMIT ?
            """, (query, domain, limit)).fetchall()
        else:
            rows = db.execute("""
                SELECT e.* FROM events e
                JOIN events_fts f ON e.rowid = f.rowid
                WHERE events_fts MATCH ?
                ORDER BY e.timestamp DESC LIMIT ?
            """, (query, limit)).fetchall()

        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        # Fallback to LIKE search if FTS query is invalid
        like = f"%{query}%"
        if domain:
            rows = db.execute("""
                SELECT * FROM events
                WHERE (description LIKE ? OR event_type LIKE ? OR person_name LIKE ?) AND domain = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (like, like, like, domain, limit)).fetchall()
        else:
            rows = db.execute("""
                SELECT * FROM events
                WHERE description LIKE ? OR event_type LIKE ? OR person_name LIKE ?
                ORDER BY timestamp DESC LIMIT ?
            """, (like, like, like, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def search_by_time(start: float, end: float, domain: str = "", limit: int = 200) -> list[dict]:
    """Search events within a time range."""
    db = _get_db()
    try:
        if domain:
            rows = db.execute("""
                SELECT * FROM events WHERE timestamp BETWEEN ? AND ? AND domain = ?
                ORDER BY timestamp ASC LIMIT ?
            """, (start, end, domain, limit)).fetchall()
        else:
            rows = db.execute("""
                SELECT * FROM events WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC LIMIT ?
            """, (start, end, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def search_by_person(name: str, limit: int = 50) -> list[dict]:
    """Search events associated with a specific person."""
    db = _get_db()
    try:
        rows = db.execute("""
            SELECT * FROM events WHERE person_name LIKE ?
            ORDER BY timestamp DESC LIMIT ?
        """, (f"%{name}%", limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def search_by_type(event_type: str, domain: str = "", limit: int = 50) -> list[dict]:
    """Search events by type."""
    db = _get_db()
    try:
        if domain:
            rows = db.execute("""
                SELECT * FROM events WHERE event_type = ? AND domain = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (event_type, domain, limit)).fetchall()
        else:
            rows = db.execute("""
                SELECT * FROM events WHERE event_type = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (event_type, limit)).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def get_event_stats(domain: str = "") -> dict:
    """Get summary statistics of indexed events."""
    db = _get_db()
    try:
        if domain:
            total = db.execute("SELECT COUNT(*) FROM events WHERE domain = ?", (domain,)).fetchone()[0]
            types = db.execute("""
                SELECT event_type, COUNT(*) as cnt FROM events WHERE domain = ?
                GROUP BY event_type ORDER BY cnt DESC
            """, (domain,)).fetchall()
        else:
            total = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            types = db.execute("""
                SELECT event_type, COUNT(*) as cnt FROM events
                GROUP BY event_type ORDER BY cnt DESC
            """).fetchall()

        domains = db.execute("""
            SELECT domain, COUNT(*) as cnt FROM events
            GROUP BY domain ORDER BY cnt DESC
        """).fetchall()

        return {
            "total_events": total,
            "by_type": {row["event_type"]: row["cnt"] for row in types},
            "by_domain": {row["domain"]: row["cnt"] for row in domains},
        }
    finally:
        db.close()


def natural_language_to_query(nl_query: str) -> dict:
    """Parse a natural language query into structured search parameters.

    Handles queries like:
    - "show me everyone near the register at 3pm" → person search + time filter
    - "find all falls today" → type=possible_fall + time=today
    - "loitering events in the last hour" → type=loitering + time range
    """
    query = nl_query.lower().strip()
    result = {"text": "", "event_type": "", "domain": "", "person": ""}

    # Event type mapping
    type_keywords = {
        "fall": "possible_fall",
        "fell": "possible_fall",
        "loiter": "loitering",
        "crowd": "crowd_forming",
        "run": "rapid_movement",
        "running": "rapid_movement",
        "tailgat": "possible_tailgating",
        "void": "void",
        "refund": "high_refund",
        "still": "sustained_stillness",
        "flap": "possible_hand_flapping",
        "rock": "possible_body_rocking",
        "repetiti": "repetitive_movement",
    }

    for keyword, etype in type_keywords.items():
        if keyword in query:
            result["event_type"] = etype
            break

    # Domain mapping
    domain_keywords = {
        "aba": "aba", "therapy": "aba", "session": "aba", "behavior": "aba",
        "retail": "retail", "store": "retail", "shop": "retail", "traffic": "retail",
        "security": "security", "safety": "security", "alert": "security",
    }

    for keyword, domain in domain_keywords.items():
        if keyword in query:
            result["domain"] = domain
            break

    # Person name extraction (basic — after "person" or "find")
    for prefix in ["person ", "find ", "show me ", "who is "]:
        if prefix in query:
            after = query.split(prefix, 1)[1].strip()
            result["person"] = after.split()[0] if after else ""
            break

    # Default to full-text search
    result["text"] = nl_query

    return result
