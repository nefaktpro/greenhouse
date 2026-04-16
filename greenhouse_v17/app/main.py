import time
import telebot
from greenhouse_v17.config import TELEGRAM_BOT_TOKEN
from greenhouse_v17.interfaces.telegram_v3.handlers import register_v3_handlers

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not found")

    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
    register_v3_handlers(bot)

    print("GREENHOUSE v17 package started")

    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(3)

if __name__ == "__main__":
    main()
