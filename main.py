import sys

from devices import load_devices
from ha_client import HomeAssistantClient
from fire_safety import cmd_fire, cmd_fire_execute, cmd_monitor_fire
from status_view import build_plants_low_text, build_plants_high_text, build_plants_full_text


VERSION = "v15"


def print_status(device: dict, ha: HomeAssistantClient) -> None:
    entity_id = device.get("entity_id", "")

    if not entity_id:
        print(f"{device['id']} | {device['name']} | no entity")
        return

    state_data = ha.get_state(entity_id)
    if not state_data:
        print(f"{device['id']} | {device['name']} | ERROR")
        return

    state = state_data.get("state", "unknown")
    print(f"{device['id']} | {device['name']} | {state}")


def cmd_status(devices: dict, ha: HomeAssistantClient) -> None:
    check_ids = ["1.1", "8.24", "5.14", "29.81", "38.101"]

    for device_id in check_ids:
        device = devices.get(device_id)
        if not device:
            print(f"{device_id} | NOT FOUND")
            continue
        print_status(device, ha)


def cmd_critical(devices: dict, ha: HomeAssistantClient) -> None:
    critical_devices = [
        d for d in devices.values()
        if d.get("critical") and d.get("entity_id")
    ]

    if not critical_devices:
        print("No critical devices found")
        return

    for device in critical_devices:
        print_status(device, ha)


def cmd_plants_low(ha: HomeAssistantClient) -> None:
    print(build_plants_low_text(ha))


def cmd_plants_high(ha: HomeAssistantClient) -> None:
    print(build_plants_high_text(ha))


def cmd_plants(ha: HomeAssistantClient) -> None:
    print(build_plants_full_text(ha))


def cmd_switch(devices: dict, ha: HomeAssistantClient, device_id: str, turn_on: bool) -> None:
    device = devices.get(device_id)

    if not device:
        print(f"{device_id} | NOT FOUND")
        return

    if not device.get("controllable"):
        print(f"{device_id} | {device['name']} | NOT CONTROLLABLE")
        return

    entity_id = device.get("entity_id", "")
    if not entity_id:
        print(f"{device_id} | {device['name']} | NO ENTITY")
        return

    result = ha.turn_on(entity_id) if turn_on else ha.turn_off(entity_id)

    action = "ON" if turn_on else "OFF"
    print(f"{device_id} | {device['name']} | {action} | {result}")


def print_help() -> None:
    print(f"greenhouse {VERSION}")
    print("Usage:")
    print("  python3 main.py status")
    print("  python3 main.py critical")
    print("  python3 main.py fire")
    print("  python3 main.py fire_execute")
    print("  python3 main.py monitor_fire")
    print("  python3 main.py plants_low")
    print("  python3 main.py plants_high")
    print("  python3 main.py plants")
    print("  python3 main.py on <device_id>")
    print("  python3 main.py off <device_id>")


def main():
    devices = load_devices()
    ha = HomeAssistantClient()

    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    if command == "status":
        cmd_status(devices, ha)
        return

    if command == "critical":
        cmd_critical(devices, ha)
        return

    if command == "fire":
        cmd_fire(devices, ha)
        return

    if command == "fire_execute":
        cmd_fire_execute(devices, ha)
        return

    if command == "monitor_fire":
        cmd_monitor_fire(devices, ha)
        return

    if command == "plants_low":
        cmd_plants_low(ha)
        return

    if command == "plants_high":
        cmd_plants_high(ha)
        return

    if command == "plants":
        cmd_plants(ha)
        return

    if command in {"on", "off"}:
        if len(sys.argv) < 3:
            print_help()
            return

        device_id = sys.argv[2]
        cmd_switch(devices, ha, device_id, turn_on=(command == "on"))
        return

    print_help()


if __name__ == "__main__":
    main()
