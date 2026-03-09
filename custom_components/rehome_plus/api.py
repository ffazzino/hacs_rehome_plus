from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import DEFAULT_BASE_URL, DEFAULT_REQUEST_TIMEOUT, ZONE_FETCH_CONCURRENCY

_LOGGER = logging.getLogger(__name__)


class ReHomePlusApi:
    def __init__(self, session: aiohttp.ClientSession, email: str, password: str, base_url: str | None) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._token: str | None = None
        self._login_lock = asyncio.Lock()
        self.logger = _LOGGER

    async def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        timeout = aiohttp.ClientTimeout(total=DEFAULT_REQUEST_TIMEOUT)
        async with self._session.get(url, params=params, headers=headers, timeout=timeout) as response:
            response.raise_for_status()
            return await response.json()

    async def login(self) -> str:
        gctoken = str(uuid.uuid4()).upper()
        data = await self._request(
            f"login/{quote(self._email)}",
            params={
                "pwd": self._password,
                "rememberme": "false",
                "gctoken": gctoken,
            },
        )
        token = data.get("token")
        if not token:
            raise ValueError("Missing token in login response")
        self._token = token
        return token

    async def _get_token(self) -> str:
        if not self._token:
            async with self._login_lock:
                if not self._token:
                    await self.login()
        return self._token

    async def _request_with_token(self, path: str, params: dict[str, Any] | None = None) -> Any:
        token = await self._get_token()
        try:
            return await self._request(path.format(token=token), params=params)
        except aiohttp.ClientResponseError as err:
            if err.status not in (401, 403):
                raise
        async with self._login_lock:
            self._token = None
            token = await self.login()
        return await self._request(path.format(token=token), params=params)

    async def _safe_fetch_dict(self, label: str, fetcher) -> dict[str, Any]:
        try:
            data = await fetcher()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            self.logger.warning("Unable to load %s: %s", label, err)
            return {}
        return data if isinstance(data, dict) else {}

    async def _safe_fetch_zones(self) -> list[dict[str, Any]]:
        try:
            return await self.fetch_zones()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            self.logger.warning("Unable to load zones: %s", err)
            return []

    async def fetch_status(self) -> dict[str, Any]:
        return await self._request_with_token("statusAndTemperatures/{token}")

    async def fetch_zones(self) -> list[dict[str, Any]]:
        data = await self._request_with_token("zones/{token}")
        return data.get("zones", [])

    async def fetch_zone_temperatures(self, zone_id: str) -> dict[str, Any]:
        return await self._request_with_token("zoneTemperatures/{token}", params={"zoneId": zone_id})

    async def fetch_consumption(self) -> dict[str, Any]:
        return await self._request_with_token("consumption/{token}")

    async def fetch_meters_history(self) -> dict[str, Any]:
        return await self._request_with_token("metersHistory/{token}")

    async def fetch_all(self) -> dict[str, Any]:
        status = await self.fetch_status()
        zones = await self._safe_fetch_zones()
        consumption, meters = await asyncio.gather(
            self._safe_fetch_dict("consumption", self.fetch_consumption),
            self._safe_fetch_dict("meters history", self.fetch_meters_history),
        )

        zone_ids = [str(zone.get("id")) for zone in zones if zone.get("id") is not None]
        semaphore = asyncio.Semaphore(ZONE_FETCH_CONCURRENCY)

        async def _fetch_zone(zone_id: str) -> dict[str, Any] | Exception:
            async with semaphore:
                try:
                    return await self.fetch_zone_temperatures(zone_id)
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                    return err

        zone_payloads = await asyncio.gather(*(_fetch_zone(zone_id) for zone_id in zone_ids))

        zones_data: dict[str, dict[str, Any]] = {}
        for zone_id, payload in zip(zone_ids, zone_payloads, strict=False):
            if isinstance(payload, Exception):
                self.logger.warning("Unable to load zone %s: %s", zone_id, payload)
                continue
            zones_data[zone_id] = payload

        return {
            "status": status,
            "zones": zones,
            "zones_data": zones_data,
            "consumption": consumption,
            "meters_history": meters,
        }

    async def set_system_status(self, status: int, current_setpoint: float) -> None:
        await self._request_with_token(
            "setStatusAndSetpoint/{token}",
            params={"currentSetPoint": current_setpoint, "status": status},
        )

    async def set_system_setpoint(self, target: float, current_setpoint: float) -> None:
        await self._request_with_token(
            "setStatusAndSetpoint/{token}",
            params={"currentSetPoint": current_setpoint, "setPoint": target},
        )
