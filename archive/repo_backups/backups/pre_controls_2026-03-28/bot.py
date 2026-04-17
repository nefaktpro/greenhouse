#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import traceback
import threading

import telebot

from bot_handlers import register_handlers
from reports import build_send_now_report
from cameras import get_report_cameras, get_camera


def load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_env_file(ENV_PATH)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
STATUS_PUSH_TIMES = [x.strip() for x in os.getenv("STATUS_PUSH_TIMES", "10:00,23:00").split(",") if x.strip()]

NIGHT_MONITOR_ENABLED = os.getenv("NIGHT_MONITOR_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not found in .env")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


def now_hhmm() -> str:
    return time.strftime("%H:%M")


def safe_send(chat_id: str, text: str) -> None:
    if not chat_id:
        return
    text = text or "(пустой ответ)"
    limit = 3800
    while text:
        chunk = text[:limit]
        bot.send_message(chat_id, chunk)
        text = text[limit:]
        if text:
            time.sleep(0.3)


def send_morning_cameras(chat_id: str):
    """
    Отправляем фото только для утреннего отчёта (10:00).
    """
    for cam in get_report_cameras():
        try:
            img = get_camera(cam["id"])
            if img:
                bot.send_chat_action(chat_id, "upload_photo")
                bot.send_photo(chat_id, img, caption=cam["name"])
                time.sleep(1)
            else:
                bot.send_message(chat_id, f"⚠️ Камера не ответила: {cam['name']}")
        except Exception:
            traceback.print_exc()
            try:
                bot.send_message(chat_id, f"⚠️ Ошибка камеры: {cam['name']}")
            except Exception:
                pass


def planned_reports_loop():
    sent_keys = set()

    while True:
        try:
            current = now_hhmm()
            today = time.strftime("%Y-%m-%d")

            for hhmm in STATUS_PUSH_TIMES:
                key = f"{today}_{hhmm}"
                if current == hhmm and key not in sent_keys:
                    try:
                        safe_send(TELEGRAM_CHAT_ID, build_send_now_report())

                        # Только в 10:00 отправляем фото с камер
                        if hhmm == "10:00":
                            send_morning_cameras(TELEGRAM_CHAT_ID)

                        print(f"[planned_reports_loop] sent report at {current}")
                    except Exception:
                        traceback.print_exc()

                    sent_keys.add(key)

            if len(sent_keys) > 20:
                sent_keys = {x for x in sent_keys if x.startswith(today)}

        except Exception:
            traceback.print_exc()

        time.sleep(10)


def main():
    print("Bot v15 started")
    print("PUSH_TIMES =", STATUS_PUSH_TIMES)
    print("TELEGRAM_CHAT_ID =", TELEGRAM_CHAT_ID)
    print("NIGHT_MONITOR_ENABLED =", NIGHT_MONITOR_ENABLED)

    register_handlers(bot)

    threading.Thread(target=planned_reports_loop, daemon=True).start()

    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
