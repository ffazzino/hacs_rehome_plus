from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .entity import ReHomePlusEntity


@dataclass(frozen=True)
class ZoneDescriptor:
    zone_id: str
    zone_name: str


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities: list[ClimateEntity] = [ReHomeMainClimate(coordinator, entry)]

    for zone in coordinator.data.get("zones", []):
        zone_id = str(zone.get("id"))
        if not zone_id:
            continue
        zone_name = zone.get("name") or f"Zona {zone_id}"
        entities.append(ReHomeZoneClimate(coordinator, entry, ZoneDescriptor(zone_id=zone_id, zone_name=zone_name)))

    async_add_entities(entities, True)


class ReHomeMainClimate(ReHomePlusEntity, ClimateEntity):
    _attr_name = "System"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_system_climate"

    def _status(self) -> dict:
        return self.coordinator.data.get("status", {})

    @property
    def current_temperature(self) -> float | None:
        return self._status().get("envTemperature")

    @property
    def target_temperature(self) -> float | None:
        status = self._status()
        return status.get("setPointTemperature") or status.get("envTemperature")

    @property
    def hvac_mode(self) -> HVACMode:
        status = int(self._status().get("status", 0))
        if status == 0:
            return HVACMode.OFF
        if status == 2:
            return HVACMode.AUTO
        return HVACMode.HEAT

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        current = self.target_temperature or self.current_temperature or 0
        await self.coordinator.api.set_system_setpoint(float(temperature), float(current))
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        status = {
            HVACMode.OFF: 0,
            HVACMode.HEAT: 1,
            HVACMode.AUTO: 2,
        }[hvac_mode]
        current = self.target_temperature or self.current_temperature or 0
        await self.coordinator.api.set_system_status(status, float(current))
        await self.coordinator.async_request_refresh()


class ReHomeZoneClimate(ReHomePlusEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]

    def __init__(self, coordinator, entry: ConfigEntry, zone: ZoneDescriptor) -> None:
        super().__init__(coordinator, entry)
        self._zone = zone
        self._attr_name = zone.zone_name
        self._attr_unique_id = f"{entry.entry_id}_zone_{zone.zone_id}_climate"

    def _zone_data(self) -> dict:
        return self.coordinator.data.get("zones_data", {}).get(self._zone.zone_id, {})

    @property
    def current_temperature(self) -> float | None:
        return self._zone_data().get("envTemperature")

    @property
    def target_temperature(self) -> float | None:
        data = self._zone_data()
        return data.get("currentEnvTempSetPoint") or data.get("envTemperature")

    @property
    def hvac_mode(self) -> HVACMode:
        status = int(self.coordinator.data.get("status", {}).get("status", 0))
        if status == 0:
            return HVACMode.OFF
        if status == 2:
            return HVACMode.AUTO
        return HVACMode.HEAT

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float | None]:
        attrs = dict(super().extra_state_attributes)
        data = self._zone_data()
        attrs["zone_id"] = self._zone.zone_id
        attrs["reported_name"] = data.get("name") or self._zone.zone_name
        attrs["humidity"] = data.get("humidity")
        attrs["setpoint_adjustment"] = data.get("setPointTempAdjustment")
        return attrs
