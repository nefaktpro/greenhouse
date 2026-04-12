#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from reports import (
    build_status_report,
    build_critical_report,
    build_fire_report,
    build_plants_low_report,
    build_plants_high_report,
    build_plants_report,
    build_ai_report,
    build_send_now_report,
    build_alerts_report,
    build_safety_report,
)
from bot_menu import build_main_menu, build_cameras_menu
from cameras import get_camera, get_camera_name
from batteries import build_batteries_report
from devices_status import build_devices_groups_text, build_devices_groups_keyboard, build_group_report, build_group_keyboard, execute_device_action


def safe_send(bot, chat_id: str, text: str, reply_markup=None) -> None:
    if not chat_id:
        return
    text = text or "(пустой ответ)"
    limit = 3800
    first = True
    while text:
        chunk = text[:limit]
        bot.send_message(
            chat_id,
            chunk,
            reply_markup=reply_markup if first else None,
        )
        first = False
        text = text[limit:]


def register_handlers(bot):
    @bot.message_handler(commands=["start", "help"])
    def cmd_start(message):
        safe_send(
            bot,
            str(message.chat.id),
            "Greenhouse Bot v15\n\n"
            "Команды:\n"
            "/start\n"
            "/help\n"
            "/myid\n"
            "/status\n"
            "/critical\n"
            "/alerts\n"
            "/safety\n"
            "/plants_low\n"
            "/plants_high\n"
            "/plants\n"
            "/ai\n"
            "/send_now\n"
            "/devices\n"
            "\n"
            "Служебные:\n"
            "/fire\n"
            "/batteries",
            reply_markup=build_main_menu(),
        )

    @bot.message_handler(commands=["myid"])
    def cmd_myid(message):
        safe_send(bot, str(message.chat.id), f"Ваш chat_id: {message.chat.id}")

    @bot.message_handler(commands=["status"])
    def cmd_status(message):
        try:
            safe_send(bot, str(message.chat.id), build_status_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /status:\n{e}")

    @bot.message_handler(commands=["critical"])
    def cmd_critical(message):
        try:
            safe_send(bot, str(message.chat.id), build_critical_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /critical:\n{e}")

    @bot.message_handler(commands=["alerts"])
    def cmd_alerts(message):
        try:
            safe_send(bot, str(message.chat.id), build_alerts_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /alerts:\n{e}")

    @bot.message_handler(commands=["safety"])
    def cmd_safety(message):
        try:
            safe_send(bot, str(message.chat.id), build_safety_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /safety:\n{e}")

    @bot.message_handler(commands=["fire"])
    def cmd_fire(message):
        try:
            safe_send(bot, str(message.chat.id), build_fire_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /fire:\n{e}")

    @bot.message_handler(commands=["plants_low"])
    def cmd_plants_low(message):
        try:
            safe_send(bot, str(message.chat.id), build_plants_low_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /plants_low:\n{e}")

    @bot.message_handler(commands=["plants_high"])
    def cmd_plants_high(message):
        try:
            safe_send(bot, str(message.chat.id), build_plants_high_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /plants_high:\n{e}")

    @bot.message_handler(commands=["plants"])
    def cmd_plants(message):
        try:
            safe_send(bot, str(message.chat.id), build_plants_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /plants:\n{e}")

    @bot.message_handler(commands=["ai"])
    def cmd_ai(message):
        try:
            safe_send(bot, str(message.chat.id), "🧠 Оценка теплицы:\n\n" + build_ai_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /ai:\n{e}")

    @bot.message_handler(commands=["send_now"])
    def cmd_send_now(message):
        try:
            safe_send(bot, str(message.chat.id), build_send_now_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /send_now:\n{e}")

    @bot.message_handler(commands=["batteries"])
    def cmd_batteries(message):
        try:
            safe_send(bot, str(message.chat.id), build_batteries_report())
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /batteries:\n{e}")

    @bot.message_handler(commands=["devices"])
    def cmd_devices(message):
        try:
            bot.send_message(
                message.chat.id,
                build_devices_groups_text(),
                reply_markup=build_devices_groups_keyboard(),
            )
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /devices:\n{e}")



    @bot.callback_query_handler(func=lambda call: call.data == "noop_devices")
    def handle_noop_devices(call):
        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda call: call.data == "devmenu")
    def handle_devices_menu(call):
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=build_devices_groups_text(),
                reply_markup=build_devices_groups_keyboard(),
            )
            bot.answer_callback_query(call.id)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:150]}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("devgrp|"))
    def handle_devices_group(call):
        try:
            _, group = call.data.split("|", 1)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=build_group_report(group),
                reply_markup=build_group_keyboard(group),
            )
            bot.answer_callback_query(call.id)
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:150]}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("devrefresh|"))
    def handle_devices_refresh(call):
        try:
            _, group = call.data.split("|", 1)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=build_group_report(group),
                reply_markup=build_group_keyboard(group),
            )
            bot.answer_callback_query(call.id, "Обновлено")
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:150]}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("devctl|"))
    def handle_device_control(call):
        try:
            _, action, code, group = call.data.split("|", 3)
            ok, msg = execute_device_action(code, action)
            bot.answer_callback_query(call.id, "Готово" if ok else msg[:150])

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=build_group_report(group),
                reply_markup=build_group_keyboard(group),
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:150]}")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("camera::"))
    def handle_camera_callback(call):
        camera_id = call.data.split("camera::", 1)[1]
        camera_name = get_camera_name(camera_id)

        bot.answer_callback_query(call.id, "Получаю фото...")
        try:
            img = get_camera(camera_id)
            if img:
                bot.send_chat_action(call.message.chat.id, "upload_photo")
                bot.send_photo(call.message.chat.id, img, caption=camera_name)
            else:
                bot.send_message(call.message.chat.id, f"❌ {camera_name} не отвечает")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"Ошибка камеры {camera_name}:\n{e}")

    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def handle_menu_buttons(message):
        text = (message.text or "").strip()

        if text == "🌿 Растения":
            return cmd_plants(message)
        elif text == "📊 Статус":
            return cmd_status(message)
        elif text == "🚨 Критично":
            return cmd_critical(message)
        elif text == "🤖 AI":
            return cmd_ai(message)
        elif text == "📷 Камеры":
            bot.send_message(
                message.chat.id,
                "📷 Выбери камеру:",
                reply_markup=build_cameras_menu(),
            )
            return
        elif text == "🛡 Безопасность":
            return cmd_safety(message)
        elif text == "🔌 Устройства":
            return cmd_devices(message)
