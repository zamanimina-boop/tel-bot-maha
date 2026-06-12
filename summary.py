import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


async def summarize_messages(messages: list[dict]) -> str:
    """Summarize today's group messages using Claude"""
    if not messages:
        return "📭 پیامی برای خلاصه‌سازی وجود نداره!"

    if len(messages) < 3:
        return f"📝 فقط {len(messages)} پیام امروز ثبت شده، خیلی کم برای خلاصه!"

    # Format messages
    chat_text = "\n".join(
        f"[{m['time']}] {m['user']}: {m['text']}"
        for m in messages[-100:]  # last 100 messages max
    )

    prompt = f"""گفتگوی زیر از یک گروه تلگرامی فارسی‌زبان است:

{chat_text}

لطفاً یک خلاصه مفید به فارسی بنویس با این فرمت:

📋 *خلاصه گفتگوی امروز*

🔑 *موضوعات اصلی:*
• ...

💡 *نکات مهم:*
• ...

👥 *فعال‌ترین اعضا:* (فقط اسم)

(اگر بحث مهم یا آموزشی بود، برجسته کن)"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        return f"⚠️ خطا در خلاصه‌سازی: {str(e)}"
