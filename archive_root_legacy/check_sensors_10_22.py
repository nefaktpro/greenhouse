from ha_client import HomeAssistantClient

ha = HomeAssistantClient()

SENSORS = [
    ("10.29", "НИЗ", "Большой белый", "Поверхность", "Влажность", "sensor.ogurets_vertikalnyi_humidity"),
    ("10.30", "НИЗ", "Большой белый", "Поверхность", "Температура", "sensor.ogurets_vertikalnyi_temperature"),
    ("10.31", "НИЗ", "Большой белый", "Поверхность", "Батарея", "sensor.ogurets_vertikalnyi_battery"),

    ("11.32", "НИЗ", "Серый горшок", "Основной", "Влажность", "sensor.klubnika_poliv_niz_seryi_humidity"),
    ("11.34", "НИЗ", "Серый горшок", "Основной", "Температура", "sensor.klubnika_poliv_niz_seryi_temperature"),
    ("11.33", "НИЗ", "Серый горшок", "Основной", "Батарея", "sensor.klubnika_poliv_niz_seryi_battery"),

    ("12.35", "НИЗ", "Большой белый", "Основной", "Влажность", "sensor.klubnika_vlazhnost_niz_belyi_humidity"),
    ("12.36", "НИЗ", "Большой белый", "Основной", "Температура", "sensor.klubnika_vlazhnost_niz_belyi_temperature"),
    ("12.37", "НИЗ", "Большой белый", "Основной", "Батарея", "sensor.klubnika_vlazhnost_niz_belyi_battery"),

    ("13.38", "НИЗ", "Большой белый", "Воздух у корней", "Влажность", "sensor.vlazhnost_nizhnii_gorshok_belyi_humidity"),
    ("13.39", "НИЗ", "Большой белый", "Воздух у корней", "Температура", "sensor.vlazhnost_nizhnii_gorshok_belyi_temperature"),
    ("13.40", "НИЗ", "Большой белый", "Воздух у корней", "Батарея", "sensor.vlazhnost_nizhnii_gorshok_belyi_battery"),

    ("14.41", "НИЗ", "Круглый у окна", "Основной", "Влажность", "sensor.sgs01_4_humidity"),
    ("14.42", "НИЗ", "Круглый у окна", "Основной", "Температура", "sensor.sgs01_4_temperature"),
    ("14.43", "НИЗ", "Круглый у окна", "Основной", "Батарея", "sensor.sgs01_4_battery"),

    ("15.44", "ВЕРХ", "Дальний горшок", "Поверхность", "Влажность", "sensor.vlazhnost_klubnika_verkh_chernyi_humidity"),
    ("15.45", "ВЕРХ", "Дальний горшок", "Поверхность", "Температура", "sensor.vlazhnost_klubnika_verkh_chernyi_temperature"),
    ("15.46", "ВЕРХ", "Дальний горшок", "Поверхность", "Батарея", "sensor.vlazhnost_klubnika_verkh_chernyi_battery"),

    ("16.47", "ВЕРХ", "Дальний горшок", "Основной", "Влажность", "sensor.datchik_vlazhnosti_spotifilum_humidity"),
    ("16.48", "ВЕРХ", "Дальний горшок", "Основной", "Температура", "sensor.datchik_vlazhnosti_spotifilum_temperature"),
    ("16.49", "ВЕРХ", "Дальний горшок", "Основной", "Батарея", "sensor.datchik_vlazhnosti_spotifilum_battery"),

    ("17.50", "НИЗ", "Круглый", "Поверхность", "Влажность", "sensor.vlazhnost_humidity"),
    ("17.51", "НИЗ", "Круглый", "Поверхность", "Температура", "sensor.vlazhnost_temperature"),
    ("17.52", "НИЗ", "Круглый", "Поверхность", "Батарея", "sensor.vlazhnost_battery"),

    ("18.53", "ВЕРХ", "У окна", "Поверхность", "Влажность", "sensor.chernyi_poverkhnost_u_okna_humidity"),
    ("18.54", "ВЕРХ", "У окна", "Поверхность", "Температура", "sensor.chernyi_poverkhnost_u_okna_temperature"),
    ("18.55", "ВЕРХ", "У окна", "Поверхность", "Батарея", "sensor.chernyi_poverkhnost_u_okna_battery"),

    ("19.56", "ВЕРХ", "У окна", "Основной", "Влажность", "sensor.klubnika_verkh_u_okna_humidity"),
    ("19.57", "ВЕРХ", "У окна", "Основной", "Температура", "sensor.klubnika_verkh_u_okna_temperature"),
    ("19.58", "ВЕРХ", "У окна", "Основной", "Батарея", "sensor.klubnika_verkh_u_okna_battery"),

    ("20.59", "ВЕРХ", "Дальний горшок", "Воздух у корней", "Влажность", "sensor.datchik_vlazhnosti_verkh_humidity"),
    ("20.60", "ВЕРХ", "Дальний горшок", "Воздух у корней", "Температура", "sensor.datchik_vlazhnosti_verkh_temperature"),
    ("20.61", "ВЕРХ", "Дальний горшок", "Воздух у корней", "Батарея", "sensor.datchik_vlazhnosti_verkh_battery"),

    ("21.62", "НИЗ", "У куста", "Воздух", "Влажность воздуха", "sensor.temperature_and_humidity_sensor_humidity"),
    ("21.63", "НИЗ", "У куста", "Воздух", "Температура воздуха", "sensor.temperature_and_humidity_sensor_temperature"),
    ("21.64", "НИЗ", "У куста", "Воздух", "Батарея", "sensor.temperature_and_humidity_sensor_battery"),

    ("22.65", "ВЕРХ", "У куста", "Воздух", "Влажность воздуха", "sensor.temperature_and_humidity_sensor_2_humidity"),
    ("22.66", "ВЕРХ", "У куста", "Воздух", "Температура воздуха", "sensor.temperature_and_humidity_sensor_2_temperature"),
    ("22.67", "ВЕРХ", "У куста", "Воздух", "Батарея", "sensor.temperature_and_humidity_sensor_2_battery"),
]


def get_state(entity_id: str) -> str:
    data = ha.get_state(entity_id)
    if not data:
        return "ERROR"
    return str(data.get("state", "unknown"))


def main():
    current_zone = None
    current_group = None

    for sensor_id, zone, plant, layer, metric, entity_id in SENSORS:
        if zone != current_zone:
            current_zone = zone
            current_group = None
            print()
            print("=" * 70)
            print(zone)
            print("=" * 70)

        group = (plant, layer)
        if group != current_group:
            current_group = group
            print()
            print(f"{plant} | {layer}")

        value = get_state(entity_id)
        print(f"  {sensor_id:>5} | {metric:<20} | {value:<8} | {entity_id}")


if __name__ == "__main__":
    main()

