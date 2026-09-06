import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manajer basis data tugas Remote-AGY dengan arsitektur Dual-Mode:
    1. Mode Cloud: Turso (libSQL over HTTP) untuk sinkronisasi instan 24/7 antara GitHub Actions & Laptop.
    2. Mode Lokal: SQLite (storage.db) jika offline atau kredensial Turso tidak diatur.
    """
    def __init__(self, db_path: str = "storage.db", config: Optional[dict] = None):
        self.db_path = db_path
        self.config = config or {}

        turso_cfg = self.config.get("turso", {})
        self.turso_url = os.environ.get("TURSO_DATABASE_URL") or turso_cfg.get("database_url", "")
        self.turso_token = os.environ.get("TURSO_AUTH_TOKEN") or turso_cfg.get("auth_token", "")

        self.is_cloud = False
        self.libsql_client = None

        if self.turso_url:
            try:
                import libsql_client
                url = self.turso_url
                if url.startswith("libsql://"):
                    url = "https://" + url[len("libsql://"):]
                self.libsql_client = libsql_client.create_client_sync(url, auth_token=self.turso_token)
                self.is_cloud = True
                logger.info(f"Basis data terhubung ke Turso Cloud: {url}")
            except Exception as e:
                logger.warning(f"Gagal menghubungkan ke Turso Cloud ({e}). Beralih ke SQLite lokal: {self.db_path}")
                self.is_cloud = False
                self.libsql_client = None

        self._ensure_db()

    @contextmanager
    def _get_local_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _execute(self, sql: str, params: tuple = ()) -> int:
        if self.is_cloud and self.libsql_client:
            res = self.libsql_client.execute(sql, list(params))
            return res.rows_affected

        with self._get_local_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount

    def _fetch_one(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        if self.is_cloud and self.libsql_client:
            res = self.libsql_client.execute(sql, list(params))
            if res.rows:
                return dict(zip(res.columns, res.rows[0]))
            return None

        with self._get_local_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def _fetch_all(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        if self.is_cloud and self.libsql_client:
            res = self.libsql_client.execute(sql, list(params))
            cols = res.columns
            return [dict(zip(cols, row)) for row in res.rows]

        with self._get_local_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]

    def _ensure_db(self):
        self._execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id TEXT PRIMARY KEY,
                portal TEXT NOT NULL,
                course_name TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT,
                difficulty TEXT DEFAULT 'Unknown',
                difficulty_reason TEXT,
                status TEXT DEFAULT 'DETECTED',
                suggested_prompt TEXT,
                workspace_path TEXT,
                result_summary TEXT,
                artifacts_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def close(self):
        if self.libsql_client:
            try:
                self.libsql_client.close()
            except Exception:
                pass

    def __del__(self):
        self.close()

    def save_assignment(self, item: Dict[str, Any]) -> bool:
        """
        Saves assignment if new. Returns True if inserted (new task), False if already existed.
        """
        existing = self._fetch_one("SELECT id, status FROM assignments WHERE id = ?", (item["id"],))
        if existing:
            return False

        sql = """
            INSERT INTO assignments (
                id, portal, course_name, title, description,
                due_date, difficulty, difficulty_reason, status,
                suggested_prompt, workspace_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """
        params = (
            item["id"],
            item.get("portal", "unknown"),
            item["course_name"],
            item["title"],
            item.get("description", ""),
            item.get("due_date", ""),
            item.get("difficulty", "Unknown"),
            item.get("difficulty_reason", ""),
            item.get("status", "DETECTED"),
            item.get("suggested_prompt", ""),
            item.get("workspace_path", "")
        )
        self._execute(sql, params)
        return True

    def get_assignment(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._fetch_one("SELECT * FROM assignments WHERE id = ?", (task_id,))

    def update_status(self, task_id: str, status: str, **kwargs) -> bool:
        allowed_fields = [
            "difficulty", "difficulty_reason", "suggested_prompt",
            "workspace_path", "result_summary", "artifacts_path"
        ]
        updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
        values = [status]

        for k, v in kwargs.items():
            if k in allowed_fields:
                updates.append(f"{k} = ?")
                values.append(v)

        values.append(task_id)
        query = f"UPDATE assignments SET {', '.join(updates)} WHERE id = ?"
        rows_affected = self._execute(query, tuple(values))
        return rows_affected > 0

    def get_all_assignments(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT * FROM assignments ORDER BY created_at DESC LIMIT ?", (limit,))

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT * FROM assignments WHERE status IN ('DETECTED', 'NOTIFIED') ORDER BY created_at ASC")

    def get_approved_tasks(self) -> List[Dict[str, Any]]:
        return self._fetch_all("SELECT * FROM assignments WHERE status = 'APPROVED' ORDER BY updated_at ASC")

