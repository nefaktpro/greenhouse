import os
import time
import telebot
from dotenv import load_dotenv

from interfaces.telegram_v3.handlers import register_v3_handlers


def main():
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not found in environment")

    bot = telebot.TeleBot(token)
    register_v3_handlers(bot)

    print("GREENHOUSE v17 / TG v3 started")

    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
