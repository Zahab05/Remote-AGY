import unittest
import os
from src.storage.db import DatabaseManager

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_storage.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.db = DatabaseManager(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_save_and_get(self):
        item = {
            "id": "task-001",
            "portal": "ui_satu",
            "course_name": "Struktur Data",
            "title": "Tugas 1: Binary Search Tree",
            "description": "Implementasikan BST dalam Python",
            "due_date": "2026-09-10 23:59:00"
        }
        # First save should be True (new task)
        self.assertTrue(self.db.save_assignment(item))
        # Second save with same ID should be False (duplicate prevention)
        self.assertFalse(self.db.save_assignment(item))

        retrieved = self.db.get_assignment("task-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["course_name"], "Struktur Data")
        self.assertEqual(retrieved["status"], "DETECTED")

    def test_update_status(self):
        item = {
            "id": "task-002",
            "portal": "ui_satu",
            "course_name": "Basis Data",
            "title": "Tugas ERD",
            "description": "Rancang ERD Toko Buku",
            "due_date": "2026-09-12 23:59:00"
        }
        self.db.save_assignment(item)
        self.db.update_status("task-002", "APPROVED", difficulty="Easy", difficulty_reason="Desain ERD standar")

        updated = self.db.get_assignment("task-002")
        self.assertEqual(updated["status"], "APPROVED")
        self.assertEqual(updated["difficulty"], "Easy")
        self.assertEqual(updated["difficulty_reason"], "Desain ERD standar")

if __name__ == "__main__":
    unittest.main()
