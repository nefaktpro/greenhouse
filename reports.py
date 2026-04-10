from alerts_engine import build_alerts_text
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import traceback


def _load_env_file(path: str) -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
_load_env_file(ENV_PATH)


def _import_module_or_none(name: str):
    try:
        return __import__(name)
    except Exception:
        return None


ha_module = _import_module_or_none("ha_client")
status_view_module = _import_module_or_none("status_view")
ai_service_module = _import_module_or_none("ai_service")
fire_safety_module = _import_module_or_none("fire_safety")
devices_module = _import_module_or_none("devices")


def _build_ha_client():
    if ha_module is None:
        raise RuntimeError("Module ha_client.py not found")

    class_candidates = [
        "HAClient",
        "HomeAssistantClient",
        "HomeAssistantAPI",
        "Client",
    ]

    for cls_name in class_candidates:
        cls = getattr(ha_module, cls_name, None)
        if cls is None:
            continue
        try:
            return cls()
        except TypeError:
            base_url = os.getenv("HA_BASE_URL") or os.getenv("HA_URL")
            token = os.getenv("HA_TOKEN")
            try:
                return cls(base_url, token)
            except Exception:
                pass
        except Exception:
            pass

    if hasattr(ha_module, "get_state"):
        return ha_module

    raise RuntimeError("Could not build HA client from ha_client.py")


def _call_first(module, names, *args, **kwargs):
    if module is None:
        raise RuntimeError("Module is not available")
    last_error = None
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                last_error = e
    if last_error:
        raise last_error
    raise AttributeError(f"None of functions exist: {names}")


