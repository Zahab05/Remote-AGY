import os
import asyncio
import logging
import threading
from typing import Dict, Any, Optional, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from src.bot.notifier_manager import BaseNotifier
from src.storage.db import DatabaseManager

logger = logging.getLogger(__name__)

class TelegramBot(BaseNotifier):
    """
    Bot Telegram interaktif untuk menerima notifikasi tugas SLCM,
    memberikan persetujuan via tombol, dan mengirimkan hasil kerja AGY.
    """
    def __init__(self, db: DatabaseManager, config: Optional[dict] = None, agy_runner = None):
        self.db = db
        self.config = config or {}
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN") or self.config.get("bot_token", "")
        self.allowed_chat_ids: List[int] = list(self.config.get("allowed_chat_ids", []))
        
        env_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if env_chat_id:
            try:
                cid = int(env_chat_id)
                if cid not in self.allowed_chat_ids:
                    self.allowed_chat_ids.append(cid)
            except ValueError:
                pass

        self.agy_runner = agy_runner
        self.app: Optional[Application] = None

    def build_application(self) -> Optional[Application]:
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN belum disetel. Bot Telegram tidak aktif.")
            return None

        if self.app:
            return self.app

        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("tasks", self._cmd_tasks))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("approve", self._cmd_approve))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
        return self.app

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id not in self.allowed_chat_ids:
            self.allowed_chat_ids.append(chat_id)

        msg = (
            f"🤖 *Remote-AGY Bot Aktif!*\n\n"
            f"Halo *{update.effective_user.first_name}*!\n"
            f"Chat ID Anda: `{chat_id}`\n"
            f"Sistem siap mendeteksi tugas kampus (SATU/EMAS UI) dan menjalankannya via AGY di terminal.\n\n"
            f"Perintah yang tersedia:\n"
            f"• /tasks - Lihat daftar tugas terbaru\n"
            f"• /status - Cek status bot & background runner\n"
            f"• /approve <id> - Setujui tugas secara manual"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        pending = self.db.get_pending_tasks()
        await update.message.reply_text(
            f"📊 *Status Remote-AGY*\n"
            f"• Tugas Menunggu Approval: *{len(pending)}*\n"
            f"• Runner: *Headless AGY CLI*",
            parse_mode="Markdown"
        )

    async def _cmd_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        tasks = self.db.get_all_assignments(limit=5)
        if not tasks:
            await update.message.reply_text("Belum ada data tugas yang terdeteksi.")
            return

        text = "📋 *Daftar Tugas Terbaru:*\n\n"
        for t in tasks:
            emoji = "🟡" if t.get("difficulty") == "Medium" else ("🔴" if t.get("difficulty") == "Hard" else "🟢")
            text += (
                f"• [{t.get('status')}] {emoji} *{t.get('course_name')}*\n"
                f"  Judul: {t.get('title')}\n"
                f"  ID: `{t.get('id')}` | Deadline: {t.get('due_date', '-')}\n\n"
            )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def _cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("Gunakan format: `/approve <task_id>`", parse_mode="Markdown")
            return
        task_id = context.args[0]
        task = self.db.get_assignment(task_id)
        if not task:
            await update.message.reply_text(f"Tugas dengan ID `{task_id}` tidak ditemukan.", parse_mode="Markdown")
            return

        await update.message.reply_text(f"✅ Tugas `{task_id}` disetujui! Memulai AGY...", parse_mode="Markdown")
        self._start_execution_async(task)

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        data = query.data
        if not data or ":" not in data:
            return

        action, task_id = data.split(":", 1)
        task = self.db.get_assignment(task_id)
        if not task:
            await query.edit_message_text(f"⚠️ Tugas ID `{task_id}` tidak ditemukan.")
            return

        if action == "approve":
            await query.edit_message_text(
                f"✅ *Persetujuan Diterima!*\n\n"
                f"📚 *Mata Kuliah*: {task.get('course_name')}\n"
                f"📝 *Tugas*: {task.get('title')}\n\n"
                f"⚙️ _AGY sedang mengeksekusi pengerjaan tugas di terminal laptop/codespace..._\n"
                f"Hasil pengerjaan akan dikirim ke sini setelah selesai.",
                parse_mode="Markdown"
            )
            self._start_execution_async(task)

        elif action == "ignore":
            self.db.update_status(task_id, "REJECTED")
            await query.edit_message_text(f"❌ Tugas `{task.get('title')}` telah diabaikan.")

        elif action == "snooze":
            await query.edit_message_text(f"⏳ Tugas `{task.get('title')}` ditunda. Akan diingatkan kembali nanti.")

    def _start_execution_async(self, task: Dict[str, Any]):
        if not self.agy_runner:
            logger.error("AGY Runner belum disetel di TelegramBot.")
            return

        def run():
            self.agy_runner.execute_task(task, callback_notifier=self)

        threading.Thread(target=run, daemon=True).start()

    def send_task_alert(self, task: Dict[str, Any]) -> bool:
        if not self.token or not self.allowed_chat_ids:
            logger.warning("Bot Telegram belum siap atau chat ID belum diatur.")
            return False

        task_id = task["id"]
        difficulty = task.get("difficulty", "Unknown")
        diff_emoji = "🔴" if difficulty == "Hard" else ("🟡" if difficulty == "Medium" else "🟢")

        text = (
            f"🚨 *[TUGAS BARU TERDETEKSI DI SLCM]* 🚨\n\n"
            f"📚 *Mata Kuliah*: {task.get('course_name', '-')}\n"
            f"📝 *Judul Tugas*: {task.get('title', '-')}\n"
            f"⏰ *Batas Waktu*: {task.get('due_date_display', task.get('due_date', '-'))}\n"
            f"⏳ *Sisa Waktu*: {task.get('remaining_time', '-')}\n"
            f"⚡ *Tingkat Kesulitan*: {diff_emoji} *{difficulty}*\n"
            f"💡 *Catatan Analisis*: {task.get('difficulty_reason', '-')}\n\n"
            f"Apakah Anda ingin AGY mengerjakan tugas ini sekarang?"
        )

        keyboard = [
            [InlineKeyboardButton("✅ Setujui & Kerjakan", callback_data=f"approve:{task_id}")],
            [
                InlineKeyboardButton("⏳ Ingatkan Nanti", callback_data=f"snooze:{task_id}"),
                InlineKeyboardButton("❌ Abaikan", callback_data=f"ignore:{task_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        async def _send():
            bot = Bot(token=self.token)
            for cid in self.allowed_chat_ids:
                try:
                    await bot.send_message(
                        chat_id=cid,
                        text=text,
                        parse_mode="Markdown",
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Gagal mengirim alert ke chat {cid}: {e}")

        self._run_async(_send())
        return True

    def notify_progress(self, task: Dict[str, Any], message: str) -> bool:
        if not self.token or not self.allowed_chat_ids:
            return False

        async def _send():
            bot = Bot(token=self.token)
            for cid in self.allowed_chat_ids:
                try:
                    await bot.send_message(
                        chat_id=cid,
                        text=f"⚙️ *Update Progres AGY*\n{message}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Gagal kirim progres: {e}")

        self._run_async(_send())
        return True

    def notify_completed(self, task: Dict[str, Any], result: Dict[str, Any]) -> bool:
        if not self.token or not self.allowed_chat_ids:
            return False

        zip_path = result.get("zip_path")
        summary = result.get("summary", "Tugas selesai dikerjakan.")

        async def _send():
            bot = Bot(token=self.token)
            for cid in self.allowed_chat_ids:
                try:
                    await bot.send_message(
                        chat_id=cid,
                        text=summary,
                        parse_mode="Markdown"
                    )
                    if zip_path and os.path.exists(zip_path):
                        with open(zip_path, "rb") as doc:
                            await bot.send_document(
                                chat_id=cid,
                                document=doc,
                                filename=os.path.basename(zip_path),
                                caption=f"📦 Berkas tugas {task.get('title')} hasil kerja AGY"
                            )
                except Exception as e:
                    logger.error(f"Gagal kirim berkas hasil: {e}")

        self._run_async(_send())
        return True

    def _run_async(self, coro):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            asyncio.run(coro)
