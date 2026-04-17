# GREENHOUSE v17 Migration Notes

## Canonical registry
- data/registry/devices.csv
- data/registry/action_map.json
- data/registry/device_capabilities.json
- data/registry/scenarios.json
- data/registry/registry_manifest.json

## Runtime moved out of root
- data/runtime/
- data/logs/
- data/memory/

## Important principle
Interfaces must edit registry/data via services, not Python business logic.

## Next layer
Web Admin / Telegram Admin should call:
- registry_service
- scenario_service
- capability_service
- admin_registry_api
