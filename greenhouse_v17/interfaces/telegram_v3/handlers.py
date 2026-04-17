from __future__ import annotations

from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from greenhouse_v17.core.intent.intent_router import route_text
from greenhouse_v17.services.mode_service import get_mode, set_mode
from greenhouse_v17.services.action_service import execute_action
from greenhouse_v17.services.ask_service import load_ask_state, clear_ask_state

def build_main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 Статус"), KeyboardButton("🤖 Режим"))
    kb.row(KeyboardButton("🌬 Верх ВКЛ"), KeyboardButton("🌬 Верх ВЫКЛ"))
    kb.row(KeyboardButton("🌬 Низ ВКЛ"), KeyboardButton("🌬 Низ ВЫКЛ"))
    kb.row(KeyboardButton("💧 Увлажнитель ВКЛ"), KeyboardButton("💧 Увлажнитель ВЫКЛ"))
    return kb

def build_ask_keyboard(action_key: str):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"ask:confirm:{action_key}"),
        InlineKeyboardButton("❌ Отмена", callback_data="ask:cancel"),
    )
    return kb

def _format_execution_result(res):
    status = res.get("status")
    mode = res.get("mode")
    msg = res.get("message", "")
    entity_id = res.get("entity_id")

    if status == "ask":
        return f"{msg}\nРежим: {mode}\nТребуется подтверждение."
    if status == "dry_run":
        return f"{msg}\nРежим: {mode}\n🧪 TEST: команда распознана, но не исполнена."
    if status == "blocked":
        return f"⛔ {msg}\nРежим: {mode}"
    if status == "unsupported":
        return f"⚠️ {msg}\nРежим: {mode}"
    if status in ("executed", "degraded"):
        verify = res.get("verify", {})
        verify_line = "✅ verify ok" if verify.get("ok") else f"⚠️ verify failed (actual={verify.get('actual_state')})"
        return (
            f"{msg}\n"
            f"Режим: {mode}\n"
            f"Устройство: {entity_id}\n"
            f"{verify_line}"
        )
    return str(res)

def register_v3_handlers(bot):
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        bot.send_message(
            message.chat.id,
            "GREENHOUSE v17 / TG v3\n\nЕдиный router + ASK + execution + verify.",
            reply_markup=build_main_menu(),
        )

    @bot.message_handler(commands=["mode"])
    def cmd_mode(message):
        bot.send_message(
            message.chat.id,
            f"Текущий режим: {get_mode()}\n\n"
            "/mode_manual\n/mode_test\n/mode_ask\n/mode_auto\n/mode_autopilot",
            reply_markup=build_main_menu(),
        )

    @bot.message_handler(commands=["mode_manual"])
    def cmd_mode_manual(message):
        set_mode("MANUAL")
        bot.send_message(message.chat.id, "Режим переключен: MANUAL", reply_markup=build_main_menu())

    @bot.message_handler(commands=["mode_test"])
    def cmd_mode_test(message):
        set_mode("TEST")
        bot.send_message(message.chat.id, "Режим переключен: TEST", reply_markup=build_main_menu())

    @bot.message_handler(commands=["mode_ask"])
    def cmd_mode_ask(message):
        set_mode("ASK")
        bot.send_message(message.chat.id, "Режим переключен: ASK", reply_markup=build_main_menu())

    @bot.message_handler(commands=["mode_auto"])
    def cmd_mode_auto(message):
        set_mode("AUTO")
        bot.send_message(message.chat.id, "Режим переключен: AUTO", reply_markup=build_main_menu())

    @bot.message_handler(commands=["mode_autopilot"])
    def cmd_mode_autopilot(message):
        set_mode("AUTOPILOT")
        bot.send_message(message.chat.id, "Режим переключен: AUTOPILOT", reply_markup=build_main_menu())

    @bot.callback_query_handler(func=lambda c: c.data.startswith("ask:"))
    def on_ask_callback(call):
        if call.data == "ask:cancel":
            clear_ask_state()
            bot.answer_callback_query(call.id, "Отменено")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, "ASK отменён.", reply_markup=build_main_menu())
            return

        parts = call.data.split(":")
        if len(parts) != 3 or parts[1] != "confirm":
            bot.answer_callback_query(call.id, "Неверный callback")
            return

        action_key = parts[2]
        stored = load_ask_state()
        if not stored or stored.get("action_key") != action_key:
            bot.answer_callback_query(call.id, "ASK state не найден")
            bot.send_message(call.message.chat.id, "Не найдено ожидающее ASK-состояние.", reply_markup=build_main_menu())
            return

        res = execute_action(action_key, force_execute=True)
        clear_ask_state()
        bot.answer_callback_query(call.id, "Подтверждено")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, _format_execution_result(res), reply_markup=build_main_menu())

    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def handle_any_text(message):
        routed = route_text(message.text or "")
        intent_type = routed.get("intent_type")
        action_key = routed.get("action_key")

        if intent_type == "mode_status":
            return cmd_mode(message)

        if intent_type == "status":
            bot.send_message(
                message.chat.id,
                "Status layer ещё упрощён. Следующий шаг — нормальный status/snapshot поверх нового Core.",
                reply_markup=build_main_menu(),
            )
            return

        if intent_type == "device_action" and action_key:
            res = execute_action(action_key)
            if res.get("status") == "ask":
                bot.send_message(
                    message.chat.id,
                    _format_execution_result(res),
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    f"Подтвердить действие: {action_key}",
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    "Нажми подтверждение ниже:",
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    "ASK pending",
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    f"Действие: {action_key}",
                    reply_markup=build_main_menu(),
                )
                bot.send_message(
                    message.chat.id,
                    "Подтверждение:",
                    reply_markup=build_ask_keyboard(action_key),
                )
                return

            bot.send_message(
                message.chat.id,
                _format_execution_result(res),
                reply_markup=build_main_menu(),
            )
            return

        bot.send_message(
            message.chat.id,
            "Команда пока не подключена в новом пакете.",
            reply_markup=build_main_menu(),
        )
