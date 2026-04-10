# GREENHOUSE v15 — DEVICES CONTEXT

> Это рабочий реестр устройств и датчиков для ИИ и логики системы.
> Здесь сохранена сквозная нумерация №1–№104.
> Формулировки можно дальше упрощать, уточнять и редактировать.

---

## DEVICE 1 — Датчик дыма (около стеллажа)

### №1 | 1.1 Дым
entity: `binary_sensor.1_datchik_dyma_smoke`  
type: smoke  
location: веранда, около стеллажа  
role: критический пожарный датчик  
status: active  

logic:
- если state = on, это пожарная тревога
- приоритет выше всех остальных процессов

actions:
1. отключить щиток веранды
2. проверить отключение по питанию
3. если не помогло — отключить резервный выключатель
4. отправить SOS в Telegram
5. повторять проверку до команды “отбой”

### №2 | 1.2 Батарея
entity: `sensor.dymovoi_signalizator_battery`  
type: battery  
location: внутри датчика  
role: контроль питания датчика дыма  
status: active  

logic:
- если battery < 20%, нужен алерт

actions:
1. отправить уведомление о замене батареи

### №3 | 1.3 Tamper
entity: `binary_sensor.dymovoi_signalizator_tamper`  
type: tamper  
location: внутри датчика  
role: датчик вскрытия / смещения корпуса  
status: ignore  

logic:
- не участвует в основной автоматике

---

## DEVICE 2 — Камера общий план

### №4 | 2.1 Видео
entity: `camera.smart_camera_2`  
type: camera  
location: веранда, общий план стеллажа  
role: визуальный контроль всей конструкции  
status: active  

logic:
- используется по команде и для проверки срабатывания автоматизаций

actions:
1. сделать скрин по запросу
2. при важных действиях можно сравнить кадр до/после

---

## DEVICE 3 — Увлажнитель

### №5 | 3.1 Вкл/выкл
entity: `switch.uviazhnitel_`  
type: humidifier_switch  
location: пол веранды, рядом со стеллажом  
role: основное включение увлажнителя  
status: active  

logic:
- целевой диапазон влажности у листьев: 60–70%
- работает только через отдельное питание
- не держать включённым слишком долго подряд

actions:
1. сначала включить розетку питания №94
2. подождать 30 секунд
3. включить сам увлажнитель №5
4. выключать в обратном порядке

---

## DEVICE 4 — Качество воздуха (верхний ярус)

### №6 | 4.1 CO₂
entity: `sensor.nobito_carbon_dioxide`  
type: co2  
location: верхний ярус  
role: контроль уровня CO₂  
status: active  

logic:
- <400 ppm → мало CO₂
- >1000 ppm → нужен воздухообмен
- >1500 ppm → критично

### №7 | 4.2 VOC
entity: `sensor.nobito_volatile_organic_compounds`  
type: voc  
location: верхний ярус  
role: контроль летучих соединений  
status: test  

logic:
- пока тестовый сенсор
- полезен для отслеживания резких аномалий

### №8 | 4.3 PM10
entity: `sensor.nobito_pm10`  
type: pm10  
location: верхний ярус  
role: контроль пыли  
status: test  

### №9 | 4.4 Влажность
entity: `sensor.nobito_humidity`  
type: air_humidity  
location: верхний ярус  
role: общая влажность воздуха на верхнем ярусе  
status: active  

logic:
- вспомогательный общий датчик
- не заменяет датчик у листьев №65

### №10 | 4.5 Формальдегид
entity: `sensor.nobito_formaldehyde`  
type: formaldehyde  
location: верхний ярус  
role: контроль вредных испарений  
status: test  

### №11 | 4.6 PM2.5
entity: `sensor.nobito_pm2_5`  
type: pm25  
location: верхний ярус  
role: контроль мелкой пыли  
status: test  

### №12 | 4.7 Температура
entity: `sensor.kachestvo_vozdukha_temperature`  
type: air_temperature  
location: верхний ярус  
role: общая температура воздуха на верхнем ярусе  
status: active  

### №13 | 4.8 Индекс качества
entity: `sensor.nobito_air_quality_index`  
type: air_quality_index  
location: верхний ярус  
role: агрегированный индекс качества воздуха  
status: test  

---

## DEVICE 5 — Щиток веранда

