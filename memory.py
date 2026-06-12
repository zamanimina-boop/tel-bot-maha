import json
import os
from datetime import datetime, date
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


def _get_file(chat_id: int) -> Path:
    return DATA_DIR / f"chat_{chat_id}.json"


def _load(chat_id: int) -> dict:
    f = _get_file(chat_id)
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {}


def _save(chat_id: int, data: dict):
    _get_file(chat_id).write_text(json.dumps(data, ensure_ascii=False, indent=2))


def save_message(chat_id: int, username: str, text: str):
    """Save a message to today's log"""
    data = _load(chat_id)
    today = str(date.today())

    if today not in data:
        data[today] = []

    data[today].append({
        "time": datetime.now().strftime("%H:%M"),
        "user": username,
        "text": text[:200]  # limit length
    })

    # Keep only last 7 days
    keys = sorted(data.keys())
    if len(keys) > 7:
        for old_key in keys[:-7]:
            del data[old_key]

    _save(chat_id, data)


def get_today_messages(chat_id: int) -> list[dict]:
    """Get all messages from today"""
    data = _load(chat_id)
    today = str(date.today())
    return data.get(today, [])


def get_active_users(chat_id: int, days: int = 7) -> list[tuple[str, int]]:
    """Get most active users in the last N days"""
    data = _load(chat_id)
    user_counts = {}

    for day_msgs in data.values():
        for msg in day_msgs:
            user = msg.get("user", "ناشناس")
            user_counts[user] = user_counts.get(user, 0) + 1

    return sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]
