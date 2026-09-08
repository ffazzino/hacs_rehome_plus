# ReHome Plus for Home Assistant

ReHome Plus is a custom Home Assistant integration designed for HACS installation.

It extends the original prototype in this repository with:

- a dedicated HACS package layout
- config flow and options flow
- a richer coordinator that loads system status, zones, consumption, and meter history
- a controllable main climate entity
- room climate snapshots for every zone
- system and per-room sensors

## What the integration can control

The ReHome API currently exposes writable controls for the main system thermostat:

- system mode: `Off`, `Manual`, `Auto`
- target setpoint

The API also exposes room data for each zone:

- current temperature
- humidity
- reported room setpoint
- setpoint adjustment

At the moment, no documented per-zone write endpoint is included in this repository, so room entities are exposed as informative climate snapshots and sensors rather than writable thermostats.

## Installation with HACS

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository of type `Integration`.
3. Install `ReHome Plus`.
4. Restart Home Assistant.
5. Go to `Settings -> Devices & Services -> Add Integration`.
6. Search for `ReHome Plus`.
7. Enter your ReHome email, password, and optionally a custom base URL.

## Repository layout

For HACS, the relevant folder is:

`custom_components/rehome_plus`

In this workspace the HACS package lives under:

`/Users/ffazzino/XCODE/Rehom_HA/hacs_rehome_plus`

## Entities created

- `climate`:
  - 1 main controllable thermostat
  - 1 read-only climate snapshot per room
- `sensor`:
  - system temperature, humidity, setpoint
  - consumption summary values
  - meter current values
  - room temperature, humidity, room setpoint adjustment

## Notes

- Polling is cloud-based.
- Default refresh interval is 60 seconds and can be changed from integration options.
- ReHome credentials can be updated from `Settings -> Devices & Services -> ReHome Plus -> Configure -> Update credentials` without removing the integration.
- The integration keeps the current prototype untouched because it uses a separate domain: `rehome_plus`.

## Recovery from cloud outages (1.0.1)

The coordinator retries transient failures at the configured polling interval.
Invalid or missing system status is treated as a failed update, and the next
poll starts a new session. Initial zone discovery failures retry setup; later
discovery failures reuse known zone IDs so room readings can recover.
Each refresh has a 90-second overall deadline, with 20-second request timeouts.
Entities use the initial coordinator snapshot without requesting another cloud
refresh during platform setup. Options reloads use Home Assistant's managed
config-entry lifecycle.

After updating the integration files, restart Home Assistant once to load the
Python changes. No periodic reload automation is needed. A cloud outage can
still make readings unavailable until the service responds again.

Regression checks: `python3 -m unittest discover -v` (dependency-light unit
tests; not a full Home Assistant runtime suite).
