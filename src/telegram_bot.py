"""
Telegram bot for Job Radar.
Sends daily digest at 7 AM CET + interactive buttons.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
)
from telegram.constants import ParseMode

from config import DELIVERY, DATA
from pipeline import run as run_pipeline

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("job-radar-bot")

DIGESTS_DIR = DATA / "digests"
DIGESTS_DIR.mkdir(exist_ok=True)


# ──── command handlers ───────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (
        f"Hey {user.first_name} 👋\n\n"
        "I'm your *Job Radar* — daily top-10 jobs matched to your profile.\n\n"
        "*Commands:*\n"
        "/today — show today's digest\n"
        "/rerun \\<hours\\> — custom window \\(e.g. `/rerun 48`\\)\n"
        "/global — search globally, not just Germany\n"
        "/help — this message\n\n"
        "I'll auto\\-ping you every day at *07:00 CET*\\."
    )
    try:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception:
        # fallback if MarkdownV2 parsing fails
        await update.message.reply_text(
            "Hey! I'm Job Radar.\n\n"
            "Commands:\n"
            "/today — show today's digest\n"
            "/rerun 48 — last 48 hours\n"
            "/global — worldwide search\n"
            "/help — command list\n\n"
            "Daily digest at 07:00 CET."
        )


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await start(update, ctx)


async def today(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    p = DIGESTS_DIR / "latest.json"
    # Always ack immediately so user knows we're alive
    if not p.exists():
        await update.message.reply_text("No digest yet — running first scan now (1–2 min)…")
        from pipeline import run as run_pipeline
        run_pipeline(hours=24)
        await _send_digest_message(update.effective_chat.id, ctx,
                                    path=DIGESTS_DIR / "latest.json",
                                    reply_to=update.message)
    else:
        await _send_digest_message(update.effective_chat.id, ctx,
                                    path=DIGESTS_DIR / "latest.json",
                                    reply_to=update.message)


async def rerun(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Usage: /rerun 48   or  /rerun 168"""
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: /rerun <hours>\nExample: /rerun 48")
        return
    try:
        hours = int(args[0])
        hours = max(1, min(hours, 24 * 30))  # 1h .. 30d
    except ValueError:
        await update.message.reply_text("Hours must be an integer.")
        return
    global_search = "global" in (args[1:] if len(args) > 1 else [])
    await update.message.reply_text(
        f"🔄 Rerunning pipeline: last {hours}h"
        f"{' (global)' if global_search else ' (Germany only)'}…"
    )
    digest = run_pipeline(hours=hours, global_search=global_search)
    await _send_digest_message(
        update.effective_chat.id, ctx,
        path=DIGESTS_DIR / "latest.json",
        text_prefix=f"🔄 *Custom rerun \\({hours}h\\)*\n",
    )


async def global_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌐 Running global scan (any country)…")
    digest = run_pipeline(hours=168, global_search=True)
    await _send_digest_message(
        update.effective_chat.id, ctx,
        path=DIGESTS_DIR / "latest.json",
        text_prefix="🌐 *Global scan*\n",
    )


# ──── callback handlers ──────────────────────────────────────────────
async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    if data == "noop":
        return
    if data.startswith("apply:"):
        url = data[len("apply:"):]
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(f"🔗 Apply: {url}")
    elif data.startswith("s:"):
        # store saved job by short hash
        import hashlib
        short = data[len("s:"):]
        # match against latest digest
        saved = _load_saved()
        digest_path = DIGESTS_DIR / "latest.json"
        if digest_path.exists():
            digest = json.loads(digest_path.read_text())
            for j in digest.get("jobs", []):
                full_id = j.get("id", "")
                if hashlib.md5(full_id.encode()).hexdigest()[:12] == short:
                    saved.add(full_id)
                    _save_saved(saved)
                    await q.answer("💾 Saved!", show_alert=True)
                    return
        await q.answer("⚠️ Could not save (job not in current digest).")
    elif data == "rerun:24":
        run_pipeline(hours=24)
        await q.message.reply_text("✅ Rerun done. /today to see.")
    elif data == "rerun:48":
        run_pipeline(hours=48)
        await q.message.reply_text("✅ 48h rerun done. /today to see.")


