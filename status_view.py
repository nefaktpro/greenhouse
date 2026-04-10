from datetime import datetime, timezone

from ha_client import HomeAssistantClient


STALE_AFTER_MINUTES = 1440


def _get_state_data(ha: HomeAssistantClient, entity_id: str) -> dict | None:
    return ha.get_state(entity_id)


def _normalize_state(state) -> str:
    if state in (None, "", "unknown", "unavailable"):
        return "нет данных"

    try:
        value = float(state)

        if value.is_integer():
            return str(int(value))

        return f"{value:.1f}"
    except Exception:
        return str(state)


def _age_minutes(iso_ts: str | None) -> int | None:
    if not iso_ts:
        return None

    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        return int(diff.total_seconds() // 60)
    except Exception:
        return None


def _line(ha: HomeAssistantClient, label: str, entity_id: str, unit: str = "") -> list[str]:
    state_data = _get_state_data(ha, entity_id)

    if not state_data:
        return [
            f"  {label}: нет данных",
            "    ⚠️ датчик недоступен",
        ]

    value = _normalize_state(state_data.get("state"))
    suffix = unit if value != "нет данных" else ""

    lines = [f"  {label}: {value}{suffix}"]

    minutes = _age_minutes(state_data.get("last_updated") or state_data.get("last_changed"))

    if minutes is None:
        lines.append("    ⚠️ нет времени обновления")
    elif minutes >= STALE_AFTER_MINUTES:
        lines.append(f"    ⚠️ {minutes} мин без обновления")

    return lines


def build_plants_low_text(ha: HomeAssistantClient) -> str:
    lines = [
        "🌿 НИЗ — влажность и температура",
        "",
        "🌬 Воздух вокруг кустов",
        *_line(ha, "Влажность воздуха", "sensor.temperature_and_humidity_sensor_humidity", "%"),
        *_line(ha, "Температура воздуха", "sensor.temperature_and_humidity_sensor_temperature", "°C"),
        "",
        "🪴 Большой белый горшок",
        *_line(ha, "Основная влажность земли", "sensor.klubnika_vlazhnost_niz_belyi_humidity", "%"),
        *_line(ha, "Температура земли", "sensor.klubnika_vlazhnost_niz_belyi_temperature", "°C"),
        *_line(ha, "Влажность на поверхности", "sensor.ogurets_vertikalnyi_humidity", "%"),
        *_line(ha, "Температура поверхности", "sensor.ogurets_vertikalnyi_temperature", "°C"),
        *_line(ha, "Воздух у корней", "sensor.vlazhnost_nizhnii_gorshok_belyi_humidity", "%"),
        *_line(ha, "Температура у корней", "sensor.vlazhnost_nizhnii_gorshok_belyi_temperature", "°C"),
        "",
        "🪴 Серый горшок",
        *_line(ha, "Основная влажность земли", "sensor.klubnika_poliv_niz_seryi_humidity", "%"),
        *_line(ha, "Температура земли", "sensor.klubnika_poliv_niz_seryi_temperature", "°C"),
        "  Влажность на поверхности: нет данных",
        "  Температура поверхности: нет данных",
        "",
        "🪴 Круглый горшок у окна",
        *_line(ha, "Основная влажность земли", "sensor.sgs01_4_humidity", "%"),
        *_line(ha, "Температура земли", "sensor.sgs01_4_temperature", "°C"),
        *_line(ha, "Влажность на поверхности", "sensor.vlazhnost_humidity", "%"),
        *_line(ha, "Температура поверхности", "sensor.vlazhnost_temperature", "°C"),
    ]

    return "\n".join(lines)


def build_plants_high_text(ha: HomeAssistantClient) -> str:
    lines = [
        "🌿 ВЕРХ — влажность и температура",
        "",
        "🌬 Воздух вокруг кустов",
        *_line(ha, "Влажность воздуха", "sensor.temperature_and_humidity_sensor_2_humidity", "%"),
        *_line(ha, "Температура воздуха", "sensor.temperature_and_humidity_sensor_2_temperature", "°C"),
        "",
        "🪴 Дальний горшок",
        *_line(ha, "Основная влажность земли", "sensor.datchik_vlazhnosti_spotifilum_humidity", "%"),
        *_line(ha, "Температура земли", "sensor.datchik_vlazhnosti_spotifilum_temperature", "°C"),
        *_line(ha, "Влажность на поверхности", "sensor.vlazhnost_klubnika_verkh_chernyi_humidity", "%"),
        *_line(ha, "Температура поверхности", "sensor.vlazhnost_klubnika_verkh_chernyi_temperature", "°C"),
        *_line(ha, "Воздух у корней", "sensor.datchik_vlazhnosti_verkh_humidity", "%"),
        *_line(ha, "Температура у корней", "sensor.datchik_vlazhnosti_verkh_temperature", "°C"),
        "",
        "🪴 Горшок у окна",
        *_line(ha, "Основная влажность земли", "sensor.klubnika_verkh_u_okna_humidity", "%"),
        *_line(ha, "Температура земли", "sensor.klubnika_verkh_u_okna_temperature", "°C"),
        *_line(ha, "Влажность на поверхности", "sensor.chernyi_poverkhnost_u_okna_humidity", "%"),
        *_line(ha, "Температура поверхности", "sensor.chernyi_poverkhnost_u_okna_temperature", "°C"),
    ]

    return "\n".join(lines)


def build_plants_full_text(ha: HomeAssistantClient) -> str:
    return build_plants_low_text(ha) + "\n\n" + build_plants_high_text(ha)


def _state_float(ha: HomeAssistantClient, entity_id: str):
    state_data = _get_state_data(ha, entity_id)
    if not state_data:
        return None
    try:
        return float(state_data.get("state"))
    except Exception:
        return None


def build_status_text(ha: HomeAssistantClient) -> str:
    low_air_h = _state_float(ha, "sensor.temperature_and_humidity_sensor_humidity")
    high_air_h = _state_float(ha, "sensor.temperature_and_humidity_sensor_2_humidity")

    low_white = _state_float(ha, "sensor.klubnika_vlazhnost_niz_belyi_humidity")
    low_gray = _state_float(ha, "sensor.klubnika_poliv_niz_seryi_humidity")
    low_round = _state_float(ha, "sensor.sgs01_4_humidity")

    high_far = _state_float(ha, "sensor.datchik_vlazhnosti_spotifilum_humidity")
    high_window = _state_float(ha, "sensor.klubnika_verkh_u_okna_humidity")

    def avg(values):
        nums = [v for v in values if v is not None]
        if not nums:
            return None
        return sum(nums) / len(nums)

    low_avg = avg([low_white, low_gray, low_round])
    high_avg = avg([high_far, high_window])

    lines = ["📊 Короткий статус теплицы", ""]

    # Воздух
    if low_air_h is None:
        low_air_text = "нет данных"
    elif low_air_h < 45:
        low_air_text = f"{low_air_h:.0f}% — сухо"
    elif low_air_h <= 70:
        low_air_text = f"{low_air_h:.0f}% — норма"
    else:
        low_air_text = f"{low_air_h:.0f}% — влажно"

    if high_air_h is None:
        high_air_text = "нет данных"
    elif high_air_h < 45:
        high_air_text = f"{high_air_h:.0f}% — сухо"
    elif high_air_h <= 70:
        high_air_text = f"{high_air_h:.0f}% — норма"
    else:
        high_air_text = f"{high_air_h:.0f}% — влажно"

    lines.append(f"🌬 Низ, воздух: {low_air_text}")
    lines.append(f"🌬 Верх, воздух: {high_air_text}")

    # Почва низ
    if low_avg is None:
        low_text = "нет данных"
    elif low_avg < 25:
        low_text = f"{low_avg:.1f}% — сухо"
    elif low_avg < 35:
        low_text = f"{low_avg:.1f}% — умеренно сухо"
    else:
        low_text = f"{low_avg:.1f}% — нормально"

    # Почва верх
    if high_avg is None:
        high_text = "нет данных"
    elif high_avg < 15:
        high_text = f"{high_avg:.1f}% — критически сухо"
    elif high_avg < 25:
        high_text = f"{high_avg:.1f}% — сухо"
    elif high_avg < 35:
        high_text = f"{high_avg:.1f}% — умеренно сухо"
    else:
        high_text = f"{high_avg:.1f}% — нормально"

    lines.append(f"🪴 Низ, грунт: {low_text}")
    lines.append(f"🪴 Верх, грунт: {high_text}")

    # Частный акцент на верхний горшок у окна
    if high_window is not None:
        if high_window < 15:
            lines.append(f"⚠️ Верхний горшок у окна: {high_window:.0f}% — критически сухо")
        elif high_window < 20:
            lines.append(f"⚠️ Верхний горшок у окна: {high_window:.0f}% — сухо")

    return "\n".join(lines)