### №14 | 5.1 Выключатель
entity: `switch.shchitok_veranda_switch`  
type: power_main  
location: главный щиток веранды  
role: аварийное отключение питания  
status: active  

logic:
- использовать в первую очередь при пожаре

### №15 | 5.2 Всего энергия
entity: `sensor.shchitok_veranda_total_energy`  
type: energy_total  
location: щиток  
role: статистика потребления  
status: active  

### №16 | 5.3 Мощность
entity: `sensor.shchitok_veranda_power`  
type: power  
location: щиток  
role: контроль текущей нагрузки  
status: active  

### №17 | 5.4 Напряжение
entity: `sensor.shchitok_veranda_voltage`  
type: voltage  
location: щиток  
role: контроль качества сети  
status: active  

### №18 | 5.5 Ток
entity: `sensor.shchitok_veranda_current`  
type: current  
location: щиток  
role: контроль нагрузки на проводку  
status: active  

---

## DEVICE 6 — Термостат веранда

### №19 | 6.1 Основной термостат
entity: `climate.termostat_veranda`  
type: thermostat  
location: веранда  
role: управление тёплым полом  
status: active  

logic:
- система инерционная
- шаг изменения уставки должен быть небольшим

### №20 | 6.2 Frost protection
entity: `switch.termostat_veranda_frost_protection`  
type: thermostat_option  
location: настройки термостата  
role: защита от замерзания  
status: ignore  

### №21 | 6.3 Temperature correction
entity: `number.termostat_veranda_temperature_correction`  
type: thermostat_calibration  
location: настройки термостата  
role: калибровка  
status: ignore  

---

## DEVICE 7 — Зашторивание

### №22 | 7.1 Штора
entity: `cover.wifi_curtain_driver_converter_curtain`  
type: curtain  
location: окно у стеллажа  
role: изоляция от окна и работа со светом  
status: active  

logic:
- днём открытие может давать естественный свет и тепло
- ночью закрытие помогает от холода и потерь света

### №23 | 7.2 Режим двигателя
entity: `select.wifi_curtain_driver_converter_motor_mode`  
type: curtain_option  
location: привод шторы  
role: служебная настройка  
status: ignore  

---

## DEVICE 8 — Датчик дыма у щитка

### №24 | 8.1 Дым
entity: `binary_sensor.dymovoi_signalizator_2_smoke`  
type: smoke  
location: над щитком  
role: критический пожарный датчик проводки  
status: active  

logic:
- такой же высокий приоритет, как у №1

actions:
1. отключить щиток
2. отключить резерв
3. уведомить о пожарной тревоге

### №25 | 8.2 Батарея
entity: `sensor.dymovoi_signalizator_2_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

### №26 | 8.3 Tamper
entity: `binary_sensor.dymovoi_signalizator_2_tamper`  
type: tamper  
location: внутри датчика  
role: вскрытие / смещение  
status: ignore  

---

## DEVICE 9 — Датчик утечки воды

### №27 | 9.1 Влага
entity: `binary_sensor.datchik_utechki_vody_moisture`  
type: leak  
location: у канистр / зоны полива  
role: аварийный датчик протечки  
status: active  

logic:
- если сработал, остановить весь полив и насосы

### №28 | 9.2 Батарея
entity: `sensor.datchik_utechki_vody_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 10 — Низ, большой белый горшок, поверхность

### №29 | 10.1 Влажность
entity: `sensor.ogurets_vertikalnyi_humidity`  
type: surface_humidity  
location: нижний ярус, большой белый горшок, верхний слой  
role: ранний индикатор пересыхания поверхности  
status: active  

logic:
- вспомогательный датчик
- не заменяет основной глубинный датчик №35

### №30 | 10.2 Температура
entity: `sensor.ogurets_vertikalnyi_temperature`  
type: surface_temperature  
location: нижний ярус, большой белый горшок, поверхность  
role: температура поверхности грунта  
status: active  

### №31 | 10.3 Батарея
entity: `sensor.ogurets_vertikalnyi_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 11 — Низ, серый горшок, основной

### №32 | 11.1 Влажность
entity: `sensor.klubnika_poliv_niz_seryi_humidity`  
type: soil_humidity_main  
location: нижний ярус, серый горшок, глубоко в грунте  
role: основной датчик полива низа  
status: active  

logic:
- участвует в среднем поливе нижнего яруса
- формула: (№32 + №35 + №41) / 3

### №33 | 11.2 Батарея
entity: `sensor.klubnika_poliv_niz_seryi_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

