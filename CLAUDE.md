# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration for the Salus iT500 thermostat + water heater. It talks to the Arrayent "App API" (`sal-emea-p01-api.arrayent.com`), the undocumented cloud backend that the Salus mobile app uses. Earlier versions scraped `salus-it500.com`, which went down in October 2026.

Distributed via HACS; requires HA 2021.12+.

## Development setup

The repo includes a Python virtualenv in `bin/`. To install HA for local development:

```bash
source bin/activate
pip install homeassistant
```

Unit tests for the `Salus` client live in `tests/` (HA is stubbed in `tests/conftest.py`; run `pytest`). End-to-end testing requires a real Salus iT500 device and a running Home Assistant instance. Install by copying `custom_components/salus_it500/` into `<ha-config>/custom_components/salus_it500/`.

## Architecture

All code lives in `custom_components/salus_it500/`:

- **`__init__.py`** — Two responsibilities: (1) HA setup (`async_setup`) that loads whichever platforms are configured; (2) the `Salus` client that handles all HTTP communication. One instance per device is stored in `hass.data[DOMAIN][id]` and shared by both entities. Auth flow: POST JSON `{username, md5(password)}` to `/acc/applications/SalusService/sessions` with the app's `Authorization` header → `securityToken` + `userId` → GET `/zdk/services/zamapi/<method>` (POST without a body is rejected). `_get_data` maps device attributes back to the old portal key names, and `_set_data` maps portal-style payloads to attribute writes, so the entity files did not change.

- **`climate.py`** — `SalusThermostat` (`ClimateEntity`) using the shared `Salus` client. Polls every 10 minutes. Supports `HVACMode.HEAT` / `HVACMode.OFF` and target temperature. Data key mapping: `CH1currentSetPoint`, `CH1currentRoomTemp`, `CH1heatOnOffStatus`, `CH1heatOnOff`, plus `CH1offPending`, `lastReport` and `onlineSince`, which are exposed as the `command_pending`, `last_report` and `online_since` state attributes. The cloud echoes a written `A89` (off) at once, while `A87` (relay) comes from the device, so off with the relay on means the gateway has not applied the write.

- **`water_heater.py`** — `SalusWaterHeater` (`WaterHeaterEntity`) using the shared `Salus` client. Polls every 1 minute. Only tracks on/off state via `HWonOffStatus`. Temperature values are synthetic (converts HA defaults from °F to °C), not read from device.

- **`services.yaml`** — Declares the `set_operation_mode` service for the water heater.

### Key design patterns

- **Shared client + cache**: one login and one attribute fetch per `DATA_TTL` serve both entities; writes drop the cache.
- **Attribute map**: A = heating zone 1, C = hot water, S = system; temperatures ×100. Mode flags: `A89` off, `A92` manual, `A88` temp-hold. In manual mode a setpoint write goes to `A85` + `A93` (as the app does); setting `A88` there would leave manual and temp-hold both on.
- **Blocking I/O in executor**: all `requests` calls are synchronous and wrapped with `hass.async_add_executor_job(self._get_data)` so they don't block the HA event loop.
- **Retry logic**: `_get_data` and `_set_data` retry up to 3 times, resetting `_token` to force re-authentication. A 500 from `setMultiDeviceAttributes2` is a known false negative and is not retried.

## Configuration (configuration.yaml)

```yaml
salus_it500:
  username: "EMAIL"
  password: "PASSWORD"
  id: "DEVICEID"          # Arrayent devId (same as the old portal's devId)
  platforms:              # optional; defaults to both
    - climate
    - water_heater
```
