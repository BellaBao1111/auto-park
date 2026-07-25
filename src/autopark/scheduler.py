import asyncio
import logging
from datetime import datetime
from pathlib import Path

from telegram.ext import ContextTypes

from . import bot, config, db, pay

config.LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.LOG_DIR / "auto-park.log"),
    ],
)
log = logging.getLogger("scheduler")

CHECK_INTERVAL_SECONDS = 30


async def check_due_jobs(context: ContextTypes.DEFAULT_TYPE):
    due = db.get_pending_due(datetime.now())
    for job in due:
        log.info(
            "Running job #%s: zone=%s space=%s duration=%s",
            job.id,
            job.zone,
            job.space,
            job.duration_minutes,
        )
        db.mark_job(job.id, "running")
        try:
            result = await asyncio.to_thread(pay.run_payment, job.zone, job.space, job.duration_minutes)
        except Exception as exc:  # noqa: BLE001
            log.exception("Unhandled error running job #%s", job.id)
            db.mark_job(job.id, "failed", str(exc))
            await context.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID, text=f"Job #{job.id} crashed: {exc}"
            )
            continue

        db.mark_job(job.id, "done" if result.success else "failed", result.message)
        status_word = "OK" if result.success else "FAILED"
        text = (
            f"Job #{job.id} [{status_word}]\n"
            f"zone={job.zone} space={job.space} duration={job.duration_minutes}min\n"
            f"{result.message}"
        )
        await context.bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)
        if result.screenshot_path and Path(result.screenshot_path).exists():
            with open(result.screenshot_path, "rb") as f:
                await context.bot.send_photo(chat_id=config.TELEGRAM_CHAT_ID, photo=f)


def main():
    # Fail fast if payment config is missing, rather than deferring the error to
    # job-fire time (pay.run_payment also enforces this, but only at 09:05am).
    config.require_payment_config()
    db.init_db()
    application = bot.build_application()
    application.job_queue.run_repeating(check_due_jobs, interval=CHECK_INTERVAL_SECONDS, first=5)
    log.info("auto-park scheduler starting (dry_run=%s)", not config.LIVE_MODE)
    application.run_polling()


if __name__ == "__main__":
    main()
