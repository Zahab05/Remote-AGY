#!/usr/bin/env python3
import os
import sys

# Ensure workspace root is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import time
import yaml
import logging
import argparse
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv(dotenv_path="config/.env")
load_dotenv()

from src.storage.db import DatabaseManager
from src.watcher import get_adapter
from src.analyzer.task_analyzer import TaskAnalyzer
from src.executor.agy_runner import AGYRunner
from src.bot.telegram_bot import TelegramBot
from src.bot.whatsapp_bot import WhatsAppNotifier
from src.bot.notifier_manager import NotifierManager

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("Remote-AGY")

def load_config(config_path: str = "config/config.yaml") -> dict:
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

class RemoteAGYOrchestrator:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = load_config(config_path)
        self.db_path = self.config.get("system", {}).get("db_path", "storage.db")
        self.db = DatabaseManager(self.db_path, config=self.config.get("system", {}))
        
        self.analyzer = TaskAnalyzer(self.config.get("ai_analyzer", {}))
        self.executor = AGYRunner(self.db, self.config.get("executor", {}))
        
        # Inisialisasi Notifiers
        self.notifier = NotifierManager()
        
        # Telegram
        tg_cfg = self.config.get("notifications", {}).get("telegram", {})
        self.tg_bot = TelegramBot(self.db, tg_cfg, agy_runner=self.executor)
        if tg_cfg.get("enabled", True):
            self.notifier.register_notifier(self.tg_bot)
            
        # WhatsApp
        wa_cfg = self.config.get("notifications", {}).get("whatsapp", {})
        self.wa_bot = WhatsAppNotifier(wa_cfg)
        if wa_cfg.get("enabled", False):
            self.notifier.register_notifier(self.wa_bot)
            
        # Adapter SLCM
        portal_cfg = self.config.get("portal", {})
        adapter_name = portal_cfg.get("active_adapter", "ui_satu")
        adapter_opts = portal_cfg.get(adapter_name, {})
        self.watcher = get_adapter(adapter_name, adapter_opts)

    def check_for_new_tasks(self) -> int:
        """
        Memeriksa tugas baru dari portal kampus, menganalisisnya,
        dan mengirimkan notifikasi ke Telegram / WhatsApp jika ada tugas baru.
        """
        logger.info("Memeriksa tugas baru di portal kampus...")
        try:
            tasks = self.watcher.fetch_active_assignments()
        except Exception as e:
            logger.error(f"Gagal mengambil tugas dari portal: {e}")
            return 0

        new_count = 0
        for raw_task in tasks:
            task_dict = raw_task.to_dict()
            task_id = task_dict["id"]
            
            # Cek apakah tugas sudah ada di database
            is_new = self.db.save_assignment(task_dict)
            if not is_new:
                continue

            new_count += 1
            logger.info(f"Tugas baru terdeteksi: [{task_dict.get('course_name')}] {task_dict.get('title')}")

            # Analisis AI: due date, kesulitan, dan prompt panduan
            analysis = self.analyzer.analyze(task_dict)
            self.db.update_status(
                task_id,
                "NOTIFIED",
                difficulty=analysis["difficulty"],
                difficulty_reason=analysis["difficulty_reason"],
                suggested_prompt=analysis["suggested_prompt"]
            )

            # Siapkan payload lengkap untuk alert notifikasi
            alert_payload = {**task_dict, **analysis}
            self.notifier.send_task_alert(alert_payload)

        logger.info(f"Pemeriksaan selesai. {new_count} tugas baru ditemukan.")
        return new_count

    def simulate_mock_task(self):
        """Simulasi memasukkan tugas dummy UI untuk menguji flow end-to-end."""
        from src.watcher.mock_watcher import MockSLCMAdapter
        mock_watcher = MockSLCMAdapter()
        tasks = mock_watcher.fetch_active_assignments()
        if not tasks:
            print("Tidak ada tugas mock.")
            return

        task = tasks[0].to_dict()
        import random
        task["id"] = f"sim-{random.randint(1000, 9999)}"
        print(f"\n[+] Memasukkan tugas simulasi: {task['title']} ({task['course_name']})")
        
        self.db.save_assignment(task)
        analysis = self.analyzer.analyze(task)
        self.db.update_status(
            task["id"],
            "NOTIFIED",
            difficulty=analysis["difficulty"],
            difficulty_reason=analysis["difficulty_reason"],
            suggested_prompt=analysis["suggested_prompt"]
        )
        
        alert_payload = {**task, **analysis}
        print(f"[+] Mengirimkan alert notifikasi ke Telegram / WhatsApp...")
        self.notifier.send_task_alert(alert_payload)
        print(f"[✓] Berhasil! Silakan periksa chat bot Telegram Anda untuk tombol Approval.")

    def run_daemon(self):
        """Menjalankan loop monitoring periodik dan bot listener."""
        poll_interval = self.config.get("system", {}).get("poll_interval_seconds", 900)
        logger.info(f"Memulai Remote-AGY Daemon (interval: {poll_interval}s)...")

        import threading
        def poll_loop():
            # Tunggu 5 detik sebelum polling pertama agar bot sempat terinisialisasi
            time.sleep(5)
            while True:
                try:
                    self.check_for_new_tasks()
                except Exception as e:
                    logger.error(f"Error pada loop polling: {e}")
                time.sleep(poll_interval)

        polling_thread = threading.Thread(target=poll_loop, daemon=True)
        polling_thread.start()

        app = self.tg_bot.build_application()
        if app:
            logger.info("Menjalankan polling Telegram Bot di main thread...")
            app.run_polling()
        else:
            polling_thread.join()

