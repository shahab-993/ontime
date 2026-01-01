# attendance/tasks.py
import os

from apscheduler.schedulers.background import BackgroundScheduler

from config import settings
from config.constants import AUTO_DOWNLOAD_ATT_LOGS_INTERVAL
from core.utils import sync_attendance_logs_raw

scheduler = BackgroundScheduler()
_scheduler_started = False  # ✅ guard to prevent multiple starts


def start_scheduler():
    global _scheduler_started

    # ── 1) Don’t schedule in the autoreloader “parent” ────────────────
    if settings.DEBUG and os.environ.get('RUN_MAIN') != 'true':
        return

    # ── 2) Only add/start once per process ────────────────────────────
    if not _scheduler_started:
        scheduler.add_job(
            sync_attendance_logs_raw,
            'interval',
            minutes=AUTO_DOWNLOAD_ATT_LOGS_INTERVAL,
            id='sync_attendance_logs',  # ← fixed ID
            replace_existing=True  # ← overwrite if already added
        )
        scheduler.start()
        _scheduler_started = True