### №34 | 11.3 Температура
entity: `sensor.klubnika_poliv_niz_seryi_temperature`  
type: soil_temperature  
location: нижний ярус, серый горшок, глубоко  
role: температура корней  
status: active  

---

## DEVICE 12 — Низ, большой белый горшок, основной полив

### №35 | 12.1 Влажность
entity: `sensor.klubnika_vlazhnost_niz_belyi_humidity`  
type: soil_humidity_main  
location: нижний ярус, большой белый горшок, глубоко  
role: основной датчик полива низа  
status: active  

logic:
- участвует в среднем поливе нижнего яруса
- формула: (№32 + №35 + №41) / 3

### №36 | 12.2 Температура
entity: `sensor.klubnika_vlazhnost_niz_belyi_temperature`  
type: soil_temperature  
location: нижний ярус, большой белый горшок, глубоко  
role: температура корней  
status: active  

### №37 | 12.3 Батарея
entity: `sensor.klubnika_vlazhnost_niz_belyi_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 13 — Низ, большой белый горшок, воздух у корней

### №38 | 13.1 Влажность
entity: `sensor.vlazhnost_nizhnii_gorshok_belyi_humidity`  
type: root_air_humidity  
location: нижний ярус, большой белый горшок, поверхность  
role: влажность воздуха у корней  
status: active  

logic:
- вспомогательный экспериментальный датчик
- не равен влажности грунта

### №39 | 13.2 Температура
entity: `sensor.vlazhnost_nizhnii_gorshok_belyi_temperature`  
type: root_air_temperature  
location: нижний ярус, большой белый горшок, поверхность  
role: температура воздуха у корней  
status: active  

### №40 | 13.3 Батарея
entity: `sensor.vlazhnost_nizhnii_gorshok_belyi_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 14 — Низ, круглый горшок у окна, основной

### №41 | 14.1 Влажность
entity: `sensor.sgs01_4_humidity`  
type: soil_humidity_main  
location: нижний ярус, круглый горшок у окна, глубоко  
role: основной датчик полива низа  
status: active  

logic:
- участвует в среднем поливе нижнего яруса
- формула: (№32 + №35 + №41) / 3

### №42 | 14.2 Температура
entity: `sensor.sgs01_4_temperature`  
type: soil_temperature  
location: нижний ярус, круглый горшок у окна, глубоко  
role: температура корней у окна  
status: active  

### №43 | 14.3 Батарея
entity: `sensor.sgs01_4_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 15 — Верх, дальний горшок, поверхность

### №44 | 15.1 Влажность
entity: `sensor.vlazhnost_klubnika_verkh_chernyi_humidity`  
type: surface_humidity  
location: верхний ярус, дальний горшок, поверхность  
role: ранний индикатор пересыхания поверхности  
status: active  

### №45 | 15.2 Температура
entity: `sensor.vlazhnost_klubnika_verkh_chernyi_temperature`  
type: surface_temperature  
location: верхний ярус, дальний горшок, поверхность  
role: температура поверхности  
status: active  

### №46 | 15.3 Батарея
entity: `sensor.vlazhnost_klubnika_verkh_chernyi_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 16 — Верх, дальний горшок, основной

### №47 | 16.1 Влажность
entity: `sensor.datchik_vlazhnosti_spotifilum_humidity`  
type: soil_humidity_main  
location: верхний ярус, дальний горшок, глубоко  
role: основной датчик полива верха  
status: active  

logic:
- участвует в среднем поливе верхнего яруса
- формула: (№47 + №56) / 2

### №48 | 16.2 Температура
entity: `sensor.datchik_vlazhnosti_spotifilum_temperature`  
type: soil_temperature  
location: верхний ярус, дальний горшок, глубоко  
role: температура корней  
status: active  

### №49 | 16.3 Батарея
entity: `sensor.datchik_vlazhnosti_spotifilum_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 17 — Низ, круглый горшок, поверхность

### №50 | 17.1 Влажность
entity: `sensor.vlazhnost_humidity`  
type: surface_humidity  
location: нижний ярус, круглый горшок, поверхность  
role: индикатор верхнего слоя  
status: active  

### №51 | 17.2 Температура
entity: `sensor.vlazhnost_temperature`  
type: surface_temperature  
location: нижний ярус, круглый горшок, поверхность  
role: температура поверхности  
status: active  

### №52 | 17.3 Батарея
entity: `sensor.vlazhnost_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 18 — Верх, горшок у окна, поверхность