def main():
    parser = argparse.ArgumentParser(description="Remote-AGY: Autonomous Assignment Detector & Executor")
    parser.add_argument("--daemon", action="store_true", help="Jalankan sebagai background service")
    parser.add_argument("--check-now", action="store_true", help="Jalankan pemeriksaan tugas satu kali sekarang")
    parser.add_argument("--simulate-task", action="store_true", help="Simulasikan tugas baru untuk menguji notifikasi dan tombol approve")
    parser.add_argument("--list-tasks", action="store_true", help="Tampilkan daftar tugas yang tersimpan di database")
    parser.add_argument("--approve", type=str, help="Setujui tugas tertentu berdasarkan ID tugas untuk langsung dikerjakan AGY")
    parser.add_argument("--login-ui", action="store_true", help="Lakukan login SSO UI untuk membuat/memperbarui session cookie")
    parser.add_argument("--process-approved", action="store_true", help="Proses dan eksekusi tugas yang berstatus APPROVED di antrean")
    args = parser.parse_args()

    orchestrator = RemoteAGYOrchestrator()

    if args.simulate_task:
        orchestrator.simulate_mock_task()
    elif args.check_now:
        orchestrator.check_for_new_tasks()
    elif args.list_tasks:
        tasks = orchestrator.db.get_all_assignments()
        print(f"\nTotal tugas tersimpan: {len(tasks)}")
        print("-" * 80)
        for t in tasks:
            print(f"[{t['status']:<9}] ID: {t['id']:<15} | {t['difficulty']:<7} | {t['course_name']} - {t['title']}")
        print("-" * 80)
    elif args.process_approved:
        approved = orchestrator.db.get_approved_tasks()
        if not approved:
            print("[*] Tidak ada tugas di antrean APPROVED.")
        for task in approved:
            print(f"[+] Menjalankan tugas antrean: {task['title']}...")
            orchestrator.executor.execute_task(task, callback_notifier=orchestrator.notifier)
    elif args.approve:
        task = orchestrator.db.get_assignment(args.approve)
        if not task:
            print(f"[!] Tugas dengan ID '{args.approve}' tidak ditemukan.")
            sys.exit(1)
        print(f"[+] Memulai pengerjaan tugas {task['title']} via AGY...")
        res = orchestrator.executor.execute_task(task)
        print(f"[✓] Selesai! Status: {'Sukses' if res['success'] else 'Gagal'}")
        print(f"    Folder: {res['task_dir']}")
        print(f"    Zip: {res['zip_path']}")
    elif args.login_ui:
        print("[+] Memulai proses autentikasi SSO UI...")
        success = orchestrator.watcher.login()
        print(f"[✓] Login {'Berhasil' if success else 'Gagal'}")
    elif args.daemon:
        orchestrator.run_daemon()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
