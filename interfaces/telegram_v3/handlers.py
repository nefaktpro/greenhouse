import time
import requests

from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from execution.engine.execution_engine import execute_action_key
from mode_manager import get_mode, set_mode
from config import HOME_ASSISTANT_URL, HOME_ASSISTANT_TOKEN, REQUEST_TIMEOUT


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


def _ha_headers():
    return {
        "Authorization": f"Bearer {HOME_ASSISTANT_TOKEN}",
        "Content-Type": "application/json",
    }


def read_entity_state(entity_id: str):
    if not entity_id:
        return None, "empty entity_id"

    try:
        r = requests.get(
            f"{HOME_ASSISTANT_URL}/api/states/{entity_id}",
            headers=_ha_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("state"), None
    except Exception as e:
        return None, str(e)


def verify_entity_state(entity_id: str, expected_state: str, retries: int = 4, delay_seconds: float = 1.5):
    last_state = None
    last_error = None

    for _ in range(retries):
        state, err = read_entity_state(entity_id)
        last_state = state
        last_error = err

        if err is None and str(state).lower() == expected_state.lower():
            return True, state, None

        time.sleep(delay_seconds)

    return False, last_state, last_error


def expected_state_for_action(action_key: str):
    mapping = {
        "fan_top_on": "on",
        "fan_top_off": "off",
        "fan_bottom_on": "on",
        "fan_bottom_off": "off",
    }
    return mapping.get(action_key)


def _format_results(title: str, mode: str, action_key: str, results):
    success_count = sum(1 for r in results if getattr(r, "success", False))
    total_count = len(results)

    lines = [
        title,
        f"Режим: {mode}",
        f"Успешно: {success_count}/{total_count}",
    ]

    expected_state = expected_state_for_action(action_key)

    for r in results:
        exec_ok = getattr(r, "success", False)
        entity = getattr(r, "entity_id", None) or "-"
        msg = getattr(r, "message", "") or "-"

        if not exec_ok:
            lines.append(f"❌ {entity} — {msg}")
            continue

        if not expected_state or entity == "-":
            lines.append(f"✅ {entity} — {msg}")
            continue

        verified, actual_state, verify_error = verify_entity_state(entity, expected_state)

        if verified:
            lines.append(f"✅ {entity} — Verified (state={actual_state})")
        else:
            if verify_error:
                lines.append(
                    f"⚠️ {entity} — Команда отправлена, но verify не подтвердился "
                    f"(state={actual_state}, error={verify_error})"
                )
            else:
                lines.append(
                    f"⚠️ {entity} — Команда отправлена, но состояние не подтвердилось "
                    f"(expected={expected_state}, actual={actual_state})"
                )

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
            _format_results(title, mode, action_key, results),
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
