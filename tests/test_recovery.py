"""Regression coverage for cloud outages (dependency-light tests)."""
import asyncio
import importlib
import sys
import types
import unittest
from unittest.mock import AsyncMock

from tests.test_api import api_module


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    def api(self):
        return api_module.ReHomePlusApi(object(), 'test@example.invalid', 'test', None)

    async def test_null_status_recovers_next_poll_with_new_login(self):
        api = self.api()
        api._token = 'expired'
        api._request = AsyncMock(side_effect=[{'status': None}, {'token': 'fresh'}, {'status': 2}])
        with self.assertRaises(ValueError):
            await api.fetch_status()
        self.assertIsNone(api._token)
        self.assertEqual(await api.fetch_status(), {'status': 2})
        self.assertEqual(api._token, 'fresh')

    async def test_discovery_failure_retries_initial_setup_then_uses_known_ids(self):
        api = self.api()
        api.fetch_status = AsyncMock(return_value={'status': 2})
        api.fetch_zones = AsyncMock(side_effect=[TimeoutError(), [{'id': '1'}], TimeoutError()])
        api.fetch_consumption = AsyncMock(return_value={})
        api.fetch_meters_history = AsyncMock(return_value={})
        api.fetch_zone_temperatures = AsyncMock(return_value={'envTemperature': 22})
        with self.assertRaises(TimeoutError):
            await api.fetch_all()
        initial = await api.fetch_all()
        recovered = await api.fetch_all()
        self.assertEqual(initial, recovered)
        self.assertIn('1', recovered['zones_data'])

    async def test_concurrent_expired_requests_share_one_login(self):
        api = self.api()
        api._token = 'old'
        entered = 0
        ready = asyncio.Event()
        async def request(path, params=None):
            nonlocal entered
            if path.endswith('/old'):
                entered += 1
                if entered == 2:
                    ready.set()
                await ready.wait()
                raise api_module.aiohttp.ClientResponseError(401)
            return {'status': 2}
        async def login():
            await asyncio.sleep(0)
            api._token = 'new'
            return 'new'
        api._request = request
        api.login = AsyncMock(side_effect=login)
        await asyncio.gather(api.fetch_status(), api.fetch_status())
        api.login.assert_awaited_once()

    async def test_cancelled_login_does_not_lock_out_next_poll(self):
        api = self.api()
        entered = asyncio.Event()
        async def blocked(path, params=None):
            entered.set()
            await asyncio.Event().wait()
        api._request = blocked
        task = asyncio.create_task(api.fetch_status())
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        api._request = AsyncMock(side_effect=[{'token': 'new'}, {'status': 1}])
        self.assertEqual(await api.fetch_status(), {'status': 1})

    async def test_invalid_zone_payload_is_not_published(self):
        api = self.api()
        api.fetch_status = AsyncMock(return_value={'status': 1})
        api.fetch_zones = AsyncMock(return_value=[{'id': 1}])
        api.fetch_consumption = AsyncMock(return_value={})
        api.fetch_meters_history = AsyncMock(return_value={})
        api.fetch_zone_temperatures = AsyncMock(return_value=None)
        self.assertEqual((await api.fetch_all())['zones_data'], {})


if __name__ == '__main__':
    unittest.main()

class EntityRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load the real entity classes against a minimal HA interface.
        registry = types.ModuleType('homeassistant.helpers.device_registry')
        registry.DeviceInfo = dict
        sys.modules[registry.__name__] = registry
        class CoordinatorEntity:
            def __init__(self, coordinator):
                self.coordinator = coordinator
        sys.modules['homeassistant.helpers.update_coordinator'].CoordinatorEntity = CoordinatorEntity
        climate = types.ModuleType('homeassistant.components.climate')
        climate.ClimateEntity = type('ClimateEntity', (), {})
        sys.modules[climate.__name__] = climate
        const = types.ModuleType('homeassistant.components.climate.const')
        const.ClimateEntityFeature = types.SimpleNamespace(TARGET_TEMPERATURE=1)
        const.HVACMode = types.SimpleNamespace(OFF='off', HEAT='heat', AUTO='auto')
        sys.modules[const.__name__] = const
        ha_const = types.ModuleType('homeassistant.const')
        ha_const.UnitOfTemperature = types.SimpleNamespace(CELSIUS='C')
        sys.modules[ha_const.__name__] = ha_const
        platform = types.ModuleType('homeassistant.helpers.entity_platform')
        platform.AddEntitiesCallback = object
        sys.modules[platform.__name__] = platform
        cls.module = importlib.import_module('custom_components.rehome_plus.climate')

    def test_null_and_invalid_status_do_not_crash_entities(self):
        entry = types.SimpleNamespace(entry_id='test')
        coordinator = types.SimpleNamespace(data={})
        main = self.module.ReHomeMainClimate(coordinator, entry)
        zone = self.module.ReHomeZoneClimate(coordinator, entry, self.module.ZoneDescriptor('1', 'Room'))
        for value, mode in ((None, None), ('invalid', None), (0, 'off'), ('2', 'auto'), (1, 'heat')):
            coordinator.data = {'status': {'status': value}}
            for entity in (main, zone):
                self.assertEqual(entity.hvac_mode, mode)
                self.assertIn('status_code', entity.extra_state_attributes)

    def test_setup_uses_existing_coordinator_snapshot(self):
        entry = types.SimpleNamespace(entry_id='test')
        coordinator = types.SimpleNamespace(data={'zones': [{'id': '1'}]})
        hass = types.SimpleNamespace(data={'rehome_plus': {'test': {'coordinator': coordinator}}})
        added = []
        # A second positional argument would fail this callback.
        asyncio.run(self.module.async_setup_entry(hass, entry, lambda entities: added.extend(entities)))
        self.assertEqual(len(added), 2)
