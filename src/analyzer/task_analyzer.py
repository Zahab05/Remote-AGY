import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TaskAnalyzer:
    """
    Menganalisis tugas akademik: mengekstrak due date terstruktur,
    menilai tingkat kesulitan (Easy, Medium, Hard),
    serta merumuskan prompt eksekusi untuk AGY CLI.
    """
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.api_key = os.environ.get("GEMINI_API_KEY") or self.config.get("api_key", "")
        self.use_gemini = self.config.get("use_gemini", True) and bool(self.api_key)

    def analyze(self, raw_task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Menganalisis tugas dan menghasilkan metadata lengkap.
        """
        title = raw_task.get("title", "")
        course = raw_task.get("course_name", "")
        desc = raw_task.get("description", "")
        due_date_str = raw_task.get("due_date", "")

        # Format due date & hitung sisa waktu
        formatted_due_date, remaining_time = self._format_deadline(due_date_str)

        # Coba analisis via LLM jika API key tersedia
        analysis_result = None
        if self.use_gemini:
            analysis_result = self._analyze_with_llm(course, title, desc, due_date_str)

        if not analysis_result:
            analysis_result = self._heuristic_analysis(course, title, desc)

        # Siapkan prompt kerja untuk AGY
        prompt = self._generate_agy_prompt(
            course=course,
            title=title,
            desc=desc,
            difficulty=analysis_result["difficulty"],
            recommendation=analysis_result["recommendations"]
        )

        return {
            "course_name": course,
            "title": title,
            "due_date_display": formatted_due_date,
            "remaining_time": remaining_time,
            "difficulty": analysis_result["difficulty"],
            "difficulty_reason": analysis_result["reason"],
            "estimated_hours": analysis_result.get("estimated_hours", 2),
            "suggested_prompt": prompt
        }

    def _format_deadline(self, due_date_str: str) -> tuple[str, str]:
        if not due_date_str:
            return "Tidak ada batas waktu", "N/A"

        # Coba parse beberapa format umum
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M", "%Y-%m-%d"]:
            try:
                dt = datetime.strptime(due_date_str.strip(), fmt)
                now = datetime.now()
                delta = dt - now
                
                formatted = dt.strftime("%d %B %Y, %H:%M WIB")
                if delta.total_seconds() < 0:
                    remaining = "⚠️ Sudah Lewat Deadline!"
                else:
                    days = delta.days
                    hours = delta.seconds // 3600
                    if days > 0:
                        remaining = f"Sisa {days} hari {hours} jam"
                    else:
                        remaining = f"Sisa {hours} jam (Segera!)"
                return formatted, remaining
            except ValueError:
                continue

        # Jika format teks mentah dari Moodle (misal: "Sabtu, 12 September 2026, 23:59")
        return due_date_str, "Lihat tanggal"

    def _heuristic_analysis(self, course: str, title: str, desc: str) -> Dict[str, Any]:
        """
        Analisis berbasis aturan / kata kunci jika tanpa LLM API key.
        """
        text = f"{course} {title} {desc}".lower()

        # Pola kata kunci untuk Hard
        hard_patterns = [
            "fullstack", "microservice", "machine learning", "deep learning", "neural network",
            "skripsi", "tugas akhir", "distributed system", "compiler", "proyek akhir",
            "multi-tier", "high performance", "pipeline", "docker-compose", "kubernetes"
        ]

        # Pola kata kunci untuk Medium
        medium_patterns = [
            "rest api", "crud", "database", "sqlite", "postgresql", "mysql", "erd",
            "dijkstra", "a* search", "binary search tree", "graph", "sorting", "algorithm",
            "algoritma", "oop", "gui", "swing", "fastapi", "flask", "express", "unit test",
            "analisis kasus", "makalah", "paper", "laporan praktikum"
        ]

        # Pola kata kunci untuk Easy
        easy_patterns = [
            "kuis", "quiz", "pilihan ganda", "multiple choice", "rangkuman", "summary",
            "review artikel", "ulasan singkat", "resume", "diskusi forum", "essay 1 halaman"
        ]

        if any(p in text for p in hard_patterns):
            return {
                "difficulty": "Hard",
                "reason": "Tugas mencakup arsitektur kompleks, banyak komponen, atau algoritma tingkat lanjut.",
                "estimated_hours": 6,
                "recommendations": "Pecah menjadi modularitas terpisah, sertakan arsitektur diagram dan validasi menyeluruh."
            }
        elif any(p in text for p in medium_patterns):
            return {
                "difficulty": "Medium",
                "reason": "Tugas memerlukan implementasi logika fungsional, manipulasi data, atau pengujian terstruktur.",
                "estimated_hours": 2,
                "recommendations": "Sediakan file kode modular, requirements/dependency list, dan unit test fungsional."
            }
        else:
            return {
                "difficulty": "Easy",
                "reason": "Tugas bersifat pemahaman konsep, rangkuman, atau implementasi kode sederhana.",
                "estimated_hours": 1,
                "recommendations": "Sediakan penjelasan ringkas, terstruktur, dan langsung pada poin utama."
            }

    def _analyze_with_llm(self, course: str, title: str, desc: str, due_date: str) -> Optional[Dict[str, Any]]:
        """
        Memanggil Gemini API jika API Key tersedia.
        """
        try:
            import httpx
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.get('model_name', 'gemini-2.0-flash')}:generateContent?key={self.api_key}"
            prompt_content = f"""
            Anda adalah asisten akademik. Analisis tugas kuliah berikut:
            Mata Kuliah: {course}
            Judul: {title}
            Deskripsi: {desc}
            Deadline: {due_date}

            Kembalikan HANYA JSON valid (tanpa markdown fences):
            {{
                "difficulty": "Easy" | "Medium" | "Hard",
                "reason": "<alasan singkat dalam 1 kalimat>",
                "estimated_hours": <angka estimasi jam kerja>,
                "recommendations": "<saran implementasi teknis>"
            }}
            """
            payload = {
                "contents": [{"parts": [{"text": prompt_content}]}],
                "generationConfig": {"response_mime_type": "application/json"}
            }
            res = httpx.post(url, json=payload, timeout=15.0)
            if res.status_code == 200:
                data = res.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
        except Exception as e:
            logger.warning(f"Gagal memanggil Gemini API: {e}. Menggunakan analisis heuristik.")
        return None

    def _generate_agy_prompt(self, course: str, title: str, desc: str, difficulty: str, recommendation: str) -> str:
        return (
            f"TUGAS AKADEMIK: {course} - {title}\n"
            f"Tingkat Kesulitan: {difficulty}\n\n"
            f"INSTRUKSI TUGAS:\n{desc}\n\n"
            f"PANDUAN PENGERJAAN UNTUK AGY:\n"
            f"1. Kerjakan tugas ini secara mandiri, lengkap, dan siap dikumpulkan.\n"
            f"2. Buat kode program yang modular, bersih, dengan dokumentasi kode (docstrings & comments).\n"
            f"3. Buat file README.md yang menjelaskan cara menjalankan program, dependensi yang dibutuhkan, dan penjelasan singkat arsitektur.\n"
            f"4. Sediakan file pengujian (unit test) untuk memastikan seluruh fungsionalitas berjalan lancar tanpa error.\n"
            f"Catatan Tambahan: {recommendation}"
        )
