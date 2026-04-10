#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telebot import types
from cameras import CAMERAS


def _camera_to_pair(item):
    if isinstance(item, dict):
        entity_id = (
            item.get("entity_id")
            or item.get("id")
            or item.get("camera")
            or ""
        )
        camera_name = (
            item.get("name")
            or item.get("title")
            or entity_id
        )
        return entity_id, camera_name

    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return item[0], item[1]

    return "", str(item)


def build_main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🌿 Растения", "📊 Статус")
    kb.row("🛡 Безопасность", "🚨 Критично")
    kb.row("🤖 AI", "🤖 Режим")
    kb.row("📷 Камеры", "🔌 Устройства")
    return kb


def build_cameras_menu():
    kb = types.InlineKeyboardMarkup()
    for item in CAMERAS:
        entity_id, camera_name = _camera_to_pair(item)
        if not entity_id:
            continue
        kb.add(
            types.InlineKeyboardButton(
                str(camera_name),
                callback_data=f"camera::{entity_id}"
            )
        )
    return kb
