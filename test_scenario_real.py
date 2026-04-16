from pprint import pprint

from core.execution.scenario_executor import execute_scenario
from ha_client import HomeAssistantClient


SCENARIO_NAME = "fans_top_enable"


def main() -> None:
    ha = HomeAssistantClient()

    print("=" * 80)
    print("REAL RUN SCENARIO:", SCENARIO_NAME)

    result = execute_scenario(
        SCENARIO_NAME,
        dry_run=False,
        ha=ha,
    )

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


if __name__ == "__main__":
    main()
