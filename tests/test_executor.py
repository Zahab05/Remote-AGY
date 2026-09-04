import unittest
import os
import shutil
from src.storage.db import DatabaseManager
from src.executor.agy_runner import AGYRunner

class TestAGYRunner(unittest.TestCase):
    def setUp(self):
        self.test_db_path = "test_executor.db"
        self.test_tasks_dir = "test_tasks"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        if os.path.exists(self.test_tasks_dir):
            shutil.rmtree(self.test_tasks_dir)

        self.db = DatabaseManager(self.test_db_path)
        self.runner = AGYRunner(self.db, {"task_storage_dir": self.test_tasks_dir})

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        if os.path.exists(self.test_tasks_dir):
            shutil.rmtree(self.test_tasks_dir)

    def test_dry_run_execution(self):
        task = {
            "id": "dry-run-001",
            "portal": "ui_satu",
            "course_name": "Sistem Operasi",
            "title": "Tugas Threading",
            "description": "Buat simulasi producer-consumer",
            "due_date": "2026-09-15 23:59:00",
            "difficulty": "Medium",
            "suggested_prompt": "Kerjakan simulasi producer-consumer"
        }
        self.db.save_assignment(task)

        result = self.runner.execute_task(task, dry_run=True)
        self.assertTrue(result["success"])
        self.assertEqual(result["task_id"], "dry-run-001")
        self.assertTrue(os.path.exists(result["zip_path"]))

        updated = self.db.get_assignment("dry-run-001")
        self.assertEqual(updated["status"], "COMPLETED")
        self.assertIn("solution.py", result["created_files"])

if __name__ == "__main__":
    unittest.main()