### №53 | 18.1 Влажность
entity: `sensor.chernyi_poverkhnost_u_okna_humidity`  
type: surface_humidity  
location: верхний ярус, горшок у окна, поверхность  
role: ранний индикатор пересыхания поверхности  
status: active  

### №54 | 18.2 Температура
entity: `sensor.chernyi_poverkhnost_u_okna_temperature`  
type: surface_temperature  
location: верхний ярус, горшок у окна, поверхность  
role: температура поверхности у окна  
status: active  

### №55 | 18.3 Батарея
entity: `sensor.chernyi_poverkhnost_u_okna_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 19 — Верх, горшок у окна, основной

### №56 | 19.1 Влажность
entity: `sensor.klubnika_verkh_u_okna_humidity`  
type: soil_humidity_main  
location: верхний ярус, горшок у окна, глубоко  
role: основной датчик полива верха  
status: active  

logic:
- участвует в среднем поливе верхнего яруса
- формула: (№47 + №56) / 2

### №57 | 19.2 Температура
entity: `sensor.klubnika_verkh_u_okna_temperature`  
type: soil_temperature  
location: верхний ярус, горшок у окна, глубоко  
role: температура корней у окна  
status: active  

### №58 | 19.3 Батарея
entity: `sensor.klubnika_verkh_u_okna_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 20 — Верх, дальний горшок, воздух у корней

### №59 | 20.1 Влажность
entity: `sensor.datchik_vlazhnosti_verkh_humidity`  
type: root_air_humidity  
location: верхний ярус, дальний горшок, поверхность  
role: влажность воздуха у корней  
status: active  

### №60 | 20.2 Температура
entity: `sensor.datchik_vlazhnosti_verkh_temperature`  
type: root_air_temperature  
location: верхний ярус, дальний горшок, поверхность  
role: температура воздуха у корней  
status: active  

### №61 | 20.3 Батарея
entity: `sensor.datchik_vlazhnosti_verkh_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 21 — Нижний ярус, датчик у листьев

### №62 | 21.1 Влажность
entity: `sensor.temperature_and_humidity_sensor_humidity`  
type: leaf_air_humidity  
location: нижний ярус, на уровне листьев  
role: главный датчик микроклимата низа  
status: active  

logic:
- главный ориентир для увлажнения и вентиляции низа

### №63 | 21.2 Температура
entity: `sensor.temperature_and_humidity_sensor_temperature`  
type: leaf_air_temperature  
location: нижний ярус, на уровне листьев  
role: главная температура для растений низа  
status: active  

### №64 | 21.3 Батарея
entity: `sensor.temperature_and_humidity_sensor_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 22 — Верхний ярус, датчик у листьев

### №65 | 22.1 Влажность
entity: `sensor.temperature_and_humidity_sensor_2_humidity`  
type: leaf_air_humidity  
location: верхний ярус, на уровне листьев  
role: главный датчик микроклимата верха  
status: active  

logic:
- самый важный датчик для увлажнения и вентиляции верха

### №66 | 22.2 Температура
entity: `sensor.temperature_and_humidity_sensor_2_temperature`  
type: leaf_air_temperature  
location: верхний ярус, на уровне листьев  
role: главная температура для растений верха  
status: active  

