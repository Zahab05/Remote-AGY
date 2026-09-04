import os
import subprocess
import shutil
import zipfile
import logging
import time
from typing import Dict, Any, Optional
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)

class AGYRunner:
    """
    Eksekutor otonom untuk Antigravity CLI (agy) dalam mode Headless Background Runner.
    """
    def __init__(self, db: DatabaseManager, config: Optional[dict] = None):
        self.db = db
        self.config = config or {}
        self.base_tasks_dir = self.config.get("task_storage_dir", "tasks")
        self.agy_bin = self.config.get("agy_binary", "agy")
        self.timeout = self.config.get("timeout_seconds", 1800)
        self.dangerously_skip = self.config.get("dangerously_skip_permissions", True)
        os.makedirs(self.base_tasks_dir, exist_ok=True)

    def execute_task(self, task: Dict[str, Any], callback_notifier=None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Mengeksekusi pengerjaan tugas oleh AGY secara headless.
        """
        task_id = task["id"]
        task_dir = os.path.abspath(os.path.join(self.base_tasks_dir, task_id))
        os.makedirs(task_dir, exist_ok=True)

        # Update status di database menjadi RUNNING
        self.db.update_status(task_id, "RUNNING", workspace_path=task_dir)

        # Buat file INSTRUCTIONS.md di workspace tugas
        instructions_path = os.path.join(task_dir, "INSTRUCTIONS.md")
        with open(instructions_path, "w", encoding="utf-8") as f:
            f.write(f"# {task.get('title', 'Tugas Kuliah')}\n\n")
            f.write(f"**Mata Kuliah**: {task.get('course_name', '-')}\n")
            f.write(f"**Batas Waktu**: {task.get('due_date', '-')}\n")
            f.write(f"**Tingkat Kesulitan**: {task.get('difficulty', 'Unknown')}\n\n")
            f.write("## Deskripsi & Instruksi Dosen:\n")
            f.write(f"{task.get('description', '')}\n\n")
            f.write("## Prompt Panduan Pengerjaan:\n")
            f.write(f"{task.get('suggested_prompt', '')}\n")

        if callback_notifier:
            try:
                callback_notifier.notify_progress(task, f"🚀 AGY mulai mengerjakan tugas di folder:\n`{task_dir}`")
            except Exception as ne:
                logger.warning(f"Gagal mengirim notifikasi progres: {ne}")

        log_path = os.path.join(task_dir, "agy_run.log")
        start_time = time.time()

        if dry_run:
            # Mode simulasi untuk pengujian unit / integrasi
            with open(os.path.join(task_dir, "solution.py"), "w") as f:
                f.write("# Solusi otomatis dari AGY Runner (Dry Run)\nprint('Tugas selesai')\n")
            with open(os.path.join(task_dir, "README.md"), "w") as f:
                f.write("# Panduan Tugas\nSelesai dijalankan dengan sukses.")
            with open(log_path, "w") as f:
                f.write("DRY RUN: Tugas disimulasikan selesai dengan status sukses.")
            success = True
            stdout_text = "DRY RUN COMPLETE"
        else:
            prompt = (
                f"Buka dan baca instruksi di berkas {instructions_path}. "
                f"Kerjakan seluruh tugas tersebut secara tuntas dan simpan semua kode serta hasil dokumen langsung di dalam folder {task_dir}. "
                f"Pastikan semua kode bebas error dan siap dinilai."
            )
            cmd = [self.agy_bin, "-p", prompt]
            if self.dangerously_skip:
                cmd.append("--dangerously-skip-permissions")

            logger.info(f"Menjalankan AGY di {task_dir}: {' '.join(cmd)}")
            try:
                with open(log_path, "w", encoding="utf-8") as log_file:
                    proc = subprocess.Popen(
                        cmd,
                        cwd=task_dir,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    proc.wait(timeout=self.timeout)
                    success = (proc.returncode == 0)
                with open(log_path, "r", encoding="utf-8", errors="ignore") as log_file:
                    stdout_text = log_file.read()
            except subprocess.TimeoutExpired:
                logger.error(f"Pengerjaan tugas {task_id} melebihi batas waktu {self.timeout} detik.")
                proc.kill()
                success = False
                stdout_text = f"TIMEOUT: Eksekusi melebihi {self.timeout} detik."
            except Exception as e:
                logger.error(f"Gagal menjalankan AGY: {e}")
                success = False
                stdout_text = str(e)

        elapsed_time = round(time.time() - start_time, 1)

        # Kompres hasil kerja menjadi zip
        zip_path = os.path.join(task_dir, f"{task_id}_result.zip")
        self._create_artifact_zip(task_dir, zip_path)

        # Daftar berkas yang dihasilkan
        created_files = [
            f for f in os.listdir(task_dir)
            if f not in ["INSTRUCTIONS.md", "agy_run.log", f"{task_id}_result.zip"]
        ]

        summary = (
            f"✅ *Pengerjaan Tugas Selesai!*\n"
            f"⏱ Durasi: {elapsed_time} detik\n"
            f"📂 Berkas Dihasilkan: {', '.join(created_files) if created_files else 'Tidak ada berkas tambahan'}\n"
            f"💾 Arsip: `{zip_path}`"
        )

        final_status = "COMPLETED" if success else "FAILED"
        self.db.update_status(
            task_id,
            final_status,
            result_summary=summary,
            artifacts_path=zip_path
        )

        result_payload = {
            "success": success,
            "task_id": task_id,
            "task_dir": task_dir,
            "zip_path": zip_path,
            "created_files": created_files,
            "summary": summary,
            "elapsed_time": elapsed_time,
            "log_snippet": stdout_text[-500:] if stdout_text else ""
        }

        if callback_notifier:
            try:
                callback_notifier.notify_completed(task, result_payload)
            except Exception as ne:
                logger.warning(f"Gagal mengirim notifikasi penyelesaian: {ne}")

        return result_payload

    def _create_artifact_zip(self, source_dir: str, output_zip: str):
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(source_dir):
                for file in files:
                    if file.endswith((".zip", ".log")):
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, source_dir)
                    zipf.write(full_path, rel_path)
