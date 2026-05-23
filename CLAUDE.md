# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration for the Salus iT500 thermostat + water heater. It communicates with `salus-it500.com` via web scraping (no official API), using session-based auth and token extraction from HTML.

Distributed via HACS; requires HA 2021.12+.

## Development setup

The repo includes a Python virtualenv in `bin/`. To install HA for local development:

```bash
source bin/activate
pip install homeassistant
```

There are no automated tests. Testing requires a real Salus iT500 device and a running Home Assistant instance. Install by copying `custom_components/salus_it500/` into `<ha-config>/custom_components/salus_it500/`.

## Architecture

All code lives in `custom_components/salus_it500/`:

- **`__init__.py`** — Two responsibilities: (1) HA setup (`async_setup`) that loads whichever platforms are configured; (2) the `Salus` base class that handles all HTTP communication with salus-it500.com. Auth flow: POST login form → GET control page → regex-extract `token` from HTML → use token in subsequent AJAX calls.

- **`climate.py`** — `SalusThermostat` inherits from both `ClimateEntity` and `Salus`. Polls every 10 minutes. Supports `HVACMode.HEAT` / `HVACMode.OFF` and target temperature. Data key mapping: `CH1currentSetPoint`, `CH1currentRoomTemp`, `CH1heatOnOffStatus`, `CH1heatOnOff`.

- **`water_heater.py`** — `SalusWaterHeater` inherits from both `WaterHeaterEntity` and `Salus`. Polls every 1 minute. Only tracks on/off state via `HWonOffStatus`. Temperature values are synthetic (converts HA defaults from °F to °C), not read from device.

- **`services.yaml`** — Declares the `set_operation_mode` service for the water heater.

### Key design patterns

- **Multiple inheritance**: both entity classes use `class SalusX(HAEntityClass, Salus)` so they get both HA entity lifecycle and the HTTP helpers from the shared `Salus` base.
- **Blocking I/O in executor**: all `requests` calls are synchronous and wrapped with `hass.async_add_executor_job(self._get_data)` so they don't block the HA event loop.
- **Retry logic**: `_get_token`, `_get_data`, and `_set_data` all retry up to 10 times on failure, resetting `_token` to `None` to force re-authentication on the next attempt.

## Configuration (configuration.yaml)

```yaml
salus_it500:
  username: "EMAIL"
  password: "PASSWORD"
  id: "DEVICEID"          # devId from URL params on salus-it500.com
  platforms:              # optional; defaults to both
    - climate
    - water_heater
```
