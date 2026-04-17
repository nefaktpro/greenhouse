#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from telebot import types
from cameras import CAMERAS


def build_main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🌿 Растения", "📊 Статус")
    kb.row("🚨 Критично", "🤖 AI")
    kb.row("📷 Камеры", "🛡 Безопасность")
    kb.row("🔌 Устройства")
    return kb


def _camera_to_pair(item):
    # dict format
    if isinstance(item, dict):
        entity_id = (
            item.get("entity_id")
            or item.get("id")
            or item.get("camera_id")
            or item.get("entity")
        )
        camera_name = (
            item.get("name")
            or item.get("title")
            or item.get("label")
            or entity_id
        )
        return entity_id, camera_name

    # tuple/list format
    if isinstance(item, (list, tuple)):
        if len(item) >= 2:
            return item[0], item[1]

    # fallback
    return str(item), str(item)


def build_cameras_menu():
    kb = types.InlineKeyboardMarkup()
    for item in CAMERAS:
        entity_id, camera_name = _camera_to_pair(item)
        kb.add(types.InlineKeyboardButton(str(camera_name), callback_data=f"camera::{entity_id}"))
    return kb