def _load_devices():
    if devices_module is None:
        return {}

    # Популярные варианты
    for name in ["load_devices", "get_devices"]:
        fn = getattr(devices_module, name, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass

    for attr in ["DEVICES", "devices"]:
        value = getattr(devices_module, attr, None)
        if isinstance(value, dict):
            return value

    return {}


try:
    HA = _build_ha_client()
except Exception as e:
    print("reports.py: HA init error:", e)
    traceback.print_exc()
    HA = None

DEVICES = _load_devices()


def get_ha():
    return HA


def _get_all_states_for_alerts():
    if HA is None:
        raise RuntimeError("HA недоступен")

    method_names = [
        "get_states",
        "get_all_states",
        "fetch_states",
        "fetch_ha_states",
        "states",
    ]

    for name in method_names:
        fn = getattr(HA, name, None)
        if callable(fn):
            data = fn()
            if data is not None:
                return data

    if ha_module is not None:
        for name in method_names:
            fn = getattr(ha_module, name, None)
            if callable(fn):
                data = fn()
                if data is not None:
                    return data

    raise AttributeError("Не найден метод получения всех состояний HA")


def build_plants_report() -> str:
    return _call_first(
        status_view_module,
        ["build_plants_full_text", "build_full_plants_text", "build_plants_text"],
        HA,
    )


def build_plants_low_report() -> str:
    return _call_first(
        status_view_module,
        ["build_plants_low_text", "build_low_plants_text"],
        HA,
    )


def build_plants_high_report() -> str:
    return _call_first(
        status_view_module,
        ["build_plants_high_text", "build_high_plants_text"],
        HA,
    )


def build_status_report() -> str:
    try:
        return _call_first(
            status_view_module,
            ["build_status_text", "build_short_status_text", "build_main_status_text"],
            HA,
        )
    except Exception:
        return build_plants_report()




def _device_name(device_id: str) -> str:
    device = DEVICES.get(device_id, {})
    return device.get("name") or device_id


def _device_state(device_id: str) -> str:
    device = DEVICES.get(device_id, {})
    entity_id = device.get("entity_id", "")
    if not entity_id or HA is None:
        return "нет данных"

    try:
        state_data = HA.get_state(entity_id)
        if not state_data:
            return "нет данных"
        return str(state_data.get("state", "нет данных"))
    except Exception:
        return "нет данных"


def build_fire_report() -> str:
    lines = ["🔥 Пожарная безопасность", ""]

    if fire_safety_module is None:
        return "Пожарный модуль недоступен."

    fire_ids = getattr(fire_safety_module, "FIRE_SENSOR_IDS", [])
    action_ids = getattr(fire_safety_module, "FIRE_ACTION_SEQUENCE", [])

    # Список пожарных датчиков
    if fire_ids:
        lines.append("Датчики пожара:")
        for device_id in fire_ids:
            name = _device_name(device_id)
            state = _device_state(device_id)
            icon = "🔥" if str(state).lower() == "on" else "✅"
            lines.append(f"{icon} {device_id} — {name}: {state}")
        lines.append("")

    # Проверка активных сработок
    try:
        fire_sources = fire_safety_module.find_fire_sources(DEVICES, HA)
    except Exception:
        fire_sources = []

    if fire_sources:
        lines.append("🚨 ОБНАРУЖЕНО СРАБАТЫВАНИЕ:")
        for device in fire_sources:
            lines.append(f"🔥 {device.get('id', '?')} — {device.get('name', 'unknown')}")
        lines.append("")
        lines.append("План отключения:")
    else:
        lines.append("✅ Пожар не обнаружен")
        lines.append("")
        lines.append("План действий при пожаре:")

    # План действий
    for idx, device_id in enumerate(action_ids, start=1):
        name = _device_name(device_id)
        lines.append(f"{idx}. OFF → {device_id} — {name}")

    # 7. Оффлайн устройства (по устройствам, не по каждому параметру)
    lines.append("")
    lines.append("📴 Оффлайн устройства")

    try:
        full_csv_path = os.path.join(BASE_DIR, "devices_full.csv")
        if os.path.exists(full_csv_path):
            with open(full_csv_path, "r", encoding="utf-8", newline="") as f:
                full_rows = list(csv.DictReader(f))

            parent_rows = [r for r in full_rows if (r.get("SubID") or "") == "0"]
            offline_devices = []

            bad_states = {"unavailable", "unknown", "none", "нет данных"}

            for parent in parent_rows:
                device_id = parent.get("DeviceID", "")
                device_name = parent.get("Name", "") or f"Устройство {device_id}"

                children = [
                    r for r in full_rows
                    if (r.get("ParentID") or "") == device_id and (r.get("EntityID") or "").strip()
                ]

                if not children:
                    continue

                bad_children = []
                for ch in children:
                    entity_id = (ch.get("EntityID") or "").strip()
                    st = state_str(entity_id).lower()
                    if st in bad_states:
                        bad_children.append(ch.get("Name") or entity_id)

                if bad_children:
                    offline_devices.append(f"• {device_id} — {device_name}")

            if offline_devices:
                lines.extend(offline_devices[:20])
            else:
                lines.append("✅ Оффлайн устройств не обнаружено")
        else:
            lines.append("⚠️ devices_full.csv не найден")
    except Exception as e:
        lines.append(f"⚠️ Не удалось проверить оффлайн устройства: {e}")

    return "\n".join(lines)


def build_ai_report() -> str:
    if ai_service_module is None:
        return "AI-сервис недоступен"

    try:
        return _call_first(
            ai_service_module,
            ["get_ai_analysis", "build_ai_analysis", "get_analysis_text"],
        )
    except Exception:
        pass

    try:
        return _call_first(
            ai_service_module,
            ["get_ai_analysis", "build_ai_analysis", "get_analysis_text"],
            HA,
        )
    except Exception as e:
        return f"AI-сервис недоступен: {e}"


def build_send_now_report() -> str:
    text = "⏰ Плановый отчёт теплицы\n\n"
    text += "🌿 Подробный статус:\n\n"
    text += build_plants_report()
    text += "\n\n🧠 Оценка теплицы:\n\n"
    text += build_ai_report()
    return text



def build_alerts_report() -> str:
    return "🚨 Тревоги\n\nПока активных тревог нет."










def build_safety_report() -> str:
    import csv
    import os
    import re

    lines = []
    lines.append("🛡 Безопасность")
    lines.append("")

    csv_path = os.path.join(BASE_DIR, "devices_safety.csv")
    full_csv_path = os.path.join(BASE_DIR, "devices_full.csv")

    if not os.path.exists(csv_path):
        return "🛡 Безопасность\n\nОшибка: devices_safety.csv не найден."

    if HA is None:
        return "🛡 Безопасность\n\nОшибка: HA недоступен."

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    def get_state(entity_id: str):
        if not entity_id:
            return None
        try:
            return HA.get_state(entity_id)
        except Exception:
            return None

    def state_str(entity_id: str) -> str:
        data = get_state(entity_id)
        if not data:
            return "нет данных"
        return str(data.get("state", "нет данных"))

    def find_rows(predicate):
        return [r for r in rows if predicate(r)]

    # 1. Пожарный контур
    fire_rows = find_rows(lambda r: (r.get("Group") or "") == "fire")
    smoke_rows = [r for r in fire_rows if (r.get("Type") or "").lower() in ("smoke", "binary_sensor")]
    smoke_alert = False

    lines.append("🧯 Пожарный контур")
    if smoke_rows:
        for r in smoke_rows:
            st = state_str(r.get("EntityID", "")).lower()
            if st == "on":
                smoke_alert = True

        lines.append("🔴 Обнаружен сигнал дыма" if smoke_alert else "✅ Дым не обнаружен")

        for r in smoke_rows:
            entity_id = r.get("EntityID", "")
            st = state_str(entity_id)
            label = r.get("Name") or r.get("Description") or entity_id
            dev = r.get("DeviceID", "")
            sub = r.get("SubID", "")
            item_id = f"{dev}.{sub}" if dev and sub and sub != "0" else dev
            lines.append(f"• {item_id} — {label}: {st}")
    else:
        lines.append("⚠️ Датчики дыма не найдены")

    lines.append("")

    # 2. Протечка
    leak_rows = find_rows(lambda r: (r.get("Group") or "") == "leak")
    leak_sensor_rows = [r for r in leak_rows if (r.get("Type") or "").lower() in ("moisture", "binary_sensor")]

    lines.append("💧 Протечка")
    if leak_sensor_rows:
        leak_alert = False
        for r in leak_sensor_rows:
            st = state_str(r.get("EntityID", "")).lower()
            if st == "on":
                leak_alert = True

        lines.append("🔴 Обнаружена протечка" if leak_alert else "✅ Не обнаружена")

        for r in leak_sensor_rows:
            entity_id = r.get("EntityID", "")
            st = state_str(entity_id)
            label = r.get("Name") or entity_id
            dev = r.get("DeviceID", "")
            sub = r.get("SubID", "")
            item_id = f"{dev}.{sub}" if dev and sub and sub != "0" else dev
            lines.append(f"• {item_id} — {label}: {st}")
    else:
        lines.append("⚠️ Датчик протечки не найден")

    lines.append("")

    # 3. Электричество
    power_rows = find_rows(lambda r: (r.get("Group") or "") == "electricity" or (r.get("DeviceID") or "") in ("5", "25", "29"))
    mains_row = voltage_row = power_sensor_row = current_row = energy_row = None
    main_switch_row = backup_switch_row = None

    for r in power_rows:
        entity_id = (r.get("EntityID") or "").lower()
        if entity_id == "binary_sensor.25_datchik_elektrichestva_door":
            mains_row = r
        elif entity_id == "sensor.shchitok_veranda_voltage":
            voltage_row = r
        elif entity_id == "sensor.shchitok_veranda_power":
            power_sensor_row = r
        elif entity_id == "sensor.shchitok_veranda_current":
            current_row = r
        elif entity_id == "sensor.shchitok_veranda_total_energy":
            energy_row = r
        elif entity_id == "switch.shchitok_veranda_switch":
            main_switch_row = r
        elif entity_id == "switch.wifi_perekliuchatel_na_din_reiku_2_switch":
            backup_switch_row = r

    lines.append("🔌 Электричество")
    if mains_row:
        mains_state = state_str(mains_row.get("EntityID", "")).lower()
        if mains_state == "off":
            lines.append("✅ 220В есть — питание от общей сети")
        elif mains_state == "on":
            lines.append("🔴 Нет 220В — питание от аккумулятора")
        else:
            lines.append(f"⚠️ Состояние 220В: {mains_state}")
    else:
        lines.append("⚠️ Датчик наличия 220В не найден")

    if voltage_row:
        lines.append(f"• Напряжение: {state_str(voltage_row.get('EntityID', ''))} В")
    if power_sensor_row:
        lines.append(f"• Мощность: {state_str(power_sensor_row.get('EntityID', ''))} Вт")
    if current_row:
        lines.append(f"• Ток: {state_str(current_row.get('EntityID', ''))} А")
    if energy_row:
        lines.append(f"• Энергия: {state_str(energy_row.get('EntityID', ''))} kWh")

    lines.append("")

    # 4. Аварийное отключение
    lines.append("⛔️ Аварийное отключение")
    lines.append(f"• Основной контур: {state_str(main_switch_row.get('EntityID', '')) if main_switch_row else 'не найден'}")
    lines.append(f"• Резервный контур: {state_str(backup_switch_row.get('EntityID', '')) if backup_switch_row else 'не найден'}")

    lines.append("")

    # 5. Критичные сущности
    critical_rows = [r for r in rows if (r.get("Criticality") or "") == "critical" and (r.get("EntityID") or "")]
    unavailable = []

    for r in critical_rows:
        entity_id = r.get("EntityID", "")
        st = state_str(entity_id).lower()
        if st in ("unavailable", "unknown", "none", "нет данных"):
            dev = r.get("DeviceID", "")
            sub = r.get("SubID", "")
            item_id = f"{dev}.{sub}" if dev and sub and sub != "0" else dev
            unavailable.append(f"• {item_id} — {r.get('Name') or entity_id}: {st}")

    lines.append("📡 Критичные сущности")
    if unavailable:
        lines.append("⚠️ Недоступны:")
        lines.extend(unavailable[:20])
    else:
        lines.append("✅ Все критичные сущности доступны")

    lines.append("")

    # 6. Все батарейки системы
    lines.append("🔋 Батарейки")
    try:
        from batteries import build_batteries_report
        batt_text = build_batteries_report()

        crit = low = norm = nodata = "?"
        for s in batt_text.splitlines():
            ss = s.strip()
            if ss.startswith("Итого:"):
                m = re.search(r'критично\s+(\d+),\s*низкие\s+(\d+),\s*нормальные\s+(\d+),\s*без данных\s+(\d+)', ss.lower())
                if m:
                    crit, low, norm, nodata = m.groups()
                break

        lines.append(f"• Критично: {crit}")
        lines.append(f"• Низкие: {low}")
        lines.append(f"• В норме: {norm}")
        lines.append(f"• Без данных: {nodata}")

        low_block = []
        capture = False
        for s in batt_text.splitlines():
            ss = s.strip()
            if "Критично низкие" in ss or "Низкие" in ss:
                capture = True
                continue
            if capture and ss.startswith("✅ Остальные"):
                break
            if capture and ss.startswith("- "):
                low_block.append("• " + ss[2:])

        if low_block:
            lines.append("")
            lines.append("🟠 Что менять:")
            for item in low_block[:12]:
                lines.append(item)

    except Exception as e:
        lines.append(f"⚠️ Не удалось получить данные: {e}")

    lines.append("")

    # 7. Оффлайн устройства
    lines.append("📴 Оффлайн устройства")
    try:
        if os.path.exists(full_csv_path):
            with open(full_csv_path, "r", encoding="utf-8", newline="") as f:
                full_rows = list(csv.DictReader(f))

            parent_rows = [r for r in full_rows if (r.get("SubID") or "") == "0"]
            offline_devices = []
            bad_states = {"unavailable", "unknown", "none", "нет данных"}

            for parent in parent_rows:
                device_id = parent.get("DeviceID", "")
                device_name = parent.get("Name", "") or f"Устройство {device_id}"

                children = [
                    r for r in full_rows
                    if (r.get("ParentID") or "") == device_id and (r.get("EntityID") or "").strip()
                ]

                if not children:
                    continue

                bad_children = []
                for ch in children:
                    entity_id = (ch.get("EntityID") or "").strip()
                    st = state_str(entity_id).lower()
                    if st in bad_states:
                        bad_children.append(ch.get("Name") or entity_id)

                if bad_children:
                    offline_devices.append(f"• {device_id} — {device_name}")

            if offline_devices:
                lines.extend(offline_devices[:20])
            else:
                lines.append("✅ Оффлайн устройств не обнаружено")
        else:
            lines.append("⚠️ devices_full.csv не найден")
    except Exception as e:
        lines.append(f"⚠️ Не удалось проверить оффлайн устройства: {e}")

    return "\n".join(lines)



def build_critical_report() -> str:
    from datetime import datetime

    if HA is None:
        return "🚨 Критично\n\nОшибка: HA недоступен."

    lines = []
    lines.append("🚨 Критично")
    lines.append("")

    now = datetime.now()
    is_day = 8 <= now.hour < 22
    period = "день" if is_day else "ночь"

    lines.append(f"Период: {period}")
    lines.append("")

    def get_state(entity_id: str):
        try:
            return HA.get_state(entity_id)
        except Exception:
            return None

    def state_str(entity_id: str) -> str:
        data = get_state(entity_id)
        if not data:
            return "нет данных"
        return str(data.get("state", "нет данных"))

    def to_float(entity_id: str):
        raw = state_str(entity_id)
        try:
            return float(str(raw).replace("%", "").replace(",", ".").strip())
        except Exception:
            return None

    critical = []
    warning = []
    info = []

    # 1. Воздух у листьев — низ (21)
    low_leaf_h = to_float("sensor.temperature_and_humidity_sensor_humidity")
    low_leaf_t = to_float("sensor.temperature_and_humidity_sensor_temperature")

    if low_leaf_h is None:
        warning.append("Низ у листьев (21): нет данных по влажности")
    elif low_leaf_h < 50:
        critical.append(f"Низ у листьев (21): влажность {low_leaf_h:.0f}% — ниже 50%")

    if low_leaf_t is None:
        warning.append("Низ у листьев (21): нет данных по температуре")
    else:
        if is_day:
            if low_leaf_t < 20:
                critical.append(f"Низ у листьев (21): температура {low_leaf_t:.1f}°C — ниже дневной нормы")
            elif low_leaf_t > 25:
                critical.append(f"Низ у листьев (21): температура {low_leaf_t:.1f}°C — выше дневной нормы")
        else:
            if low_leaf_t < 12:
                critical.append(f"Низ у листьев (21): температура {low_leaf_t:.1f}°C — ниже ночной нормы")
            elif low_leaf_t > 18:
                warning.append(f"Низ у листьев (21): температура {low_leaf_t:.1f}°C — выше ночной нормы")

    # 2. Воздух у листьев — верх (22)
    top_leaf_h = to_float("sensor.temperature_and_humidity_sensor_2_humidity")
    top_leaf_t = to_float("sensor.temperature_and_humidity_sensor_2_temperature")

    if top_leaf_h is None:
        warning.append("Верх у листьев (22): нет данных по влажности")
    elif top_leaf_h < 50:
        critical.append(f"Верх у листьев (22): влажность {top_leaf_h:.0f}% — ниже 50%")

    if top_leaf_t is None:
        warning.append("Верх у листьев (22): нет данных по температуре")
    else:
        if is_day:
            if top_leaf_t < 20:
                critical.append(f"Верх у листьев (22): температура {top_leaf_t:.1f}°C — ниже дневной нормы")
            elif top_leaf_t > 25:
                critical.append(f"Верх у листьев (22): температура {top_leaf_t:.1f}°C — выше дневной нормы")
        else:
            if top_leaf_t < 12:
                critical.append(f"Верх у листьев (22): температура {top_leaf_t:.1f}°C — ниже ночной нормы")
            elif top_leaf_t > 18:
                warning.append(f"Верх у листьев (22): температура {top_leaf_t:.1f}°C — выше ночной нормы")

    # 3. Полив — низ по 11
    low_main = to_float("sensor.klubnika_poliv_niz_seryi_humidity")
    if low_main is None:
        warning.append("Низ основной (11): нет данных")
    elif low_main < 40:
        critical.append(f"Низ основной (11): влажность {low_main:.0f}% — ниже порога полива 40%")
    else:
        info.append(f"Низ основной (11): {low_main:.0f}%")

    # 4. Полив — верх по 16
    top_main = to_float("sensor.datchik_vlazhnosti_spotifilum_humidity")
    if top_main is None:
        warning.append("Верх основной (16): нет данных")
    elif top_main < 33:
        critical.append(f"Верх основной (16): влажность {top_main:.0f}% — ниже порога полива 33%")
    else:
        info.append(f"Верх основной (16): {top_main:.0f}%")

    # 5. Поверхности
    low_surface = to_float("sensor.ogurets_vertikalnyi_humidity")                  # 10
    top_surface_far = to_float("sensor.vlazhnost_klubnika_verkh_chernyi_humidity") # 15
    top_surface_win = to_float("sensor.chernyi_poverkhnost_u_okna_humidity")       # 18

    if low_surface is not None and low_surface <= 1:
        warning.append(f"Низ поверхность (10): {low_surface:.0f}% — поверхность пересохла")

    top_surfaces = [x for x in [top_surface_far, top_surface_win] if x is not None]
    if len(top_surfaces) == 2 and all(x <= 1 for x in top_surfaces):
        warning.append("Верхние поверхности (15 и 18): обе пересохли")

    # 6. Аномалии ключевых датчиков
    anomaly_checks = [
        ("11", "Низ основной", "sensor.klubnika_poliv_niz_seryi_humidity"),
        ("16", "Верх основной", "sensor.datchik_vlazhnosti_spotifilum_humidity"),
        ("21", "Низ у листьев влажность", "sensor.temperature_and_humidity_sensor_humidity"),
        ("22", "Верх у листьев влажность", "sensor.temperature_and_humidity_sensor_2_humidity"),
        ("10", "Низ поверхность", "sensor.ogurets_vertikalnyi_humidity"),
        ("15", "Верх дальний поверхность", "sensor.vlazhnost_klubnika_verkh_chernyi_humidity"),
        ("18", "Верх у окна поверхность", "sensor.chernyi_poverkhnost_u_okna_humidity"),
    ]

    for num, label, entity_id in anomaly_checks:
        raw = state_str(entity_id).lower()
        val = to_float(entity_id)

        if raw in ("нет данных", "unknown", "unavailable", "none"):
            warning.append(f"{label} ({num}): датчик недоступен")
        elif val is not None and val == 0:
            pass

    # Вывод
    if critical:
        lines.append("🔴 Срочно")
        for item in critical:
            lines.append(f"• {item}")
        lines.append("")

    if warning:
        lines.append("🟠 Требует внимания")
        for item in warning:
            lines.append(f"• {item}")
        lines.append("")

    if not critical and not warning:
        lines.append("✅ Критичных проблем по растениям не обнаружено.")
        lines.append("")

    if info:
        lines.append("ℹ️ Контрольные точки")
        for item in info:
            lines.append(f"• {item}")

    return "\n".join(lines)

