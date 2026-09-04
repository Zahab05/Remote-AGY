from datetime import datetime, timedelta
from typing import List, Optional
from src.watcher.base import BaseSLCMAdapter, AssignmentData

class MockSLCMAdapter(BaseSLCMAdapter):
    """
    Mock Adapter untuk simulasi tugas portal kampus tanpa perlu kredensial langsung.
    Sangat berguna untuk pengujian flow notifikasi, approval, dan eksekusi AGY.
    """
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.logged_in = False
        self._mock_tasks = [
            AssignmentData(
                id="ui-cs-algo-01",
                portal="ui_satu",
                course_name="Perancangan & Analisis Algoritma",
                title="Tugas Pemrograman 1: Shortest Path Optimization",
                description=(
                    "Implementasikan algoritma Dijkstra dan A* Search dalam bahasa Python untuk "
                    "mencari rute terpendek pada graf dengan bobot non-negatif. "
                    "Tugas harus menyertakan unit test, benchmark perbandingan waktu eksekusi kedua algoritma, "
                    "serta dokumentasi singkat dalam format Markdown."
                ),
                due_date=(datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S")
            ),
            AssignmentData(
                id="ui-pweb-02",
                portal="ui_satu",
                course_name="Pemrograman Berbasis Web",
                title="Tugas 2: FastAPI Auth & Product CRUD REST API",
                description=(
                    "Buat backend REST API menggunakan FastAPI (Python) dengan otentikasi JWT. "
                    "Fitur yang dibutuhkan: Register user, Login (token generation), "
                    "dan CRUD item/produk dengan database SQLite. Berikan file test dan requirements.txt."
                ),
                due_date=(datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S")
            )
        ]

    def login(self) -> bool:
        self.logged_in = True
        return True

    def fetch_active_assignments(self) -> List[AssignmentData]:
        return self._mock_tasks

    def fetch_assignment_details(self, task_id: str) -> Optional[AssignmentData]:
        for task in self._mock_tasks:
            if task.id == task_id:
                return task
        return None
