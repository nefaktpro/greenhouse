import json
import os

STATE_FILE = "/home/mi/greenhouse_v2/system_state.json"

DEFAULT_STATE = {
    "mode": "TEST"
}

MODE_CONFIG = {
    "MANUAL": {
        "execute": False,
        "log": False,
        "ask": False,
        "ai_control": False,
        "title": "MANUAL",
        "description": "Всё вручную. Система ничего не предлагает и ничего не выполняет."
    },
    "TEST": {
        "execute": False,
        "log": True,
        "ask": False,
        "ai_control": False,
        "title": "TEST",
        "description": "Система считает, что бы сделала, но ничего не включает."
    },
    "AUTO": {
        "execute": True,
        "log": True,
        "ask": False,
        "ai_control": False,
        "title": "AUTO",
        "description": "Система работает по правилам и выполняет действия автоматически."
    },
    "ASK": {
        "execute": False,
        "log": True,
        "ask": True,
        "ai_control": False,
        "title": "ASK",
        "description": "Система предлагает действие и ждёт подтверждение."
    },
    "AUTOPILOT": {
        "execute": True,
        "log": True,
        "ask": False,
        "ai_control": True,
        "title": "AUTOPILOT",
        "description": "AI сам анализирует и управляет системой."
    }
}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def load_state():
    if not os.path.exists(STATE_FILE):
        save_state(DEFAULT_STATE)
        return DEFAULT_STATE.copy()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        save_state(DEFAULT_STATE)
        return DEFAULT_STATE.copy()

    if not isinstance(state, dict):
        save_state(DEFAULT_STATE)
        return DEFAULT_STATE.copy()

    mode = state.get("mode", "TEST")
    if mode not in MODE_CONFIG:
        state["mode"] = "TEST"
        save_state(state)

    return state


def get_mode():
    state = load_state()
    mode = state.get("mode", "TEST")
    if mode not in MODE_CONFIG:
        return "TEST"
    return mode


def set_mode(new_mode):
    if new_mode not in MODE_CONFIG:
        raise ValueError(f"Unsupported mode: {new_mode}")

    state = load_state()
    state["mode"] = new_mode
    save_state(state)
    return state


def get_mode_config(mode=None):
    if mode is None:
        mode = get_mode()
    return MODE_CONFIG.get(mode, MODE_CONFIG["TEST"])


def get_mode_status_text():
    mode = get_mode()
    config = get_mode_config(mode)

    lines = [
        "🤖 Режим системы",
        "",
        f"Текущий режим: {mode}",
        f"Описание: {config.get('description', '-')}",
        "",
        "Статусы:",
        f"• выполнение действий: {'да' if config.get('execute') else 'нет'}",
        f"• логирование решений: {'да' if config.get('log') else 'нет'}",
        f"• ожидание подтверждения: {'да' if config.get('ask') else 'нет'}",
        f"• AI-управление: {'да' if config.get('ai_control') else 'нет'}",
    ]
    return "\n".join(lines)


def build_mode_text():
    return get_mode_status_text()


def build_mode_keyboard():
    from telebot import types

    current = get_mode()

    def label(mode_name):
        return f"✅ {mode_name}" if current == mode_name else mode_name

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(label("MANUAL"), callback_data="mode|MANUAL"),
        types.InlineKeyboardButton(label("TEST"), callback_data="mode|TEST"),
    )
    kb.add(
        types.InlineKeyboardButton(label("AUTO"), callback_data="mode|AUTO"),
        types.InlineKeyboardButton(label("ASK"), callback_data="mode|ASK"),
    )
    kb.add(
        types.InlineKeyboardButton(label("AUTOPILOT"), callback_data="mode|AUTOPILOT"),
    )
    return kb
