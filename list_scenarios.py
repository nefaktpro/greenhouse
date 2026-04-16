from core.registry.registry_loader import get_all_scenarios

scenarios = get_all_scenarios()
print("TOTAL:", len(scenarios))
for name in sorted(scenarios.keys()):
    print(name)
