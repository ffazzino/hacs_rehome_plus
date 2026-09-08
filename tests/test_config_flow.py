from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _Schema:
    def __init__(self, schema):
        self.schema = schema


class _Marker:
    def __init__(self, key, default=None):
        self.key = key
        self.default = default

    def __hash__(self):
        return hash((self.key, self.default))

    def __eq__(self, other):
        return isinstance(other, _Marker) and self.key == other.key and self.default == other.default


class _TextSelectorConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _TextSelector:
    def __init__(self, config):
        self.config = config


class _TextSelectorType:
    EMAIL = "email"
    PASSWORD = "password"


class _ConfigFlow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__()

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        return None

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}


class _OptionsFlow:
    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_show_menu(self, **kwargs):
        return {"type": "menu", **kwargs}


class _ClientResponseError(Exception):
    def __init__(self, status):
        self.status = status


def _install_homeassistant_stubs():
    vol = types.ModuleType("voluptuous")
    vol.Schema = _Schema
    vol.Required = lambda key, default=None: _Marker(key, default)
    vol.Optional = lambda key, default=None: _Marker(key, default)
    vol.All = lambda *validators: validators
    vol.Coerce = lambda value_type: value_type
    vol.Range = lambda **kwargs: kwargs
    sys.modules["voluptuous"] = vol

    aiohttp = types.ModuleType("aiohttp")
    aiohttp.ClientSession = object
    aiohttp.ClientTimeout = lambda total: total
    aiohttp.ClientError = Exception
    aiohttp.ClientResponseError = _ClientResponseError
    sys.modules["aiohttp"] = aiohttp

    homeassistant = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = _ConfigFlow
    config_entries.OptionsFlow = _OptionsFlow
    config_entries.ConfigEntry = object
    homeassistant.config_entries = config_entries

    data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    data_entry_flow.FlowResult = dict

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object

    helpers = types.ModuleType("homeassistant.helpers")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass: hass.session

    selector = types.ModuleType("homeassistant.helpers.selector")
    selector.TextSelector = _TextSelector
    selector.TextSelectorConfig = _TextSelectorConfig
    selector.TextSelectorType = _TextSelectorType

    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    update_coordinator.DataUpdateCoordinator = object
    update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.data_entry_flow"] = data_entry_flow
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.selector"] = selector
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator


_install_homeassistant_stubs()
config_flow = importlib.import_module("custom_components.rehome_plus.config_flow")


class _Entry:
    def __init__(self, entry_id="entry-1", unique_id="old@example.com"):
        self.entry_id = entry_id
        self.unique_id = unique_id
        self.title = "old@example.com"
        self.data = {
            "email": "old@example.com",
            "password": "old-password",
            "base_url": "http://old.example.test",
        }
        self.options = {"scan_interval": 60}


class _ConfigEntriesManager:
    def __init__(self, entries):
        self._entries = entries
        self.updates = []

    def async_entries(self, domain):
        return self._entries

    def async_update_entry(self, entry, **kwargs):
        self.updates.append((entry, kwargs))
        if "data" in kwargs:
            entry.data = kwargs["data"]
        if "title" in kwargs:
            entry.title = kwargs["title"]
        if "unique_id" in kwargs:
            entry.unique_id = kwargs["unique_id"]


class _Hass:
    def __init__(self, entries):
        self.session = object()
        self.config_entries = _ConfigEntriesManager(entries)


class TestReHomePlusOptionsFlow(unittest.IsolatedAsyncioTestCase):
    async def test_init_shows_settings_and_credentials_menu(self):
        entry = _Entry()
        flow = config_flow.ReHomePlusOptionsFlow(entry)

        result = await flow.async_step_init()

        self.assertEqual(result["type"], "menu")
        self.assertEqual(result["step_id"], "init")
        self.assertEqual(result["menu_options"], ["settings", "credentials"])

    async def test_settings_updates_only_scan_interval_options(self):
        entry = _Entry()
        flow = config_flow.ReHomePlusOptionsFlow(entry)

        result = await flow.async_step_settings({"scan_interval": 120})

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"], {"scan_interval": 120})

    async def test_credentials_are_validated_saved_and_not_returned_to_ui(self):
        entry = _Entry()
        hass = _Hass([entry])
        flow = config_flow.ReHomePlusOptionsFlow(entry)
        flow.hass = hass

        class Api:
            def __init__(self, session, email, password, base_url):
                self.email = email
                self.password = password
                self.base_url = base_url

            async def login(self):
                return "token"

        original_api = config_flow.ReHomePlusApi
        config_flow.ReHomePlusApi = Api
        try:
            result = await flow.async_step_credentials(
                {
                    "email": "new@example.com",
                    "password": "new-secret",
                    "base_url": " http://new.example.test ",
                }
            )
        finally:
            config_flow.ReHomePlusApi = original_api

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"], {"scan_interval": 60})
        self.assertNotIn("new-secret", str(result))
        self.assertEqual(entry.data["email"], "new@example.com")
        self.assertEqual(entry.data["password"], "new-secret")
        self.assertEqual(entry.data["base_url"], "http://new.example.test")
        self.assertEqual(entry.title, "new@example.com")
        self.assertEqual(entry.unique_id, "new@example.com")
        self.assertEqual(len(hass.config_entries.updates), 1)

    async def test_credentials_login_failure_does_not_update_entry(self):
        entry = _Entry()
        hass = _Hass([entry])
        flow = config_flow.ReHomePlusOptionsFlow(entry)
        flow.hass = hass

        class Api:
            def __init__(self, session, email, password, base_url):
                pass

            async def login(self):
                raise ValueError("Missing token in login response")

        original_api = config_flow.ReHomePlusApi
        config_flow.ReHomePlusApi = Api
        try:
            result = await flow.async_step_credentials(
                {
                    "email": "new@example.com",
                    "password": "new-secret",
                    "base_url": "http://new.example.test",
                }
            )
        finally:
            config_flow.ReHomePlusApi = original_api

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "cannot_connect"})
        self.assertNotIn("new-secret", str(result))
        self.assertEqual(entry.data["email"], "old@example.com")
        self.assertEqual(entry.data["password"], "old-password")
        self.assertEqual(hass.config_entries.updates, [])

    async def test_credentials_reject_duplicate_email_before_login(self):
        entry = _Entry()
        other_entry = _Entry(entry_id="entry-2", unique_id="taken@example.com")
        other_entry.data["email"] = "taken@example.com"
        hass = _Hass([entry, other_entry])
        flow = config_flow.ReHomePlusOptionsFlow(entry)
        flow.hass = hass

        result = await flow.async_step_credentials(
            {
                "email": "taken@example.com",
                "password": "new-secret",
                "base_url": "http://new.example.test",
            }
        )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"email": "already_configured"})
        self.assertEqual(hass.config_entries.updates, [])


if __name__ == "__main__":
    unittest.main()
