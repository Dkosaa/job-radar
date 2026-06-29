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
from filters import load_prefs, save_prefs, apply_filters, parse_filter_command

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
        "/chalohave — unlock the bot and show help\n"
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
            "/chalohave — unlock the bot and show help\n"
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
    if not p.exists():
        await update.message.reply_text("No digest yet — running first scan now (1–2 min)…")
        from pipeline import run as run_pipeline
        run_pipeline(hours=24)
    # Apply user filters before sending
    await _send_digest_message(update.effective_chat.id, ctx,
                                path=DIGESTS_DIR / "latest.json",
                                reply_to=update.message,
                                apply_user_filters=True)


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
        apply_user_filters=True,
    )


async def global_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌐 Running global scan (any country)…")
    digest = run_pipeline(hours=168, global_search=True)
    await _send_digest_message(
        update.effective_chat.id, ctx,
        path=DIGESTS_DIR / "latest.json",
        text_prefix="🌐 *Global scan*\n",
        apply_user_filters=True,
    )


async def filter_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /filter role=uipath        → require role keyword
    /filter salary=70          → min salary €70k
    /filter remote=on          → only remote jobs
    /filter location=munich    → only Munich jobs
    /filter min_score=50       → higher bar
    /filter exclude=senior     → exclude jobs with 'senior'

    Multiple values for the same key — TWO supported syntaxes:

      Syntax A (space-separated, implicit repeat):
        /filter role=uipath power_automate test_automation
        /filter location=munich berlin hamburg
        # the bare tokens after the first `key=val` are added to the same key

      Syntax B (explicit repeat):
        /filter role=uipath role=power_automate role=test_automation
        /filter location=munich location=berlin
    """
    args = ctx.args or []
    if not args:
        await update.message.reply_text(_filters_help())
        return

    prefs = load_prefs()
    parts = []

    # First pass: explicit `key=value` tokens
    last_key = None
    pending = []
    for arg in args:
        if "=" in arg:
            # finalize any pending tokens for previous key
            if last_key and pending:
                _apply_filter_set(prefs, last_key, pending, parts)
                pending = []
            parsed = parse_filter_command(arg)
            if not parsed:
                parts.append(f"⚠️ ignored `{arg}`")
                last_key = None
                continue
            key, val = parsed
            if key in {"role_keywords_append", "exclude_keywords_append"}:
                # accumulate these into lists
                _apply_filter_set(prefs, key, [val], parts)
                last_key = None
                pending = []
            else:
                # scalar setting — apply immediately
                _apply_scalar(prefs, key, val, parts)
                last_key = None
                pending = []
        else:
            # bare token — attach to last append-style key, or default to role
            if last_key is None:
                last_key = "role_keywords_append"
            pending.append(arg)

    # flush trailing pending
    if last_key and pending:
        _apply_filter_set(prefs, last_key, pending, parts)

    save_prefs(prefs)
    await update.message.reply_text(
        "✅ Filters updated:\n• " + "\n• ".join(parts)
        + "\n\nSend `/today` to apply."
    )


def _apply_filter_set(prefs, key, values, parts):
    if key == "role_keywords_append":
        prefs.setdefault("role_keywords", [])
        for v in values:
            if v.lower() not in [k.lower() for k in prefs["role_keywords"]]:
                prefs["role_keywords"].append(v)
        parts.append(f"role += `{', '.join(values)}`")
    elif key == "exclude_keywords_append":
        prefs.setdefault("exclude_keywords", [])
        for v in values:
            if v.lower() not in [k.lower() for k in prefs["exclude_keywords"]]:
                prefs["exclude_keywords"].append(v)
        parts.append(f"exclude += `{', '.join(values)}`")


def _apply_scalar(prefs, key, val, parts):
    if key == "min_salary":
        prefs["min_salary"] = val
        parts.append(f"min salary = €{val:,}")
    elif key == "remote_only":
        prefs["remote_only"] = val
        parts.append(f"remote only = {val}")
    elif key == "location":
        prefs["location"] = val
        parts.append(f"location = `{val}`")
    elif key == "min_score":
        prefs["min_score"] = val
        parts.append(f"min score = {val}")


async def filters_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show current filters."""
    prefs = load_prefs()
    msg = (
        "*Current filters:*\n"
        f"• Min salary: €{prefs['min_salary']:,}\n"
        f"• Min score: {prefs['min_score']}\n"
        f"• Remote only: {prefs['remote_only']}\n"
        f"• Location: {prefs['location']}\n"
        f"• Role keywords: {', '.join(prefs['role_keywords']) or 'none'}\n"
        f"• Exclude keywords: {', '.join(prefs['exclude_keywords']) or 'none'}\n"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)


async def reset_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from filters import DEFAULT_PREFS
    save_prefs(DEFAULT_PREFS.copy())
    await update.message.reply_text(
        "✅ Filters reset to defaults.\nSend /today to apply."
    )


def _filters_help() -> str:
    return (
        "*Filter syntax* \\(one or more `key=value`\\):\n\n"
        "`/filter role=uipath` \\- require role keyword\n"
        "`/filter salary=70` \\- min salary €70k\n"
        "`/filter remote=on` \\- only remote jobs\n"
        "`/filter location=munich` \\- only Munich jobs\n"
        "`/filter min_score=50` \\- higher bar\n"
        "`/filter exclude=senior` \\- skip senior\\-level\n\n"
        "*Combine:* `/filter role=automation salary=70`\n\n"
        "*Other:* `/filters` to view, `/reset` to clear"
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
                                reply_to=None,
                                apply_user_filters: bool = False):
    if not path.exists():
        if reply_to:
            await reply_to.reply_text("No digest available.")
        return
    digest = json.loads(path.read_text())
    jobs = digest.get("jobs", [])

    # Apply user filters if requested
    if apply_user_filters:
        prefs = load_prefs()
        before = len(jobs)
        jobs = apply_filters(jobs, prefs)
        # Show filter summary in prefix
        fsummary = (
            f"\n_Filters: salary≥€{prefs['min_salary']:,} • "
            f"score≥{prefs['min_score']} • "
            f"remote={prefs['remote_only']} • "
            f"loc={prefs['location']}_"
        )
        if prefs["role_keywords"]:
            fsummary += f"\n_Role: {', '.join(prefs['role_keywords'])}_"
        if prefs["exclude_keywords"]:
            fsummary += f"\n_Excluded: {', '.join(prefs['exclude_keywords'])}_"
        text_prefix = (text_prefix or "") + fsummary

    if not jobs:
        await ctx.bot.send_message(
            chat_id=chat_id,
            text=("No matching jobs with current filters. "
                  "Try `/reset` to clear, or `/filter salary=50` to lower the bar."),
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

    await ctx.bot.send_message(
        chat_id=chat_id, text=header,
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    for i, j in enumerate(jobs[:15], 1):  # cap at 15 jobs per send
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
    app.add_handler(CommandHandler("chalohave", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("rerun", rerun))
    app.add_handler(CommandHandler("global", global_cmd))
    app.add_handler(CommandHandler("filter", filter_cmd))
    app.add_handler(CommandHandler("filters", filters_cmd))
    app.add_handler(CommandHandler("reset", reset_cmd))
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