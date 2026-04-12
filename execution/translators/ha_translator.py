from __future__ import annotations


def translate_operation_to_ha(operation: str, entity_id: str) -> tuple[str, str, dict]:
    """
    Returns: (domain, service, service_data)
    """
    domain = entity_id.split(".", 1)[0]

    operation = operation.strip().lower()

    if operation in ("turn_on", "on", "start"):
        return domain, "turn_on", {"entity_id": entity_id}

    if operation in ("turn_off", "off", "stop"):
        return domain, "turn_off", {"entity_id": entity_id}

    if operation == "open":
        return domain, "open_cover", {"entity_id": entity_id}

    if operation == "close":
        return domain, "close_cover", {"entity_id": entity_id}

    raise ValueError(f"Unsupported operation: {operation}")
