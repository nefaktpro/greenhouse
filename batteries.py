#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from reports import get_ha

BATTERY_SENSORS = [
    ("1.2", "Датчик дыма (центр) — батарея", "sensor.dymovoi_signalizator_battery"),
    ("8.25", "Датчик дыма 2 — батарея", "sensor.dymovoi_signalizator_2_battery"),
    ("9.28", "Датчик протечки — батарея", "sensor.datchik_utechki_vody_battery"),

    ("10.31", "НИЗ / Большой белый / Поверхность — батарея", "sensor.ogurets_vertikalnyi_battery"),
    ("11.33", "НИЗ / Серый горшок / Основной — батарея", "sensor.klubnika_poliv_niz_seryi_battery"),
    ("12.37", "НИЗ / Большой белый / Основной — батарея", "sensor.klubnika_vlazhnost_niz_belyi_battery"),
    ("13.40", "НИЗ / Большой белый / Воздух у корней — батарея", "sensor.vlazhnost_nizhnii_gorshok_belyi_battery"),
    ("14.43", "НИЗ / Круглый у окна / Основной — батарея", "sensor.sgs01_4_battery"),

    ("15.46", "ВЕРХ / Дальний / Поверхность — батарея", "sensor.vlazhnost_klubnika_verkh_chernyi_battery"),
    ("16.49", "ВЕРХ / Дальний / Основной — батарея", "sensor.datchik_vlazhnosti_spotifilum_battery"),
    ("17.52", "НИЗ / Круглый / Поверхность — батарея", "sensor.vlazhnost_battery"),
    ("18.55", "ВЕРХ / У окна / Поверхность — батарея", "sensor.chernyi_poverkhnost_u_okna_battery"),
    ("19.58", "ВЕРХ / У окна / Основной — батарея", "sensor.klubnika_verkh_u_okna_battery"),
    ("20.61", "ВЕРХ / Дальний / Воздух у корней — батарея", "sensor.datchik_vlazhnosti_verkh_battery"),

    ("21.64", "НИЗ / Воздух у куста — батарея", "sensor.temperature_and_humidity_sensor_battery"),
    ("22.67", "ВЕРХ / Воздух у куста — батарея", "sensor.temperature_and_humidity_sensor_2_battery"),

    ("23.xx", "Освещённость — батарея", "sensor.luminance_sensor_battery"),
    ("24.xx", "Датчик электричества — батарея", "sensor.datchik_elektrichestva_battery"),
]


def _to_float(value):
    try:
        return float(value)
    except Exception:
        return None


def _read_battery(entity_id: str):
    ha = get_ha()
    if ha is None:
        return None, "нет HA"

    try:
        state_data = ha.get_state(entity_id)
    except Exception:
        return None, "ошибка чтения"

    if not state_data:
        return None, "нет данных"

    state = state_data.get("state")
    if state in (None, "", "unknown", "unavailable"):
        return None, "нет данных"

    value = _to_float(state)
    if value is None:
        return None, str(state)

    return value, None


def build_batteries_report() -> str:
    critical = []
    low = []
    normal = []
    nodata = []

    for device_id, label, entity_id in BATTERY_SENSORS:
        value, problem = _read_battery(entity_id)

        if value is None:
            nodata.append((device_id, label, problem or "нет данных"))
            continue

        item = (device_id, label, value)

        if value < 10:
            critical.append(item)
        elif value <= 20:
            low.append(item)
        else:
            normal.append(item)

    critical.sort(key=lambda x: x[2])
    low.sort(key=lambda x: x[2])
    normal.sort(key=lambda x: x[2])

    lines = ["🔋 Батарейки устройств", ""]

    lines.append(
        f"Итого: критично {len(critical)}, низкие {len(low)}, нормальные {len(normal)}, без данных {len(nodata)}"
    )
    lines.append("")

    if critical:
        lines.append("🚨 Критически низкие (<10%):")
        for device_id, label, value in critical:
            lines.append(f"- {device_id} — {label}: {value:.0f}%")
        lines.append("")

    if low:
        lines.append("⚠️ Низкие (<=20%):")
        for device_id, label, value in low:
            lines.append(f"- {device_id} — {label}: {value:.0f}%")
        lines.append("")

    if normal:
        lines.append("✅ Остальные:")
        for device_id, label, value in normal:
            lines.append(f"- {device_id} — {label}: {value:.0f}%")
        lines.append("")

    if nodata:
        lines.append("❓ Нет данных:")
        for device_id, label, problem in nodata:
            lines.append(f"- {device_id} — {label}: {problem}")

    if len(lines) == 4:
        lines.append("Нет данных по батарейкам.")

    return "\n".join(lines)
