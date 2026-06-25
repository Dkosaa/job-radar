"""
Long-running service: scheduler + bot polling + dashboard.
Runs the daily pipeline at 07:00 CET, also keeps Telegram bot polling
so /today, /rerun etc. work instantly.

Start with:
    python3 scheduler.py
"""
import logging
import signal
import sys
import time
from datetime import datetime
from threading import Thread

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import DELIVERY
from pipeline import run as run_pipeline
from telegram_bot import (
    build_application, send_daily_digest_sync,
)
from dashboard import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("scheduler")


def daily_job():
    log.info("⏰ Daily 7am CET job firing…")
    try:
        send_daily_digest_sync()
        log.info("✅ Daily digest sent via Telegram.")
    except Exception as e:
        log.exception(f"Daily job failed: {e}")


def start_scheduler():
    tz = pytz.timezone("Europe/Berlin")
    sched = BackgroundScheduler(timezone=tz)
    sched.add_job(
        daily_job,
        CronTrigger(
            hour=DELIVERY["schedule"]["daily_hour_cet"],
            minute=DELIVERY["schedule"]["daily_minute_cet"],
            timezone=tz,
        ),
        id="daily_digest",
        name="Daily 7am CET job digest",
        replace_existing=True,
    )
    sched.start()
    log.info(
        f"Scheduler started. Next run: "
        f"{sched.get_job('daily_digest').next_run_time}"
    )
    return sched


def start_dashboard():
    log.info(f"Starting dashboard on "
             f"{DELIVERY['dashboard']['host']}:{DELIVERY['dashboard']['port']}")
    # use Flask built-in server; production swap-in would be gunicorn
    app.run(
        host=DELIVERY["dashboard"]["host"],
        port=DELIVERY["dashboard"]["port"],
        debug=False,
        use_reloader=False,
    )


def start_bot_polling():
    log.info("Starting Telegram bot (polling)…")
    application = build_application()
    application.run_polling(stop_signals=[])


def main():
    log.info("=" * 50)
    log.info("📡 Job Radar — Raj Sakhiya")
    log.info("=" * 50)

    # 1) Scheduler thread
    sched = start_scheduler()

    # 2) Dashboard thread (Flask)
    dash_thread = Thread(target=start_dashboard, daemon=True)
    dash_thread.start()

    # 3) Bot polling (main thread)
    try:
        start_bot_polling()
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutting down…")
        sched.shutdown(wait=False)
        sys.exit(0)


if __name__ == "__main__":
    main()