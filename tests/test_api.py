from __future__ import annotations

import importlib
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _ClientResponseError(Exception):
    def __init__(self, status):
        self.status = status


def _install_dependency_stubs():
    aiohttp = types.ModuleType("aiohttp")
    aiohttp.ClientSession = object
    aiohttp.ClientTimeout = lambda total: total
    aiohttp.ClientError = Exception
    aiohttp.ClientResponseError = _ClientResponseError
    sys.modules["aiohttp"] = aiohttp

    homeassistant = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    homeassistant.config_entries = config_entries

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object

    helpers = types.ModuleType("homeassistant.helpers")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aiohttp_client.async_get_clientsession = lambda hass: hass.session

    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    update_coordinator.DataUpdateCoordinator = object
    update_coordinator.UpdateFailed = type("UpdateFailed", (Exception,), {})

    sys.modules["homeassistant"] = homeassistant
    sys.modules["homeassistant.config_entries"] = config_entries
    sys.modules["homeassistant.core"] = core
    sys.modules["homeassistant.helpers"] = helpers
    sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
    sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator


_install_dependency_stubs()
api_module = importlib.import_module("custom_components.rehome_plus.api")


class TestReHomePlusApi(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_all_uses_gctoken_when_login_response_omits_token(self):
        api = api_module.ReHomePlusApi(
            session=object(),
            email="simulated@example.invalid",
            password="simulated-password",
            base_url="http://rehome.test/rest/vc_service",
        )
        generated_token = "2d8e6e3a-8b5d-4a5a-930e-4a358e6831e4"
        token = generated_token.upper()
        calls = []

        async def request(path, params=None):
            calls.append((path, params))
            if path.startswith("login/"):
                return {"authenticated": True}
            if path == f"statusAndTemperatures/{token}":
                return {"envTemperature": 21.5, "humidity": 45, "status": 1}
            if path == f"zones/{token}":
                return {"zones": [{"id": "zone-1", "name": "Simulated zone"}]}
            if path == f"consumption/{token}":
                return {"consumption": 12}
            if path == f"metersHistory/{token}":
                return {"caloriesCurrent": 3}
            if path == f"zoneTemperatures/{token}":
                self.assertEqual(params, {"zoneId": "zone-1"})
                return {"envTemperature": 22.0, "humidity": 50}
            self.fail(f"Unexpected request path: {path}")

        api._request = request
        with patch.object(api_module.uuid, "uuid4", return_value=uuid.UUID(generated_token)):
            data = await api.fetch_all()

        self.assertEqual(api._token, token)
        self.assertEqual(calls[0][1]["gctoken"], token)
        self.assertEqual(data["status"]["envTemperature"], 21.5)
        self.assertEqual(data["zones_data"]["zone-1"]["envTemperature"], 22.0)
        self.assertEqual(data["consumption"]["consumption"], 12)
        self.assertEqual(data["meters_history"]["caloriesCurrent"], 3)

    async def test_login_prefers_a_server_issued_token(self):
        api = api_module.ReHomePlusApi(
            session=object(),
            email="simulated@example.invalid",
            password="simulated-password",
            base_url=None,
        )

        async def request(path, params=None):
            return {"token": "server-issued-token"}

        api._request = request

        self.assertEqual(await api.login(), "server-issued-token")
        self.assertEqual(api._token, "server-issued-token")


if __name__ == "__main__":
    unittest.main()
