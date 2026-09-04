import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

class DatabaseManager:
    def __init__(self, db_path: str = "storage.db"):
        self.db_path = db_path
        self._ensure_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
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
            conn.commit()

    def save_assignment(self, item: Dict[str, Any]) -> bool:
        """
        Saves assignment if new. Returns True if inserted (new task), False if already existed.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, status FROM assignments WHERE id = ?", (item["id"],))
            existing = cursor.fetchone()
            if existing:
                return False

            cursor.execute("""
                INSERT INTO assignments (
                    id, portal, course_name, title, description,
                    due_date, difficulty, difficulty_reason, status,
                    suggested_prompt, workspace_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (
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
            ))
            conn.commit()
            return True

    def get_assignment(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assignments WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

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

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(values))
            conn.commit()
            return cursor.rowcount > 0

    def get_all_assignments(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assignments ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assignments WHERE status IN ('DETECTED', 'NOTIFIED') ORDER BY created_at ASC")
            return [dict(row) for row in cursor.fetchall()]

    def get_approved_tasks(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assignments WHERE status = 'APPROVED' ORDER BY updated_at ASC")
            return [dict(row) for row in cursor.fetchall()]

