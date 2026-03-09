from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN, SYSTEM_STATUS_LABELS


class ReHomePlusEntity(CoordinatorEntity):
    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=DEFAULT_NAME,
            manufacturer="ReHome",
            model="Cloud HVAC",
            configuration_url=self._entry.data.get("base_url"),
        )

    @property
    def extra_state_attributes(self) -> dict[str, str | int]:
        zones = self.coordinator.data.get("zones", [])
        status_code = int(self.coordinator.data.get("status", {}).get("status", 0))
        return {
            "system_status": SYSTEM_STATUS_LABELS.get(status_code, "unknown"),
            "status_code": status_code,
            "zone_count": len(zones),
        }
