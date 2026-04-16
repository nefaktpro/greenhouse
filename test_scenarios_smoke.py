from pprint import pprint

from core.execution.scenario_executor import execute_scenario

TO_TEST = [
    "humidifier_start",
    "humidifier_stop",
    "fans_top_enable",
    "fans_bottom_enable",
    "emergency_fire_smoke",
    "emergency_leak",
]

for scenario_name in TO_TEST:
    print("=" * 80)
    print("SCENARIO:", scenario_name)
    result = execute_scenario(scenario_name, dry_run=True)
    pprint({
        "success": result.success,
        "scenario_name": result.scenario_name,
        "dry_run": result.dry_run,
        "error": result.error,
        "steps_count": len(result.step_results),
    })
    for step in result.step_results:
        pprint({
            "success": step.success,
            "action": step.action,
            "details": step.details,
        })
