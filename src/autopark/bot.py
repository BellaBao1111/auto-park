import logging
import re
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from . import config, db

log = logging.getLogger("bot")

SHORTHAND_RE = re.compile(r"^\s*(\S+)\s+(\S+)\s+(15|30|45|60)(?:\s+(\d{1,2}:\d{2}))?\s*$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
VALID_DURATIONS = {15, 30, 45, 60}


def _next_run_at(now: datetime, hour: int | None = None, minute: int | None = None) -> datetime:
    if hour is None and minute is None:
        return (now + timedelta(days=1)).replace(
            hour=config.RUN_HOUR, minute=config.RUN_MINUTE, second=0, microsecond=0
        )
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def _parse_time_arg(time_str: str) -> tuple[int, int]:
    match = TIME_RE.match(time_str)
    if not match:
        raise ValueError(f"Invalid time '{time_str}', expected HH:MM")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time '{time_str}', expected HH:MM (00:00-23:59)")
    return hour, minute


def _is_authorized(update: Update) -> bool:
    chat_id = str(update.effective_chat.id)
    if chat_id != config.TELEGRAM_CHAT_ID:
        log.warning("Ignoring message from unauthorized chat_id=%s", chat_id)
        return False
    return True


HELP_TEXT = (
    "Available commands:\n"
    "/park <zone> <space> <duration minutes: 15/30/45/60> [HH:MM] - schedule parking\n"
    "e.g. /park 408 503 60 (default triggers at 9:05am tomorrow)\n"
    "e.g. /park 408 503 60 08:30  (runs at 08:30 today if that's still in the future, else tomorrow)\n"
    'Shorthand also works: just send "408 503 60" or "408 503 60 08:30"\n'
    "/status - show pending job\n"
    "/cancel - cancel the pending job"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def schedule_job(update: Update, zone: str, space: str, duration: int, time_str: str | None = None):
    now = datetime.now()
    hour, minute = None, None
    if time_str is not None:
        try:
            hour, minute = _parse_time_arg(time_str)
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
    run_at = _next_run_at(now, hour, minute)
    job_id = db.add_job(zone, space, duration, run_at)
    await update.message.reply_text(
        f"Scheduled job #{job_id}: zone={zone} space={space} duration={duration}min\n"
        f"Will run at {run_at.strftime('%Y-%m-%d %H:%M')}"
    )


async def park(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    args = context.args
    if len(args) not in (3, 4):
        await update.message.reply_text("Usage: /park <zone> <space> <duration minutes: 15/30/45/60> [HH:MM]")
        return
    zone, space, duration_str = args[:3]
    time_str = args[3] if len(args) == 4 else None
    if not duration_str.isdigit() or int(duration_str) not in VALID_DURATIONS:
        await update.message.reply_text("Duration must be one of: 15, 30, 45, 60")
        return
    await schedule_job(update, zone, space, int(duration_str), time_str)


async def plain_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    match = SHORTHAND_RE.match(update.message.text or "")
    if not match:
        await update.message.reply_text(f"Didn't understand that.\n\n{HELP_TEXT}")
        return
    zone, space, duration_str, time_str = match.groups()
    await schedule_job(update, zone, space, int(duration_str), time_str)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    job = db.get_latest_pending()
    if not job:
        await update.message.reply_text("No pending job.")
        return
    await update.message.reply_text(
        f"Pending job #{job.id}: zone={job.zone} space={job.space} "
        f"duration={job.duration_minutes}min, run_at={job.run_at}"
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    job = db.cancel_latest_pending()
    if not job:
        await update.message.reply_text("No pending job to cancel.")
        return
    await update.message.reply_text(f"Cancelled job #{job.id}.")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    await update.message.reply_text(f"Unknown command.\n\n{HELP_TEXT}")


def build_application() -> Application:
    config.require_bot_config()
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("park", park))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, plain_text))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    return application
