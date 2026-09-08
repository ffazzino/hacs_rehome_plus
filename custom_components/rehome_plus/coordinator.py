from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ReHomePlusApi
from .const import CONF_BASE_URL, CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL


def build_coordinator(hass: HomeAssistant, entry: ConfigEntry) -> DataUpdateCoordinator:
    api = ReHomePlusApi(
        session=async_get_clientsession(hass),
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        base_url=entry.data.get(CONF_BASE_URL),
    )

    async def async_update_data():
        try:
            async with asyncio.timeout(90):
                return await api.fetch_all()
        except ValueError as err:
            raise UpdateFailed("Invalid response from ReHome cloud") from err

    interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = DataUpdateCoordinator(
        hass,
        logger=api.logger,
        name="ReHome Plus",
        update_method=async_update_data,
        update_interval=timedelta(seconds=interval),
    )
    coordinator.api = api
    return coordinator
