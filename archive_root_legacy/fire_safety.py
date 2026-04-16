import time


FIRE_SENSOR_IDS = ["1.1", "8.24"]
FIRE_ACTION_SEQUENCE = ["5.14", "29.81"]
FIRE_CHECK_INTERVAL = 5


def get_state(device: dict, ha) -> str | None:
    entity_id = device.get("entity_id", "")

    if not entity_id:
        return None

    state_data = ha.get_state(entity_id)
    if not state_data:
        return None

    return state_data.get("state")


def find_fire_sources(devices: dict, ha) -> list[dict]:
    fire_sources = []

    for device_id in FIRE_SENSOR_IDS:
        device = devices.get(device_id)
        if not device:
            continue

        state = get_state(device, ha)
        if state == "on":
            fire_sources.append(device)

    return fire_sources


def print_fire_plan(devices: dict) -> None:
    print("🚨 FIRE ACTION PLAN:")
    for idx, device_id in enumerate(FIRE_ACTION_SEQUENCE, start=1):
        device = devices.get(device_id)

        if not device:
            print(f"{idx}. OFF -> {device_id} | NOT FOUND")
            continue

        print(f"{idx}. OFF -> {device_id} | {device['name']}")


def execute_fire_shutdown(devices: dict, ha) -> None:
    for device_id in FIRE_ACTION_SEQUENCE:
        device = devices.get(device_id)

        if not device:
            print(f"{device_id} | NOT FOUND")
            continue

        if not device.get("controllable"):
            print(f"{device_id} | {device['name']} | NOT CONTROLLABLE")
            continue

        entity_id = device.get("entity_id", "")
        if not entity_id:
            print(f"{device_id} | {device['name']} | NO ENTITY")
            continue

        result = ha.turn_off(entity_id)
        print(f"{device_id} | {device['name']} | OFF | {result}")

        time.sleep(1)


def cmd_fire(devices: dict, ha) -> None:
    fire_sources = find_fire_sources(devices, ha)

    if not fire_sources:
        print("OK: no fire")
        return

    for device in fire_sources:
        print(f"🔥 FIRE: {device['id']} | {device['name']}")

    print_fire_plan(devices)


def cmd_fire_execute(devices: dict, ha) -> None:
    fire_sources = find_fire_sources(devices, ha)

    if not fire_sources:
        print("❌ ABORT: no fire detected")
        return

    for device in fire_sources:
        print(f"🔥 FIRE: {device['id']} | {device['name']}")

    print_fire_plan(devices)
    print("🚨 EXECUTING FIRE SHUTDOWN...")
    execute_fire_shutdown(devices, ha)


def cmd_monitor_fire(devices: dict, ha) -> None:
    print(f"👀 FIRE MONITOR STARTED | interval={FIRE_CHECK_INTERVAL}s")

    while True:
        fire_sources = find_fire_sources(devices, ha)

        if fire_sources:
            print("🔥 FIRE DETECTED IN MONITOR MODE")

            for device in fire_sources:
                print(f"🔥 FIRE: {device['id']} | {device['name']}")

            print_fire_plan(devices)
            print("🚨 EXECUTING FIRE SHUTDOWN...")
            execute_fire_shutdown(devices, ha)
            print("🛑 FIRE MONITOR STOPPED AFTER SHUTDOWN")
            return

        print("OK: no fire")
        time.sleep(FIRE_CHECK_INTERVAL)
