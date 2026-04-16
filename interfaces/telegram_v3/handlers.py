from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from execution.engine.execution_engine import execute_action_key
from mode_manager import get_mode, set_mode


def build_main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("📊 Статус"),
        KeyboardButton("🤖 Режим"),
    )
    kb.row(
        KeyboardButton("🌬 Верх ВКЛ"),
        KeyboardButton("🛑 Верх ВЫКЛ"),
    )
    kb.row(
        KeyboardButton("🌬 Низ ВКЛ"),
        KeyboardButton("🛑 Низ ВЫКЛ"),
    )
    return kb


def _format_results(title: str, mode: str, results):
    success_count = sum(1 for r in results if getattr(r, "success", False))
    total_count = len(results)

    lines = [
        title,
        f"Режим: {mode}",
        f"Успешно: {success_count}/{total_count}",
    ]

    for r in results:
        icon = "✅" if getattr(r, "success", False) else "❌"
        entity = getattr(r, "entity_id", None) or "-"
        msg = getattr(r, "message", "") or "-"
        lines.append(f"{icon} {entity} — {msg}")

    return "\n".join(lines)


def register_v3_handlers(bot):
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        bot.send_message(
            message.chat.id,
            "GREENHOUSE v17 / TG v3\n\nЧистый новый контур запущен.",
            reply_markup=build_main_menu(),
        )

    @bot.message_handler(commands=["mode"])
    def cmd_mode(message):
        current_mode = get_mode()
        bot.send_message(
            message.chat.id,
            f"Текущий режим: {current_mode}\n\n"
            "Команды:\n"
            "/mode_manual\n"
            "/mode_test\n"
            "/mode_ask\n"
            "/mode_auto\n"
            "/mode_autopilot"
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
            bot.send_message(
                message.chat.id,
                f"{title}\n🧪 TEST: команда распознана, но не исполнена."
            )
            return

        results = execute_action_key(action_key, force_execute=True)
        bot.send_message(
            message.chat.id,
            _format_results(title, mode, results),
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
            bot.send_message(
                message.chat.id,
                "📊 Статус v17 пока минимальный. Следующий шаг — подключить новый status layer.",
                reply_markup=build_main_menu(),
            )
            return

        bot.send_message(
            message.chat.id,
            "Команда пока не подключена в TG v3.",
            reply_markup=build_main_menu(),
        )
