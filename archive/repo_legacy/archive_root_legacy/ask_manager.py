#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime
from telebot import types
from services.paths import ASK_STATE_PATH

ASK_STATE_FILE = str(ASK_STATE_PATH)


def save_ask_state(data):
    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": data,
    }
    with open(ASK_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def load_ask_state():
    if not os.path.exists(ASK_STATE_FILE):
        return None

    try:
        with open(ASK_STATE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload.get("data")
    except Exception:
        return None


def clear_ask_state():
    if os.path.exists(ASK_STATE_FILE):
        try:
            os.remove(ASK_STATE_FILE)
        except Exception:
            pass


def build_ask_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ OK", callback_data="ask|ok"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="ask|cancel"),
    )
    return kb


def build_action_ask_payload(
    *,
    action_key: str,
    target_role: str,
    operation: str,
    mode_flags: dict,
    validation: dict,
):
    return {
        "kind": "execution_action",
        "action_key": action_key,
        "target_role": target_role,
        "operation": operation,
        "mode_flags": mode_flags,
        "validation": validation,
        "status": "pending_confirmation",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_pending_action_key():
    state = load_ask_state()
    if not state:
        return None

    if state.get("kind") != "execution_action":
        return None

    return state.get("action_key")
