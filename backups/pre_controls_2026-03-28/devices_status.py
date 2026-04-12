#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from reports import get_ha

DEVICES = {
    "⚡ Питание": [
        ("Главный щиток", "switch.shchitok_veranda_switch"),
        ("Резервный выключатель", "switch.wifi_perekliuchatel_na_din_reiku_2_switch"),
        ("Питание камер", "switch.setveoi_filtr_klubnika_socket_5"),
    ],
    "💡 Свет": [
        ("Свет верхний ярус", "switch.setevoi_filtr_klubnika_socket_2"),
        ("Свет нижний ярус", "switch.setevoi_filtr_novyi_socket_4"),
    ],
    "🌬 Вентиляция": [
        ("Вентиляторы верх", "switch.setevoi_filtr_novyi_socket_1"),
        ("Вентиляторы низ", "switch.setevoi_filtr_novyi_usb_1"),
    ],
    "💧 Полив и вода": [
        ("Увлажнитель", "switch.uviazhnitel_"),
        ("Розетка увлажнителя", "switch.smart_power_strip_eu_2_socket_3"),
        ("Полив верхний ярус", "switch.klubnika_poliv_verkh_switch_1"),
        ("Полив верх с удобрениями", "switch.klubnika_poliv_verkh_switch_2"),
        ("Защита полива верх", "switch.klubnika_poliv_verkh_switch_3"),
        ("Полив нижний ярус", "switch.klubnika_poliv_switch_1"),
        ("Полив низ с удобрениями", "switch.klubnika_poliv_switch_2"),
        ("Защита полива низ", "switch.klubnika_poliv_switch_3"),
        ("Насос удобрений", "switch.smart_power_strip_eu_2_socket_4"),
        ("Розетка насос верх", "switch.setevoi_filtr_klubnika_socket_4"),
        ("Розетка насос низ", "switch.setevoi_filtr_klubnika_socket_3"),
    ],
    "🪟 Штора": [
        ("Штора", "cover.wifi_curtain_driver_converter_curtain"),
    ],
    "♨️ Климат": [
        ("Термостат веранда", "climate.termostat_veranda"),
        ("Frost protection", "switch.termostat_veranda_frost_protection"),
    ],
    "🔌 Служебное питание": [
        ("Питание датчика освещённости верх", "switch.smart_power_strip_eu_2_socket_5"),
        ("Питание датчика низа", "switch.setevoi_filtr_Novyi_socket_2"),
        ("Питание датчика качества воздуха", "switch.setevoi_filtr_novyi_socket_3"),
    ],
}


def _normalize_state(state):
    if state in (None, "", "unknown", "unavailable"):
        return "нет данных"

    s = str(state).lower()

    if s == "on":
        return "🟢 ВКЛ"
    if s == "off":
        return "⚪ ВЫКЛ"
    if s == "open":
        return "🟢 ОТКРЫТА"
    if s == "closed":
        return "⚪ ЗАКРЫТА"

    return str(state)


def _read_state(entity_id: str):
    ha = get_ha()
    if ha is None:
        return "нет HA"

    try:
        state_data = ha.get_state(entity_id)
    except Exception:
        return "ошибка чтения"

    if not state_data:
        return "нет данных"

    return _normalize_state(state_data.get("state"))


def build_devices_report() -> str:
    lines = ["🔌 Устройства теплицы", ""]

    for group_name, items in DEVICES.items():
        lines.append(group_name)
        for label, entity_id in items:
            state = _read_state(entity_id)
            lines.append(f"- {label}: {state}")
        lines.append("")

    return "\n".join(lines).strip()
