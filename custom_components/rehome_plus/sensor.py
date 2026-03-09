from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entity import ReHomePlusEntity


@dataclass(frozen=True)
class ZoneDescriptor:
    zone_id: str
    zone_name: str


SYSTEM_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="system_temperature",
        name="System Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="system_humidity",
        name="System Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="system_setpoint",
        name="System Setpoint",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(key="season", name="Season"),
    SensorEntityDescription(key="consumption", name="Thermal Consumption"),
    SensorEntityDescription(key="hot_water_consumption", name="Hot Water Consumption"),
    SensorEntityDescription(key="cold_water_consumption", name="Cold Water Consumption"),
    SensorEntityDescription(key="hotwater_current", name="Hot Water Current"),
    SensorEntityDescription(key="coldwater_current", name="Cold Water Current"),
    SensorEntityDescription(key="calories_current", name="Calories Current"),
    SensorEntityDescription(key="frigories_current", name="Frigories Current"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[SensorEntity] = [ReHomeSystemSensor(coordinator, entry, description) for description in SYSTEM_SENSORS]

    for zone in coordinator.data.get("zones", []):
        zone_id = str(zone.get("id"))
        if not zone_id:
            continue
        zone_name = zone.get("name") or f"Zona {zone_id}"
        desc = ZoneDescriptor(zone_id=zone_id, zone_name=zone_name)
        entities.extend(
            [
                ReHomeZoneTemperatureSensor(coordinator, entry, desc),
                ReHomeZoneHumiditySensor(coordinator, entry, desc),
                ReHomeZoneAdjustmentSensor(coordinator, entry, desc),
            ]
        )

    async_add_entities(entities, True)


class ReHomeSystemSensor(ReHomePlusEntity, SensorEntity):
    entity_description: SensorEntityDescription

    def __init__(self, coordinator, entry: ConfigEntry, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def native_value(self):
        status = self.coordinator.data.get("status", {})
        consumption = self.coordinator.data.get("consumption", {})
        meters = self.coordinator.data.get("meters_history", {})

        mapping = {
            "system_temperature": status.get("envTemperature"),
            "system_humidity": status.get("humidity"),
            "system_setpoint": status.get("setPointTemperature") or status.get("envTemperature"),
            "season": consumption.get("season"),
            "consumption": consumption.get("consumption"),
            "hot_water_consumption": consumption.get("hotWaterConsumption"),
            "cold_water_consumption": consumption.get("coldWaterConsumption"),
            "hotwater_current": meters.get("hotwaterCurrent"),
            "coldwater_current": meters.get("coldwaterCurrent"),
            "calories_current": meters.get("caloriesCurrent"),
            "frigories_current": meters.get("frigoriesCurrent"),
        }
        return mapping[self.entity_description.key]

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float | None]:
        attrs = dict(super().extra_state_attributes)
        if self.entity_description.key == "season":
            attrs["source"] = "consumption"
        return attrs


class ReHomeZoneSensor(ReHomePlusEntity, SensorEntity):
    def __init__(self, coordinator, entry: ConfigEntry, zone: ZoneDescriptor, suffix: str) -> None:
        super().__init__(coordinator, entry)
        self._zone = zone
        self._suffix = suffix

    def _zone_data(self) -> dict:
        return self.coordinator.data.get("zones_data", {}).get(self._zone.zone_id, {})

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float | None]:
        attrs = dict(super().extra_state_attributes)
        attrs["zone_id"] = self._zone.zone_id
        attrs["zone_name"] = self._zone.zone_name
        return attrs


class ReHomeZoneTemperatureSensor(ReHomeZoneSensor):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry: ConfigEntry, zone: ZoneDescriptor) -> None:
        super().__init__(coordinator, entry, zone, "temperature")
        self._attr_name = f"{zone.zone_name} Temperature"
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone.zone_id}_temperature"

    @property
    def native_value(self) -> float | None:
        return self._zone_data().get("envTemperature")


class ReHomeZoneHumiditySensor(ReHomeZoneSensor):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry: ConfigEntry, zone: ZoneDescriptor) -> None:
        super().__init__(coordinator, entry, zone, "humidity")
        self._attr_name = f"{zone.zone_name} Humidity"
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone.zone_id}_humidity"

    @property
    def native_value(self) -> float | None:
        return self._zone_data().get("humidity")


class ReHomeZoneAdjustmentSensor(ReHomeZoneSensor):
    def __init__(self, coordinator, entry: ConfigEntry, zone: ZoneDescriptor) -> None:
        super().__init__(coordinator, entry, zone, "adjustment")
        self._attr_name = f"{zone.zone_name} Setpoint Adjustment"
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone.zone_id}_adjustment"

    @property
    def native_value(self) -> float | None:
        return self._zone_data().get("setPointTempAdjustment")
