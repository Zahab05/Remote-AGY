import unittest
from datetime import datetime, timedelta
from src.analyzer.task_analyzer import TaskAnalyzer

class TestTaskAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = TaskAnalyzer({"use_gemini": False})

    def test_heuristic_difficulty_medium(self):
        raw_task = {
            "course_name": "Pemrograman Berbasis Web",
            "title": "Tugas 2: FastAPI Auth & Product CRUD REST API",
            "description": "Buat REST API menggunakan FastAPI dengan otentikasi JWT dan database SQLite.",
            "due_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        }
        res = self.analyzer.analyze(raw_task)
        self.assertEqual(res["difficulty"], "Medium")
        self.assertTrue("Sisa 2 hari" in res["remaining_time"] or "Sisa 3 hari" in res["remaining_time"])
        self.assertIn("TUGAS AKADEMIK: Pemrograman Berbasis Web", res["suggested_prompt"])

    def test_heuristic_difficulty_easy(self):
        raw_task = {
            "course_name": "Etika Profesi",
            "title": "Kuis 1: Etika Rekayasa Perangkat Lunak",
            "description": "Jawab 10 soal pilihan ganda mengenai kode etik ACM/IEEE.",
            "due_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        }
        res = self.analyzer.analyze(raw_task)
        self.assertEqual(res["difficulty"], "Easy")

    def test_heuristic_difficulty_hard(self):
        raw_task = {
            "course_name": "Pembelajaran Mesin Lanjut",
            "title": "Proyek Akhir: Deep Learning Microservices Pipeline",
            "description": "Bangun distributed pipeline machine learning dengan docker-compose.",
            "due_date": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        }
        res = self.analyzer.analyze(raw_task)
        self.assertEqual(res["difficulty"], "Hard")

if __name__ == "__main__":
    unittest.main()
