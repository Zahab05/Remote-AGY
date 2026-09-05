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
        # Provider strategy: "auto" (default: agy lokal -> api key cloud -> heuristic), "agy", "gemini_api", "heuristic"
        if self.config.get("use_gemini") is False:
            self.provider = "heuristic"
        else:
            self.provider = self.config.get("provider", "auto")

        self.agy_model = self.config.get("agy_model", "gemini-3.7-flash-medium")
        self.api_model = self.config.get("api_model", self.config.get("model_name", "gemini-flash-latest"))

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

        # Multi-engine analyzer pipeline
        analysis_result = None

        # 1. Coba via Antigravity CLI lokal jika diizinkan
        if self.provider in ["auto", "agy"]:
            analysis_result = self._analyze_with_agy(course, title, desc, due_date_str)

        # 2. Coba via Cloud Gemini REST API jika agy tidak tersedia atau gagal
        if not analysis_result and self.provider in ["auto", "gemini_api"]:
            analysis_result = self._analyze_with_gemini_api(course, title, desc, due_date_str)

        # 3. Fallback ke heuristik berbasis aturan jika offline / tanpa AI
        if not analysis_result:
            analysis_result = self._heuristic_analysis(course, title, desc)

        # Siapkan prompt kerja untuk AGY
        prompt = self._generate_agy_prompt(
            course=course,
            title=title,
            desc=desc,
            difficulty=analysis_result["difficulty"],
            recommendation=analysis_result.get("recommendations", "")
        )

        return {
            "course_name": course,
            "title": title,
            "due_date_display": formatted_due_date,
            "remaining_time": remaining_time,
            "difficulty": analysis_result["difficulty"],
            "difficulty_reason": analysis_result["reason"],
            "estimated_hours": analysis_result.get("estimated_hours", 2),
            "recommendations": analysis_result.get("recommendations", ""),
            "suggested_prompt": prompt,
            "engine": analysis_result.get("engine", "heuristic")
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
                "recommendations": "Pecah menjadi modularitas terpisah, sertakan arsitektur diagram dan validasi menyeluruh.",
                "engine": "heuristic"
            }
        elif any(p in text for p in medium_patterns):
            return {
                "difficulty": "Medium",
                "reason": "Tugas memerlukan implementasi logika fungsional, manipulasi data, atau pengujian terstruktur.",
                "estimated_hours": 2,
                "recommendations": "Sediakan file kode modular, requirements/dependency list, dan unit test fungsional.",
                "engine": "heuristic"
            }
        else:
            return {
                "difficulty": "Easy",
                "reason": "Tugas bersifat pemahaman konsep, rangkuman, atau implementasi kode sederhana.",
                "estimated_hours": 1,
                "recommendations": "Sediakan penjelasan ringkas, terstruktur, dan langsung pada poin utama.",
                "engine": "heuristic"
            }

    def _analyze_with_agy(self, course: str, title: str, desc: str, due_date: str) -> Optional[Dict[str, Any]]:
        """
        Memanggil agy CLI secara headless untuk menganalisis tugas menggunakan model Antigravity
        (misal gemini-3.7-flash-medium atau gemini-3.6-flash-high) tanpa butuh API key terpisah.
        """
        import shutil
        import subprocess

        agy_path = shutil.which("agy")
        if not agy_path:
            return None

        prompt = (
            f"Analisis tugas kuliah berikut secara ringkas:\n"
            f"Mata Kuliah: {course}\n"
            f"Judul: {title}\n"
            f"Deskripsi: {desc}\n"
            f"Deadline: {due_date}\n\n"
            f"Kembalikan HANYA format JSON valid tanpa narasi lain di luar JSON:\n"
            f'{{"difficulty": "Easy"|"Medium"|"Hard", "reason": "<alasan 1 kalimat>", "estimated_hours": <angka>, "recommendations": "<saran teknis implementasi>"}}'
        )

        try:
            logger.info(f"Menganalisis tugas via AGY CLI lokal (Model: {self.agy_model})...")
            cmd = [agy_path, "-p", prompt, "--model", self.agy_model]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=45,
                encoding="utf-8",
                errors="replace"
            )
            if result.returncode == 0 and result.stdout:
                parsed = self._extract_json(result.stdout)
                if parsed:
                    parsed["engine"] = f"agy ({self.agy_model})"
                    return parsed
            else:
                logger.warning(f"AGY analyzer error code {result.returncode}: {result.stderr.strip()[:200]}")
        except Exception as e:
            logger.warning(f"Gagal menjalankan analisis via AGY: {e}")

        return None

    def _analyze_with_gemini_api(self, course: str, title: str, desc: str, due_date: str) -> Optional[Dict[str, Any]]:
        """
        Memanggil Google AI Studio / Gemini REST API jika GEMINI_API_KEY tersedia.
        Cocok untuk lingkungan Cloud (GitHub Actions) di mana agy CLI tidak terpasang.
        """
        if not self.api_key:
            return None

        import httpx
        models_to_try = [self.api_model]
        if "gemini-3.6-flash" not in models_to_try:
            models_to_try.append("gemini-3.6-flash")

        prompt_content = f"""
        Anda adalah asisten akademik. Analisis tugas kuliah berikut:
        Mata Kuliah: {course}
        Judul: {title}
        Deskripsi: {desc}
        Deadline: {due_date}

        Kembalikan HANYA JSON valid:
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

        for model in models_to_try:
            try:
                logger.info(f"Menganalisis tugas via Cloud Gemini API (Model: {model})...")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                headers = {
                    "Content-Type": "application/json",
                    "X-goog-api-key": self.api_key
                }
                res = httpx.post(url, headers=headers, json=payload, timeout=20.0)
                if res.status_code == 200:
                    data = res.json()
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = self._extract_json(text)
                    if parsed:
                        parsed["engine"] = f"cloud_api ({model})"
                        return parsed
                elif res.status_code in [503, 429]:
                    logger.warning(f"Model {model} sedang padat ({res.status_code}), mencoba model alternatif...")
                    continue
                else:
                    logger.warning(f"Gemini API ({model}) status {res.status_code}: {res.text[:200]}")
            except Exception as e:
                logger.warning(f"Gagal memanggil Gemini API ({model}): {e}")

        return None

    def _extract_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """
        Mengekstrak dan memvalidasi objek JSON dari respon teks mentah LLM.
        """
        if not raw_text:
            return None

        clean_text = raw_text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text)
        candidate = match.group(1).strip() if match else clean_text

        if not candidate.startswith("{"):
            start = candidate.find("{")
            end = candidate.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = candidate[start:end+1]

        try:
            data = json.loads(candidate)
            if "difficulty" in data and "reason" in data:
                diff = str(data["difficulty"]).strip().capitalize()
                if diff not in ["Easy", "Medium", "Hard"]:
                    diff = "Medium"
                data["difficulty"] = diff

                # Jika recommendations berupa list, gabungkan menjadi string rapi
                recs = data.get("recommendations", "")
                if isinstance(recs, list):
                    data["recommendations"] = "; ".join(str(r) for r in recs)
                elif not isinstance(recs, str):
                    data["recommendations"] = str(recs)

                # Pastikan estimated_hours berupa float/int
                try:
                    data["estimated_hours"] = float(data.get("estimated_hours", 2))
                except (ValueError, TypeError):
                    data["estimated_hours"] = 2.0

                return data
        except Exception as e:
            logger.warning(f"Gagal mem-parse JSON hasil LLM: {e}. Output mentah: {clean_text[:150]}")

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
