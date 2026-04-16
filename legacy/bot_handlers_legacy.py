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
from mode_manager import build_mode_text, build_mode_keyboard, set_mode, get_mode
from test_mode import build_test_report
from decision_logger import load_recent_logs, log_decisions
from ask_manager import save_ask_state, load_ask_state, clear_ask_state, build_ask_keyboard
from ask_manager import get_pending_action_key
from execution.engine.execution_engine import execute_action_key
from test_mode import get_ask_payload
from action_executor import execute_decisions
from ask_manager import load_ask_state
from ai_mode_support import build_ai_comment_for_decisions
from chat.chat_router import handle_chat_message
ACTION_MAP = {
    "water_low": "💧 Полив низа",
    "water_top": "💧 Полив верха",
    "humidify": "🌫 Увлажнение",
    "none": "—"
}


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




    def _run_manual_executor(message, action_name, title):
        try:
            current_mode = get_mode()

            if current_mode == "TEST":
                bot.send_message(
                    message.chat.id,
                    f"{title}\n🧪 TEST: команда распознана, но не исполнена."
                )
                return

            results = execute_action_key(action_name, force_execute=True)

            success_count = sum(1 for r in results if getattr(r, "success", False))
            total_count = len(results)

            log_decisions(
                mode=current_mode,
                decisions=[{
                    "action": action_name,
                    "reason": "manual_command",
                    "results": [str(r) for r in results],
                }],
                source="manual_command",
            )

            lines = [
                title,
                f"Режим: {current_mode}",
                f"Успешно: {success_count}/{total_count}",
            ]

            for r in results:
                icon = "✅" if getattr(r, "success", False) else "❌"
                entity = getattr(r, "entity_id", None) or "-"
                msg = getattr(r, "message", "") or "-"
                lines.append(f"{icon} {entity} — {msg}")

            bot.send_message(message.chat.id, "\n".join(lines))
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка manual fan command:\n{e}")

    @bot.message_handler(commands=["fan_top_on"])
    def cmd_fan_top_on(message):
        _run_manual_executor(message, "fan_top_on", "🌬 Верх: включить вентиляторы")

    @bot.message_handler(commands=["fan_top_off"])
    def cmd_fan_top_off(message):
        _run_manual_executor(message, "fan_top_off", "🛑 Верх: выключить вентиляторы")

    @bot.message_handler(commands=["fan_low_on"])
    def cmd_fan_low_on(message):
        _run_manual_executor(message, "fan_low_on", "🌬 Низ: включить вентиляторы")

    @bot.message_handler(commands=["fan_low_off"])
    def cmd_fan_low_off(message):
        _run_manual_executor(message, "fan_low_off", "🛑 Низ: выключить вентиляторы")

    @bot.message_handler(commands=["test_now"])
    def cmd_test_now(message):
        try:
            report = build_test_report()

            if get_mode() == "ASK":
                payload = get_ask_payload()
                save_ask_state(payload)

                bot.send_message(
                    message.chat.id,
                    report,
                    reply_markup=build_ask_keyboard(),
                )
            else:
                safe_send(bot, str(message.chat.id), report)

        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /test_now:\n{e}")

    @bot.message_handler(commands=["ask_ai"])
    def cmd_ask_ai(message):
        try:
            state = load_ask_state()

            if not state:
                bot.send_message(
                    message.chat.id,
                    "🤖 DeepSeek\n\nНет активного ASK-предложения. Сначала запусти /test_now в режиме ASK."
                )
                return

            mode = state.get("mode", "ASK")
            decisions = state.get("decisions", [])

            text_out = build_ai_comment_for_decisions(mode, decisions)
            bot.send_message(message.chat.id, text_out)

        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /ask_ai:\n{e}")

    @bot.message_handler(commands=["mode"])
    def cmd_mode(message):
        try:
            bot.send_message(
                message.chat.id,
                build_mode_text(),
                reply_markup=build_mode_keyboard(),
            )
        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /mode:\n{e}")

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





    @bot.callback_query_handler(func=lambda call: call.data.startswith("ask|"))
    def handle_ask_decision(call):
        try:
            _, action = call.data.split("|", 1)
            state = load_ask_state()

            if not state:
                bot.answer_callback_query(call.id, "Нет активного предложения")
                return

            if action == "ok":
                bot.answer_callback_query(call.id, "Подтверждено")

                if state.get("kind") == "execution_action":
                    action_key = state.get("action_key")
                    results = execute_action_key(action_key, force_execute=True)

                    success_count = sum(1 for r in results if getattr(r, "success", False))
                    total_count = len(results)

                    log_decisions(
                        mode="ASK",
                        decisions=[
                            {
                                "action": action_key,
                                "reason": "ask_confirmed_execution_action",
                                "results": [str(r) for r in results],
                            }
                        ],
                        source="ask_confirmed"
                    )

                    lines = [
                        "✅ Подтверждено.",
                        f"Action: {action_key}",
                        f"Успешно: {success_count}/{total_count}",
                    ]

                    for r in results:
                        icon = "🟢" if getattr(r, "success", False) else "❌"
                        entity = getattr(r, "entity_id", None) or "-"
                        msg = getattr(r, "message", "")
                        lines.append(f"{icon} {entity} — {msg}")

                    bot.send_message(call.message.chat.id, "\n".join(lines))

                else:
                    from legacy.decision_action_bridge import extract_action_keys_from_decisions

                    decisions = state.get("decisions", []) or []
                    action_keys = extract_action_keys_from_decisions(decisions)

                    if action_keys:
                        execution_results = []
                        lines = ["✅ ASK подтверждён. Запускаю через новый execution pipeline:"]

                        for action_key in action_keys:
                            results = execute_action_key(action_key, force_execute=True)
                            execution_results.extend(results)

                            for r in results:
                                icon = "🟢" if getattr(r, "success", False) else "❌"
                                entity = getattr(r, "entity_id", None) or "-"
                                msg = getattr(r, "message", "") or "-"
                                lines.append(f"{icon} {action_key} → {entity} — {msg}")

                        log_decisions(
                            mode="ASK",
                            decisions=[
                                {
                                    "action": ak,
                                    "reason": "ask_confirmed_bridge",
                                }
                                for ak in action_keys
                            ],
                            source="ask_confirmed_bridge"
                        )

                        bot.send_message(
                            call.message.chat.id,
                            "\n".join(lines),
                        )

                    else:
                        confirmed = execute_decisions(
                            decisions,
                            dry_run=True
                        )

                        log_decisions(
                            mode="ASK",
                            decisions=confirmed,
                            source="ask_confirmed_legacy_dry_run"
                        )

                        bot.send_message(
                            call.message.chat.id,
                            "⚠️ ASK подтверждён, но для этих решений ещё нет bridge в новый execution layer.\n"
                            "Пока оставлен legacy dry-run fallback."
                        )

            elif action == "cancel":
                bot.answer_callback_query(call.id, "Отменено")

                if state.get("kind") == "execution_action":
                    log_decisions(
                        mode="ASK",
                        decisions=[
                            {
                                "action": state.get("action_key"),
                                "reason": "ask_cancelled_execution_action",
                            }
                        ],
                        source="ask_cancelled"
                    )
                else:
                    log_decisions(
                        mode="ASK",
                        decisions=state.get("decisions", []),
                        source="ask_cancelled"
                    )

                bot.send_message(
                    call.message.chat.id,
                    "❌ Предложение отменено пользователем."
                )

            clear_ask_state()

        except Exception as e:
            try:
                bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:150]}")
            except Exception:
                pass

    @bot.callback_query_handler(func=lambda call: call.data.startswith("mode|"))
    def handle_mode_change(call):
        try:
            _, mode = call.data.split("|", 1)

            bot.answer_callback_query(call.id, f"Режим: {mode}")
            set_mode(mode)

            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=build_mode_text(),
                reply_markup=build_mode_keyboard(),
            )
        except Exception as e:
            try:
                bot.answer_callback_query(call.id, f"Ошибка: {str(e)[:150]}")
            except Exception:
                pass

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

    @bot.message_handler(commands=["decisions"])
    def cmd_decisions(message):
        logs = load_recent_logs(5)

        if not logs:
            bot.send_message(message.chat.id, "📘 Журнал решений пуст.")
            return

        ACTION_TEXT = {
            "water_low": "💧 Полить низ",
            "water_top": "💧 Полить верх",
            "humidify_low": "🌫 Увлажнить низ",
            "humidify_top": "🌫 Увлажнить верх",
            "fan_low_on": "🌬 Включить вентиляторы низа",
            "fan_low_off": "🛑 Выключить вентиляторы низа",
            "fan_top_on": "🌬 Включить вентиляторы верха",
            "fan_top_off": "🛑 Выключить вентиляторы верха",
        }

        SENSOR_LABELS = {
            "11": "Низ",
            "16": "Верх",
            "21_humidity": "Листья низ",
            "22_humidity": "Листья верх",
            "21_temp": "Темп. низ",
            "22_temp": "Темп. верх",
        }

        parts = ["📘 Последние решения", ""]

        for entry in reversed(logs):
            ts = entry.get("timestamp", "-")
            mode = entry.get("mode", "-")
            source = entry.get("source", "unknown")
            decisions = entry.get("decisions", [])

            SOURCE_TEXT = {
                "manual_test": "вручную",
                "scheduler_test": "по расписанию",
                "ask_proposal": "предложение",
                "ask_confirmed": "подтверждено",
                "ask_cancelled": "отменено",
                "auto_cycle": "авто",
                "autopilot_ai": "AI",
                "unknown": "источник не указан",
            }

            filtered = [d for d in decisions if d.get("action") != "none"]

            if not filtered:
                continue

            time_short = ts.split(" ")[1][:5] if " " in ts else ts
            source_text = SOURCE_TEXT.get(source, source)
            parts.append(f"🕒 {time_short} — {mode} / {source_text}")

            for d in filtered:
                raw = d.get("action")
                sensor = d.get("sensor")

                if raw == "humidify":
                    if sensor == "21":
                        action = ACTION_TEXT["humidify_low"]
                    elif sensor == "22":
                        action = ACTION_TEXT["humidify_top"]
                    else:
                        action = "🌫 Увлажнение"
                else:
                    action = ACTION_TEXT.get(raw, "действие")

                executed = d.get("executed")

                blocked = d.get("blocked", False)
                dry_run = d.get("dry_run", False)
                block_reason = d.get("block_reason", "")

                if source == "ask_confirmed":
                    status_icon = "🧪"
                    status_text = "Подтверждено (dry-run)"
                elif source == "ask_cancelled":
                    status_icon = "❌"
                    status_text = "Отменено"
                elif source == "ask_proposal":
                    status_icon = "🟡"
                    status_text = "Предложено"
                elif blocked:
                    status_icon = "🚫"
                    status_text = f"Заблокировано: {block_reason}" if block_reason else "Заблокировано"
                elif dry_run:
                    status_icon = "🧪"
                    status_text = "Dry-run"
                elif executed is True:
                    status_icon = "🟢"
                    status_text = "Выполнено"
                else:
                    status_icon = "⚪"
                    status_text = "Не выполнено"

                parts.append(f"• {action} — {status_icon} {status_text}")

            values = []
            for d in filtered:
                sensor = d.get("sensor")
                value = d.get("value")
                action_name = d.get("action", "")

                if value is None:
                    continue

                if sensor == "21":
                    if action_name in {"fan_low_on", "fan_low_off"}:
                        values.append(f"{SENSOR_LABELS['21_temp']} — {float(value):.1f}°C")
                    else:
                        values.append(f"{SENSOR_LABELS['21_humidity']} — {int(value)}%")
                elif sensor == "22":
                    if action_name in {"fan_top_on", "fan_top_off"}:
                        values.append(f"{SENSOR_LABELS['22_temp']} — {float(value):.1f}°C")
                    else:
                        values.append(f"{SENSOR_LABELS['22_humidity']} — {int(value)}%")
                elif sensor == "11":
                    values.append(f"{SENSOR_LABELS['11']} — {int(value)}%")
                elif sensor == "16":
                    values.append(f"{SENSOR_LABELS['16']} — {int(value)}%")

            if values:
                parts.append("")
                parts.append("Показания:")
                parts.extend(values)

            parts.append("")

        text_out = "\n".join(parts).strip()

        if len(text_out) > 4000:
            text_out = text_out[:4000] + "\n\n…обрезано"

        bot.send_message(message.chat.id, text_out)



    @bot.message_handler(commands=["auto_status"])
    def cmd_auto_status(message):
        try:
            import os
            from mode_manager import get_mode

            mode = get_mode()
            enabled = os.getenv("AUTO_ACTIONS_ENABLED", "0")

            parts = ["🤖 AUTO статус", ""]

            parts.append(f"Режим: {mode}")

            if enabled == "1":
                parts.append("AUTO действия: 🟢 ВКЛЮЧЕНЫ")
            else:
                parts.append("AUTO действия: 🔴 ВЫКЛЮЧЕНЫ (безопасный режим)")

            parts.append("")
            parts.append("Разрешённые действия:")
            parts.append("• вентиляторы верх")
            parts.append("• вентиляторы низ")

            parts.append("")
            parts.append("Ограничения:")
            parts.append("• полив ❌")
            parts.append("• увлажнение ❌")
            parts.append("• свет ❌")

            bot.send_message(message.chat.id, "\n".join(parts))

        except Exception as e:
            safe_send(bot, str(message.chat.id), f"Ошибка /auto_status:\n{e}")

    


    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def handle_menu_buttons(message):
        text = (message.text or "").strip()

        try:
            # --- МЕНЮ (оставляем как есть) ---
            if text == "🌿 Растения":
                return cmd_plants(message)

            elif text == "📊 Статус":
                return cmd_status(message)

            elif text == "🚨 Критично":
                return cmd_critical(message)

            elif text == "🤖 AI":
                return cmd_ai(message)

            elif text == "🤖 Режим":
                return cmd_mode(message)

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

            # --- ВСЁ ОСТАЛЬНОЕ → ЧАТ ---
            response = handle_chat_message(text)

            if response.response_type == "ask_candidate":
                ask_payload = response.ask_payload or {}
                save_ask_state(ask_payload)

                bot.send_message(
                    message.chat.id,
                    response.reply_text,
                    reply_markup=build_ask_keyboard(),
                )
                return

            if response.response_type == "action_candidate":
                action_payload = response.action_payload or {}
                action_key = action_payload.get("action_key")

                if not action_key:
                    bot.send_message(message.chat.id, response.reply_text)
                    return

                results = execute_action_key(action_key)
                lines = [response.reply_text, ""]

                for r in results:
                    icon = "🟢" if getattr(r, "success", False) else "❌"
                    entity = getattr(r, "entity_id", None) or "-"
                    msg = getattr(r, "message", "")
                    lines.append(f"{icon} {entity} — {msg}")

                bot.send_message(
                    message.chat.id,
                    "\n".join(lines),
                )
                return

            bot.send_message(
                message.chat.id,
                response.reply_text,
            )
            return

        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Ошибка обработки сообщения: {e}"
            )
            return
     




