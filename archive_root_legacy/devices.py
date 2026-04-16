import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV_PATH = BASE_DIR / "devices.csv"


def str_to_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def load_devices(csv_path: str | None = None) -> dict:
    path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH

    if not path.exists():
        raise FileNotFoundError(f"Devices file not found: {path}")

    devices = {}

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required_fields = {
            "id",
            "parent_id",
            "name",
            "type",
            "entity_id",
            "unit",
            "location",
            "controllable",
            "critical",
        }

        if not reader.fieldnames:
            raise ValueError("devices.csv is empty or missing header")

        missing_fields = required_fields - set(reader.fieldnames)
        if missing_fields:
            raise ValueError(f"devices.csv missing fields: {', '.join(sorted(missing_fields))}")

        for row in reader:
            device_id = row["id"].strip()

            if not device_id:
                continue

            if device_id in devices:
                raise ValueError(f"Duplicate device id found: {device_id}")

            devices[device_id] = {
                "id": device_id,
                "parent_id": row["parent_id"].strip(),
                "name": row["name"].strip(),
                "type": row["type"].strip(),
                "entity_id": row["entity_id"].strip(),
                "unit": row["unit"].strip(),
                "location": row["location"].strip(),
                "controllable": str_to_bool(row["controllable"]),
                "critical": str_to_bool(row["critical"]),
            }

    return devices


def get_device(devices: dict, device_id: str):
    return devices.get(device_id)
