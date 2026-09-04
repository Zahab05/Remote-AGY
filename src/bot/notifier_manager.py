import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class BaseNotifier:
    def send_task_alert(self, task: Dict[str, Any]) -> bool:
        raise NotImplementedError
    
    def notify_progress(self, task: Dict[str, Any], message: str) -> bool:
        raise NotImplementedError

    def notify_completed(self, task: Dict[str, Any], result: Dict[str, Any]) -> bool:
        raise NotImplementedError

class NotifierManager(BaseNotifier):
    """
    Manajer terpusat untuk mendistribusikan notifikasi ke Telegram dan WhatsApp.
    """
    def __init__(self):
        self.notifiers: List[BaseNotifier] = []

    def register_notifier(self, notifier: BaseNotifier):
        self.notifiers.append(notifier)

    def send_task_alert(self, task: Dict[str, Any]) -> bool:
        success = True
        for n in self.notifiers:
            try:
                res = n.send_task_alert(task)
                success = success and res
            except Exception as e:
                logger.error(f"Gagal mengirim alert tugas via {n.__class__.__name__}: {e}")
                success = False
        return success

    def notify_progress(self, task: Dict[str, Any], message: str) -> bool:
        success = True
        for n in self.notifiers:
            try:
                res = n.notify_progress(task, message)
                success = success and res
            except Exception as e:
                logger.error(f"Gagal mengirim progres via {n.__class__.__name__}: {e}")
                success = False
        return success

    def notify_completed(self, task: Dict[str, Any], result: Dict[str, Any]) -> bool:
        success = True
        for n in self.notifiers:
            try:
                res = n.notify_completed(task, result)
                success = success and res
            except Exception as e:
                logger.error(f"Gagal mengirim notifikasi selesai via {n.__class__.__name__}: {e}")
                success = False
        return success