### №67 | 22.3 Батарея
entity: `sensor.temperature_and_humidity_sensor_2_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 23 — Датчик освещения низ

### №68 | 23.1 Освещенность
entity: `sensor.luminance_sensor_illuminance`  
type: illuminance  
location: нижний ярус  
role: тестовый контроль света  
status: test  

logic:
- не использовать как основной триггер автоматики

### №69 | 23.2 Батарея
entity: `sensor.luminance_sensor_battery`  
type: battery  
location: внутри датчика  
role: контроль питания  
status: test  

---

## DEVICE 24 — Общий датчик температуры и влажности, нижний ярус

### №70 | 24.1 Температура
entity: `sensor.datchik_temeratury_i_vlazhnosti_temperature`  
type: air_temperature  
location: нижний ярус, центр  
role: общая температура воздуха низа  
status: active  

### №71 | 24.2 Влажность
entity: `sensor.datchik_temeratury_i_vlazhnosti_humidity`  
type: air_humidity  
location: нижний ярус, центр  
role: общая влажность воздуха низа  
status: active  

---

## DEVICE 25 — Датчик электричества

### №72 | 25.1 Питание
entity: `binary_sensor.25_datchik_elektrichestva_door`  
type: mains_power_state  
location: ввод питания  
role: контроль наличия основного электричества  
status: active  

logic:
- если питание пропало, нужно отключать лишнюю нагрузку

### №73 | 25.2 Батарея
entity: `sensor.datchik_elektrichestva_battery`  
type: battery  
location: внутри датчика  
role: контроль питания датчика  
status: active  

---

## DEVICE 26 — Уличные датчики

### №74 | 26.1 Выключатель
entity: `switch.temperature_and_humidity_alarm_switch`  
type: sensor_power  
location: улица  
role: служебное питание датчика  
status: ignore  

### №75 | 26.2 Влажность
entity: `sensor.temperature_and_humidity_alarm_humidity`  
type: outdoor_humidity  
location: улица  
role: внешний контекст  
status: ignore  

### №76 | 26.3 Освещенность
entity: `sensor.temperature_and_humidity_alarm_illuminance`  
type: outdoor_illuminance  
location: улица  
role: ориентир для работы шторы  
status: active  

### №77 | 26.4 Температура
entity: `sensor.temperature_and_humidity_alarm_temperature`  
type: outdoor_temperature  
location: улица  
role: главный внешний температурный контекст  
status: active  

### №78 | 26.5 Состояние батареи
entity: `sensor.temperature_and_humidity_alarm_battery_state`  
type: battery_state  
location: внутри датчика  
role: контроль питания  
status: active  

---

## DEVICE 27 — Камера верхний ярус справа

### №79 | 27.1 Видео
entity: `camera.kamera_verkhnii_stellazh_obshchii_plan`  
type: camera  
location: верхний ярус, справа  
role: визуальный контроль дальнего горшка  
status: active  

---

## DEVICE 28 — Камера верхний ярус слева

### №80 | 28.1 Видео
entity: `camera.kamera_na_ogurtsy`  
type: camera  
location: верхний ярус, слева  
role: визуальный контроль горшка у окна и шторы  
status: active  

---

## DEVICE 29 — WiFi переключатель на DIN-рейку 2

### №81 | 29.1 Выключатель
entity: `switch.wifi_perekliuchatel_na_din_reiku_2_switch`  
type: power_backup_switch  
location: щиток  
role: резервное отключение питания  
status: active  

---

## DEVICE 30 — Датчик освещенности верх

### №82 | 30.1 Освещенность
entity: `sensor.lightsensor_illuminance`  
type: illuminance  
location: верхний ярус  
role: тестовый контроль света  
status: test  

### №83 | 30.2 Светимость
entity: `sensor.lightsensor_luminosity`  
type: luminosity  
location: верхний ярус  
role: вспомогательный / неразобранный параметр  
status: test  

---

## DEVICE 31 — Хаб Zigbee

### №84 | 31.1 Проблема
entity: `binary_sensor.multimode_gateway_mini_problem`  
type: zigbee_status  
location: хаб  
role: контроль проблем Zigbee сети  
status: active  

logic:
- если у хаба проблема, часть датчиков может отвалиться

---

## DEVICE 32 — Камера нижний ярус слева

### №85 | 32.1 Видео
entity: `camera.security_camera_4_2`  
type: camera  
location: нижний ярус, слева  
role: визуальный контроль серого горшка  
status: active  

---

## DEVICE 33 — Камера нижний ярус справа

### №86 | 33.1 Видео
entity: `camera.kamera_vertikalnaia_pomidor`  
type: camera  
location: нижний ярус, справа  
role: визуальный контроль большого белого и круглого горшков  
status: active  

---

## DEVICE 34 — Полив верхний ярус

### №87 | 34.1 Полив всего яруса (основной)
entity: `switch.klubnika_poliv_verkh_switch_1`  
type: irrigation_valve_main  
location: верхний ярус, магистраль  
role: основной полив верха  
status: active  

logic:
- работает вместе с насосом верха
- не превышать дневной лимит

### №88 | 34.2 Полив с удобрениями
entity: `switch.klubnika_poliv_verkh_switch_2`  
type: irrigation_valve_fertilizer  
location: верхний ярус, линия удобрений  
role: полив верха с удобрениями  
status: active  

### №89 | 34.3 Защита
entity: `switch.klubnika_poliv_verkh_switch_3`  
type: dry_run_protection  
location: линия полива  
role: защита от сухого хода / аварийная защита  
status: active  

---

## DEVICE 35 — Полив нижний ярус

### №90 | 35.1 Основной полив
entity: `switch.klubnika_poliv_switch_1`  
type: irrigation_valve_main  
location: нижний ярус, магистраль  
role: основной полив низа  
status: active  

### №91 | 35.2 Полив с удобрениями
entity: `switch.klubnika_poliv_switch_2`  
type: irrigation_valve_fertilizer  
location: нижний ярус, линия удобрений  
role: полив низа с удобрениями  
status: active  

### №92 | 35.3 Защита от сухого хода
entity: `switch.klubnika_poliv_switch_3`  
type: dry_run_protection  
location: линия полива низа  
role: защита от сухого хода  
status: active  

---

## DEVICE 36 — Сетевой фильтр (3)

### №93 | 36.1 Насос для перемешивания удобрений
entity: `switch.smart_power_strip_eu_2_socket_4`  
type: mixing_pump  
location: зона удобрений  
role: перемешивание раствора перед поливом с удобрениями  
status: active  

### №94 | 36.2 Розетка для увлажнителя
entity: `switch.smart_power_strip_eu_2_socket_3`  
type: humidifier_power  
location: рядом с увлажнителем  
role: питание увлажнителя  
status: active  

### №95 | 36.3 USB — датчик освещенности верх
entity: `switch.smart_power_strip_eu_2_socket_5`  
type: sensor_power  
location: питание датчика света  
role: питание тестового датчика освещённости верха  
status: active  

---

## DEVICE 37 — Сетевой фильтр (2)

### №96 | 37.1 Свет над верхним ярусом
entity: `switch.setevoi_filtr_klubnika_socket_2`  
type: light_upper  
location: верхний ярус  
role: основной свет верха  
status: active  

### №97 | 37.2 Розетка насос полив верх
entity: `switch.setevoi_filtr_klubnika_socket_4`  
type: pump_power_upper  
location: насос верхнего яруса  
role: питание насоса верха  
status: active  

### №98 | 37.3 Розетка насос полив низ
entity: `switch.setevoi_filtr_klubnika_socket_3`  
type: pump_power_lower  
location: насос нижнего яруса  
role: питание насоса низа  
status: active  

### №99 | 37.4 4 камеры на стеллаже
entity: `switch.setveoi_filtr_klubnika_socket_5`  
type: camera_power  
location: питание камер  
role: включение камер по запросу  
status: need_check  

logic:
- возможно, розетка должна включаться только на время фото / проверки

---

## DEVICE 38 — Сетевой фильтр (1)

### №100 | 38.1 Вентиляторы верх
entity: `switch.setevoi_filtr_novyi_socket_1`  
type: fan_upper  
location: верхний ярус  
role: вентиляция верха  
status: active  

### №101 | 38.2 Вентиляторы низ (USB)
entity: `switch.setevoi_filtr_novyi_usb_1`  
type: fan_lower  
location: нижний ярус  
role: вентиляция низа  
status: active  

### №102 | 38.3 Питание датчика темп/влажности нижнего яруса
entity: `switch.setevoi_filtr_Novyi_socket_2`  
type: sensor_power  
location: нижний ярус  
role: питание общего датчика низа  
status: active  

### №103 | 38.4 Питание датчика CO₂ и др.
entity: `switch.setevoi_filtr_novyi_socket_3`  
type: sensor_power  
location: верхний ярус  
role: питание датчика качества воздуха  
status: active  

### №104 | 38.5 Свет нижний ярус
entity: `switch.setevoi_filtr_novyi_socket_4`  
type: light_lower  
location: нижний ярус  
role: свет нижнего яруса  
status: active  

---

## Итоговые группы для логики

### Главные датчики полива верха
- №47
- №56

### Главные датчики полива низа
- №32
- №35
- №41

### Главные датчики микроклимата
- верх: №65, №66
- низ: №62, №63

### Главные датчики безопасности
- пожар: №1, №24
- протечка: №27
- питание: №72

### Вспомогательные, но важные
- штора: №22
- уличная температура: №77
- уличная освещённость: №76
- Zigbee-хаб: №84

