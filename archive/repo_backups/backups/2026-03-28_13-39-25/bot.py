#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import traceback
import threading
from datetime import datetime

import telebot


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

NIGHT_MONITOR_ENABLED = os.getenv("NIGHT_MONITOR_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
NIGHT_MONITOR_CHAT_ID = os.getenv("NIGHT_MONITOR_CHAT_ID", TELEGRAM_CHAT_ID).strip()
NIGHT_MONITOR_START = os.getenv("NIGHT_MONITOR_START", "00:00").strip()
NIGHT_MONITOR_END = os.getenv("NIGHT_MONITOR_END", "08:00").strip()
NIGHT_MONITOR_MINUTES = int(os.getenv("NIGHT_MONITOR_MINUTES", "30").strip() or "30")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not found in .env")

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


def import_module_or_none(name: str):
    try:
        return __import__(name)
    except Exception:
        return None


ha_module = import_module_or_none("ha_client")
status_view_module = import_module_or_none("status_view")
ai_service_module = import_module_or_none("ai_service")
fire_safety_module = import_module_or_none("fire_safety")


def build_ha_client():
    if ha_module is None:
        raise RuntimeError("Module ha_client.py not found")

    class_candidates = [
        "HAClient",
        "HomeAssistantClient",
        "HomeAssistantAPI",
        "Client",
    ]

    for cls_name in class_candidates:
        cls = getattr(ha_module, cls_name, None)
        if cls is None:
            continue
        try:
            return cls()
        except TypeError:
            base_url = os.getenv("HA_BASE_URL") or os.getenv("HA_URL")
            token = os.getenv("HA_TOKEN")
            try:
                return cls(base_url, token)
            except Exception:
                pass
        except Exception:
            pass

    if hasattr(ha_module, "get_state"):
        return ha_module

    raise RuntimeError("Could not build HA client from ha_client.py")


def call_first(module, names, *args, **kwargs):
    if module is None:
        raise RuntimeError("Module is not available")
    last_error = None
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_error = e
    if last_error:
        raise last_error
    raise AttributeError(f"None of functions exist: {names}")


try:
    ha = build_ha_client()
except Exception as e:
    print("HA init error:", e)
    traceback.print_exc()
    ha = None


def build_plants_full_text() -> str:
    return call_first(
        status_view_module,
        ["build_plants_full_text", "build_full_plants_text", "build_plants_text"],
        ha,
    )


def build_plants_low_text() -> str:
    return call_first(
        status_view_module,
        ["build_plants_low_text", "build_low_plants_text"],
        ha,
    )


def build_plants_high_text() -> str:
    return call_first(
        status_view_module,
        ["build_plants_high_text", "build_high_plants_text"],
        ha,
    )


def build_status_text() -> str:
    try:
        return call_first(
            status_view_module,
            ["build_status_text", "build_short_status_text", "build_main_status_text"],
            ha,
        )
    except Exception:
        return build_plants_full_text()


def build_critical_text() -> str:
    try:
        return call_first(
            status_view_module,
            ["build_critical_text", "build_critical_status_text"],
            ha,
        )
    except Exception:
        return build_plants_full_text()


def build_fire_text() -> str:
    try:
        return call_first(
            status_view_module,
            ["build_fire_text", "build_fire_status_text"],
            ha,
        )
    except Exception:
        pass

    try:
        return call_first(
            fire_safety_module,
            ["build_fire_text", "build_fire_status_text", "get_fire_status_text"],
            ha,
        )
    except Exception:
        return "Пожарный статус: отдельная функция не найдена, используй /critical или /plants."


def get_ai_analysis_text() -> str:
    if ai_service_module is None:
        return "AI-сервис недоступен"

    # Сначала пробуем без аргументов
    try:
        return call_first(
            ai_service_module,
            ["get_ai_analysis", "build_ai_analysis", "get_analysis_text"],
        )
    except Exception:
        pass

    # Потом пробуем с ha
    try:
        return call_first(
            ai_service_module,
            ["get_ai_analysis", "build_ai_analysis", "get_analysis_text"],
            ha,
        )
    except Exception as e:
        return f"AI-сервис недоступен: {e}"


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


def now_hhmm() -> str:
    return datetime.now().strftime("%H:%M")


def in_time_window(now_value: str, start_value: str, end_value: str) -> bool:
    now_m = int(now_value[:2]) * 60 + int(now_value[3:])
    start_m = int(start_value[:2]) * 60 + int(start_value[3:])
    end_m = int(end_value[:2]) * 60 + int(end_value[3:])

    if start_m <= end_m:
        return start_m <= now_m <= end_m
    return now_m >= start_m or now_m <= end_m


@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    safe_send(
        str(message.chat.id),
        "Greenhouse Bot v15\n\n"
        "Команды:\n"
        "/start\n"
        "/help\n"
        "/myid\n"
        "/status\n"
        "/critical\n"
        "/fire\n"
        "/plants_low\n"
        "/plants_high\n"
        "/plants\n"
        "/ai\n"
        "/send_now",
    )


@bot.message_handler(commands=["myid"])
def cmd_myid(message):
    safe_send(str(message.chat.id), f"Ваш chat_id: {message.chat.id}")


@bot.message_handler(commands=["status"])
def cmd_status(message):
    try:
        safe_send(str(message.chat.id), build_status_text())
    except Exception as e:
        safe_send(str(message.chat.id), f"Ошибка /status:\n{e}")


@bot.message_handler(commands=["critical"])
def cmd_critical(message):
    try:
        safe_send(str(message.chat.id), build_critical_text())
    except Exception as e:
        safe_send(str(message.chat.id), f"Ошибка /critical:\n{e}")


@bot.message_handler(commands=["fire"])
def cmd_fire(message):
    try:
        safe_send(str(message.chat.id), build_fire_text())
    except Exception as e:
        safe_send(str(message.chat.id), f"Ошибка /fire:\n{e}")


@bot.message_handler(commands=["plants_low"])
def cmd_plants_low(message):
    try:
        safe_send(str(message.chat.id), build_plants_low_text())
    except Exception as e:
        safe_send(str(message.chat.id), f"Ошибка /plants_low:\n{e}")


@bot.message_handler(commands=["plants_high"])
def cmd_plants_high(message):
    try:
        safe_send(str(message.chat.id), build_plants_high_text())
    except Exception as e:
        safe_send(str(message.chat.id), f"Ошибка /plants_high:\n{e}")


@bot.message_handler(commands=["plants"])
def cmd_plants(message):
    try:
        safe_send(str(message.chat.id), build_plants_full_text())
    except Exception as e:
        safe_send(str(message.chat.id), f"Ошибка /plants:\n{e}")


@bot.message_handler(commands=["ai"])
def cmd_ai(message):
    try:
        safe_send(str(message.chat.id), "🧠 Оценка теплицы:\n\n" + get_ai_analysis_text())
    except Exception as e:
        safe_send(str(message.chat.id), f"Ошибка /ai:\n{e}")


@bot.message_handler(commands=["send_now"])
def cmd_send_now(message):
    try:
        text = "⏰ Плановый отчёт теплицы\n\n"
        text += "🌿 Подробный статус:\n\n"
        text += build_plants_full_text()
        text += "\n\n🧠 Оценка теплицы:\n\n"
        text += get_ai_analysis_text()
        safe_send(str(message.chat.id), text)
    except Exception as e:
        safe_send(str(message.chat.id), f"Ошибка /send_now:\n{e}")


def planned_reports_loop():
    sent_keys = set()
    while True:
        try:
            current = now_hhmm()
            today = datetime.now().strftime("%Y-%m-%d")
            for hhmm in STATUS_PUSH_TIMES:
                key = f"{today}_{hhmm}"
                if current == hhmm and key not in sent_keys:
                    text = "⏰ Плановый отчёт теплицы\n\n"
                    text += "🌿 Подробный статус:\n\n"
                    text += build_plants_full_text()
                    text += "\n\n🧠 Оценка теплицы:\n\n"
                    text += get_ai_analysis_text()
                    safe_send(TELEGRAM_CHAT_ID, text)
                    sent_keys.add(key)
            if len(sent_keys) > 20:
                sent_keys = {x for x in sent_keys if x.startswith(today)}
        except Exception:
            traceback.print_exc()
        time.sleep(10)


def night_monitor_loop():
    if not NIGHT_MONITOR_ENABLED:
        return

    last_sent_key = None
    while True:
        try:
            current = now_hhmm()
            if in_time_window(current, NIGHT_MONITOR_START, NIGHT_MONITOR_END):
                minute = datetime.now().minute
                if minute % NIGHT_MONITOR_MINUTES == 0:
                    send_key = datetime.now().strftime("%Y-%m-%d %H:%M")
                    if send_key != last_sent_key:
                        text = "🧪 Ночной мониторинг\n\n" + build_plants_full_text()
                        safe_send(NIGHT_MONITOR_CHAT_ID, text)
                        last_sent_key = send_key
                        time.sleep(65)
        except Exception:
            traceback.print_exc()
        time.sleep(5)


def main():
    print("Bot v15 started")
    print("PUSH_TIMES =", STATUS_PUSH_TIMES)
    print("TELEGRAM_CHAT_ID =", TELEGRAM_CHAT_ID)

    threading.Thread(target=planned_reports_loop, daemon=True).start()
    threading.Thread(target=night_monitor_loop, daemon=True).start()

    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=20)
        except Exception:
            traceback.print_exc()
            time.sleep(5)


if __name__ == "__main__":
    main()