# ──── send digest ────────────────────────────────────────────────────
async def _send_digest_message(chat_id, ctx, path: Path,
                                text_prefix: str = "",
                                reply_to=None):
    if not path.exists():
        if reply_to:
            await reply_to.reply_text("No digest available.")
        return
    digest = json.loads(path.read_text())
    jobs = digest.get("jobs", [])

    if not jobs:
        await ctx.bot.send_message(
            chat_id=chat_id,
            text=("No matching jobs in the window. "
                  "Try `/rerun 168` for a 7-day look-back."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    header = text_prefix or (
        f"📬 *Daily Job Radar* \\({datetime.now():%d %b}\\)\n"
        f"_Generated {datetime.now():%H:%M} • "
        f"window: {digest.get('window_hours', 24)}h • "
        f"{digest['counts']['delivered']} of "
        f"{digest['counts']['filtered']} matched_\n"
    )

    # Send header as one message
    await ctx.bot.send_message(
        chat_id=chat_id, text=header,
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    # Send each job with its own buttons
    for i, j in enumerate(jobs, 1):
        msg = _format_job_message(i, j)
        kb = _job_keyboard(j)
        try:
            await ctx.bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
        except Exception as e:
            log.error(f"send job {i} failed: {e}")


def _format_job_message(idx: int, j: dict) -> str:
    loc = j.get("location", "")
    remote = " 🏠 Remote" if j.get("remote_ok") else ""
    sal = ""
    if j.get("salary_eur"):
        sal = f" 💶 €{j['salary_eur']:,}"
    matched_skills = ", ".join((j.get("matched_skills") or [])[:6])
    ats_kw = j.get("ats_keywords_to_add") or []
    age = j.get("_age_hours")
    age_str = f" • ⏱ {age}h ago" if age is not None else ""

    msg = (
        f"*{idx:02d}\\. \\[{j['score']:03d}\\] {escape_md(j['title'])}*\n"
        f"🏢 {escape_md(j.get('company', 'Unknown'))} • "
        f"📍 {escape_md(loc)}{remote}{sal}{age_str}\n"
    )
    if matched_skills:
        msg += f"✅ Matched: {escape_md(matched_skills)}\n"
    if ats_kw:
        # Show top ATS keyword suggestions to add to resume
        msg += f"📝 *Add to resume:* {escape_md(', '.join(ats_kw[:6]))}\n"
    reasons = j.get("reasons") or []
    if reasons:
        msg += f"💡 {escape_md(' • '.join(reasons[:3]))}\n"
    return msg


def _job_keyboard(j: dict) -> InlineKeyboardMarkup:
    url = j.get("url") or ""
    # Telegram callback_data limit is 64 bytes. Use short hash of job id.
    import hashlib
    jid = j.get("id") or ""
    short_id = hashlib.md5(jid.encode()).hexdigest()[:12] if jid else ""
    buttons = []
    if url:
        buttons.append(InlineKeyboardButton("🔗 Apply", url=url))
    if short_id:
        buttons.append(
            InlineKeyboardButton("💾 Save", callback_data=f"s:{short_id}")
        )
    rows = [buttons]
    return InlineKeyboardMarkup(rows)


# ──── saved-jobs persistence ────────────────────────────────────────
SAVED_FILE = DATA / "saved_jobs.json"


def _load_saved() -> set[str]:
    if SAVED_FILE.exists():
        try:
            return set(json.loads(SAVED_FILE.read_text()))
        except Exception:
            return set()
    return set()


def _save_saved(s: set[str]) -> None:
    SAVED_FILE.write_text(json.dumps(sorted(s)))


# ──── markdown escape ───────────────────────────────────────────────
def escape_md(text: str) -> str:
    """Light Telegram MarkdownV2 escape."""
    if not text:
        return ""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


# ──── main entry ─────────────────────────────────────────────────────
def build_application() -> Application:
    token = DELIVERY["telegram"]["token"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("rerun", rerun))
    app.add_handler(CommandHandler("global", global_cmd))
    app.add_handler(CallbackQueryHandler(on_button))
    return app


def send_daily_digest_sync():
    """Used by the scheduler — runs pipeline + sends Telegram message."""
    import asyncio
    from telegram import Bot

    token = DELIVERY["telegram"]["token"]
    chat_id = DELIVERY["telegram"]["chat_id"]
    log.info("Running daily pipeline…")
    run_pipeline()

    async def _send():
        bot = Bot(token=token)
        await _send_digest_message(
            chat_id=int(chat_id),
            ctx=type("C", (), {"bot": bot})(),
            path=DIGESTS_DIR / "latest.json",
        )

    asyncio.run(_send())


if __name__ == "__main__":
    app = build_application()
    log.info("Starting bot (polling)…")
    app.run_polling()