import os
import logging
import asyncio
from datetime import time
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from summary import summarize_messages
from stock import analyze_stock
from memory import save_message, get_today_messages
import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

MAAHI_SYSTEM_PROMPT = """تو یک دستیار هوش مصنوعی پیشرفته برای یک گروه تلگرامی فارسی‌زبان هستی. اسم تو «ماهی» است.

رفتارت:
- دوستانه، ساده و قابل فهم
- کمی شوخ‌طبع ولی حرفه‌ای
- رفتار اعضا را از نوع پیام‌هایشان تشخیص بده (فعال، شوخ‌طبع، منطقی، احساسی، تازه‌وارد)
- فضای گروه را مثبت و مفید نگه دار
- به سوال‌ها سریع و دقیق جواب بده
- همیشه فارسی جواب بده مگر کاربر به زبان دیگری بنویسد"""

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


async def ask_maahi(user_message: str, username: str) -> str:
    """Send message to Claude (Maahi personality)"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=MAAHI_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"[{username}]: {user_message}"}
            ]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Anthropic error: {e}")
        return "⚠️ یه مشکلی پیش اومد، دوباره امتحان کن!"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🐟 سلام! منم ماهی، دستیار این گروه!\n"
        "می‌تونی باهام حرف بزنی، تحلیل بورس بخوای یا خلاصه گفتگو بگیری.\n\n"
        "دستورات:\n"
        "/stock [نماد] — تحلیل سهم\n"
        "/summary — خلاصه امروز\n"
        "/help — راهنما"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🐟 ماهی اینجاست!\n\n"
        "📌 دستورات:\n"
        "/stock خودرو — تحلیل سهم\n"
        "/summary — خلاصه گفتگوی امروز\n\n"
        "💬 یا فقط منو صدا بزن:\n"
        "«ماهی، نظرت چیه؟»\n"
        "«@bot_username سلام!»"
    )


async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stock command"""
    if not context.args:
        await update.message.reply_text("📊 نماد سهم رو بنویس!\nمثال: /stock خودرو")
        return

    symbol = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 دارم {symbol} رو بررسی می‌کنم...")

    analysis = await analyze_stock(symbol)
    await msg.edit_text(analysis)


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /summary command"""
    msg = await update.message.reply_text("📝 دارم خلاصه می‌کنم...")
    messages = get_today_messages(update.effective_chat.id)

    if not messages:
        await msg.edit_text("📭 امروز هنوز پیامی ثبت نشده!")
        return

    summary = await summarize_messages(messages)
    await msg.edit_text(summary)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all group/private messages"""
    if not update.message or not update.message.text:
        return

    msg_text = update.message.text
    username = update.effective_user.username or update.effective_user.first_name
    chat_id = update.effective_chat.id

    # Save message to memory
    save_message(chat_id, username, msg_text)

    # Check if bot is mentioned or it's a private chat
    bot_username = context.bot.username
    is_private = update.effective_chat.type == "private"
    is_mentioned = (
        f"@{bot_username}" in msg_text or
        "ماهی" in msg_text or
        (update.message.reply_to_message and
         update.message.reply_to_message.from_user.id == context.bot.id)
    )

    if not is_private and not is_mentioned:
        return

    # Check if stock analysis is requested inline
    stock_keywords = ["تحلیل", "نماد", "سهم", "بورس", "قیمت"]
    if any(kw in msg_text for kw in stock_keywords):
        # Try to extract symbol from message
        words = msg_text.split()
        for i, word in enumerate(words):
            if word in stock_keywords and i + 1 < len(words):
                symbol = words[i + 1]
                if len(symbol) >= 2:
                    analysis = await analyze_stock(symbol)
                    await update.message.reply_text(analysis)
                    return

    # General AI response
    reply = await ask_maahi(msg_text, username)
    await update.message.reply_text(reply)


async def send_daily_summary(context: ContextTypes.DEFAULT_TYPE):
    """Scheduled summary - runs at 8 AM and 8 PM"""
    chat_id = context.job.chat_id
    messages = get_today_messages(chat_id)

    if not messages:
        return

    summary = await summarize_messages(messages)
    await context.bot.send_message(chat_id=chat_id, text=f"🗓 خلاصه امروز:\n\n{summary}")


async def setup_jobs(app):
    """Setup scheduled jobs for a chat - call after bot joins a group"""
    pass  # Jobs are set per chat when bot is added


def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("stock", stock_command))
    app.add_handler(CommandHandler("summary", summary_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🐟 ماهی شروع به کار کرد!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
