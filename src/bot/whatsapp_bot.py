import logging
import httpx
from typing import Dict, Any, Optional
from src.bot.notifier_manager import BaseNotifier

logger = logging.getLogger(__name__)

class WhatsAppNotifier(BaseNotifier):
    """
    Adapter notifikasi WhatsApp via HTTP Gateway (Fonnte, Wablas, atau generic webhook).
    """
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", False)
        self.api_url = self.config.get("api_url", "")
        self.api_token = self.config.get("api_token", "")
        self.target_phone = self.config.get("target_phone", "")

    def send_task_alert(self, task: Dict[str, Any]) -> bool:
        if not self.enabled or not self.api_url or not self.target_phone:
            return False

        message = (
            f"🚨 *TUGAS BARU TERDETEKSI DI SLCM* 🚨\n\n"
            f"📚 *Mata Kuliah*: {task.get('course_name', '-')}\n"
            f"📝 *Tugas*: {task.get('title', '-')}\n"
            f"⏰ *Deadline*: {task.get('due_date', '-')}\n"
            f"⚡ *Tingkat Kesulitan*: {task.get('difficulty', 'Unknown')}\n"
            f"💡 *Alasan*: {task.get('difficulty_reason', '-')}\n\n"
            f"Balas dengan pesan berikut untuk mengeksekusi:\n"
            f"`!approve {task.get('id')}`"
        )
        return self._send_http(message)

    def notify_progress(self, task: Dict[str, Any], message: str) -> bool:
        if not self.enabled:
            return False
        return self._send_http(f"⏳ *Progres Tugas {task.get('title')}*\n{message}")

    def notify_completed(self, task: Dict[str, Any], result: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        msg = f"🎉 *Tugas Selesai Dikerjakan AGY*\n{result.get('summary', '')}"
        return self._send_http(msg)

    def _send_http(self, text: str) -> bool:
        try:
            headers = {}
            if self.api_token:
                headers["Authorization"] = self.api_token

            payload = {
                "target": self.target_phone,
                "message": text
            }
            res = httpx.post(self.api_url, json=payload, headers=headers, timeout=10.0)
            return res.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Gagal mengirim pesan WhatsApp: {e}")
            return False
