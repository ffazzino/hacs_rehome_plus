from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import ReHomePlusApi
from .const import (
    CONF_BASE_URL,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


def _base_url(value: str | None) -> str:
    if not value:
        return DEFAULT_BASE_URL
    return value.strip() or DEFAULT_BASE_URL


def _credentials_data(data: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_EMAIL: data[CONF_EMAIL].strip(),
        CONF_PASSWORD: data[CONF_PASSWORD],
        CONF_BASE_URL: _base_url(data.get(CONF_BASE_URL)),
    }


def _scan_interval_options(options: dict[str, Any]) -> dict[str, int]:
    return {
        CONF_SCAN_INTERVAL: options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    }


async def _async_validate_credentials(hass, data: dict[str, Any]) -> None:
    api = ReHomePlusApi(
        session=async_get_clientsession(hass),
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        base_url=data.get(CONF_BASE_URL),
    )
    await api.login()


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
            ),
            vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
        }
    )


def _credentials_schema(config_entry: config_entries.ConfigEntry) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_EMAIL, default=config_entry.data.get(CONF_EMAIL, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
            ),
            vol.Optional(CONF_BASE_URL, default=config_entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)): str,
        }
    )


class ReHomePlusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _credentials_data(user_input)
            try:
                await _async_validate_credentials(self.hass, data)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(data[CONF_EMAIL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=data[CONF_EMAIL],
                    data=data,
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return ReHomePlusOptionsFlow(config_entry)


class ReHomePlusOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["settings", "credentials"],
        )

    async def async_step_settings(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self._config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL))
                }
            ),
        )

    async def async_step_credentials(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            data = _credentials_data(user_input)

            if self._email_already_configured(data[CONF_EMAIL]):
                errors[CONF_EMAIL] = "already_configured"
            else:
                try:
                    await _async_validate_credentials(self.hass, data)
                except Exception:
                    errors["base"] = "cannot_connect"
                else:
                    update_kwargs: dict[str, Any] = {
                        "data": {
                            **self._config_entry.data,
                            **data,
                        },
                        "title": data[CONF_EMAIL],
                    }
                    if self._config_entry.unique_id is not None:
                        update_kwargs["unique_id"] = data[CONF_EMAIL]
                    self.hass.config_entries.async_update_entry(self._config_entry, **update_kwargs)
                    return self.async_create_entry(
                        title="",
                        data=_scan_interval_options(self._config_entry.options),
                    )

        return self.async_show_form(
            step_id="credentials",
            data_schema=_credentials_schema(self._config_entry),
            errors=errors,
        )

    def _email_already_configured(self, email: str) -> bool:
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id == self._config_entry.entry_id:
                continue
            if entry.unique_id == email or entry.data.get(CONF_EMAIL) == email:
                return True
        return False
