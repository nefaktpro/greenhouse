from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from greenhouse_v17.services.mode_service import get_mode, set_mode
from greenhouse_v17.services.ha_client import call_switch
from greenhouse_v17.registry.loader import resolve_action_to_entity


def build_main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 Статус"), KeyboardButton("🤖 Режим"))
    kb.row(KeyboardButton("🌬 Верх ВКЛ"), KeyboardButton("🛑 Верх ВЫКЛ"))
    kb.row(KeyboardButton("🌬 Низ ВКЛ"), KeyboardButton("🛑 Низ ВЫКЛ"))
    return kb


def _run_action(action_key: str):
    resolved = resolve_action_to_entity(action_key)
    entity_id = resolved["entity_id"]
    operation = resolved["operation"]

    result = call_switch(entity_id, turn_on=(operation == "turn_on"))
    return resolved, result


def register_v3_handlers(bot):
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        bot.send_message(
            message.chat.id,
            "GREENHOUSE v17 / TG v3\n\nЧистый новый пакетный контур запущен.",
            reply_markup=build_main_menu(),
        )

    @bot.message_handler(commands=["mode"])
    def cmd_mode(message):
        bot.send_message(
            message.chat.id,
            f"Текущий режим: {get_mode()}\n\n"
            "/mode_manual\n/mode_test\n/mode_ask\n/mode_auto\n/mode_autopilot"
        )

    @bot.message_handler(commands=["mode_manual"])
    def cmd_mode_manual(message):
        set_mode("MANUAL")
        bot.send_message(message.chat.id, "Режим переключен: MANUAL")

    @bot.message_handler(commands=["mode_test"])
    def cmd_mode_test(message):
        set_mode("TEST")
        bot.send_message(message.chat.id, "Режим переключен: TEST")

    @bot.message_handler(commands=["mode_ask"])
    def cmd_mode_ask(message):
        set_mode("ASK")
        bot.send_message(message.chat.id, "Режим переключен: ASK")

    @bot.message_handler(commands=["mode_auto"])
    def cmd_mode_auto(message):
        set_mode("AUTO")
        bot.send_message(message.chat.id, "Режим переключен: AUTO")

    @bot.message_handler(commands=["mode_autopilot"])
    def cmd_mode_autopilot(message):
        set_mode("AUTOPILOT")
        bot.send_message(message.chat.id, "Режим переключен: AUTOPILOT")

    def run_action(message, action_key: str, title: str):
        mode = get_mode()

        if mode == "TEST":
            bot.send_message(message.chat.id, f"{title}\n🧪 TEST: команда распознана, но не исполнена.")
            return

        if mode == "ASK":
            bot.send_message(message.chat.id, f"{title}\n⛔ ASK пока не подключен в новом пакете. Переключись в MANUAL.")
            return

        try:
            resolved, result = _run_action(action_key)
            bot.send_message(
                message.chat.id,
                f"{title}\n"
                f"Режим: {mode}\n"
                f"✅ {resolved['entity_id']} — HA command sent ({result['service']})",
                reply_markup=build_main_menu(),
            )
        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"{title}\n❌ Ошибка: {e}",
                reply_markup=build_main_menu(),
            )

    @bot.message_handler(commands=["fan_top_on"])
    def cmd_fan_top_on(message):
        run_action(message, "fan_top_on", "🌬 Верх: включить вентиляторы")

    @bot.message_handler(commands=["fan_top_off"])
    def cmd_fan_top_off(message):
        run_action(message, "fan_top_off", "🛑 Верх: выключить вентиляторы")

    @bot.message_handler(commands=["fan_low_on"])
    def cmd_fan_low_on(message):
        run_action(message, "fan_bottom_on", "🌬 Низ: включить вентиляторы")

    @bot.message_handler(commands=["fan_low_off"])
    def cmd_fan_low_off(message):
        run_action(message, "fan_bottom_off", "🛑 Низ: выключить вентиляторы")

    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def handle_buttons(message):
        text = (message.text or "").strip()

        if text == "🤖 Режим":
            return cmd_mode(message)
        if text == "🌬 Верх ВКЛ":
            return run_action(message, "fan_top_on", "🌬 Верх: включить вентиляторы")
        if text == "🛑 Верх ВЫКЛ":
            return run_action(message, "fan_top_off", "🛑 Верх: выключить вентиляторы")
        if text == "🌬 Низ ВКЛ":
            return run_action(message, "fan_bottom_on", "🌬 Низ: включить вентиляторы")
        if text == "🛑 Низ ВЫКЛ":
            return run_action(message, "fan_bottom_off", "🛑 Низ: выключить вентиляторы")
        if text == "📊 Статус":
            bot.send_message(message.chat.id, "📊 Новый status layer будет подключен следующим шагом.", reply_markup=build_main_menu())
            return

        bot.send_message(message.chat.id, "Команда пока не подключена в новом пакете.", reply_markup=build_main_menu())
