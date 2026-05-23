# AGENTS.md

Context for AI coding agents working in this repository.

## Project summary

Home Assistant custom integration for the Salus iT500 thermostat and water heater. Communicates with `salus-it500.com` via web scraping — there is no official API. All integration code is under `custom_components/salus_it500/`.

## File map

| File | Purpose |
|---|---|
| `__init__.py` | HA entry point + `Salus` HTTP base class |
| `climate.py` | `SalusThermostat` entity (polls every 10 min) |
| `water_heater.py` | `SalusWaterHeater` entity (polls every 1 min) |
| `manifest.json` | Integration metadata (domain, version, HACS) |
| `services.yaml` | HA service schema for water heater |

## Non-obvious constraints

**No async HTTP.** The `Salus` base class uses `requests` (synchronous). Any call to `_get_data` or `_set_data` must be wrapped in `hass.async_add_executor_job(...)` — never called directly from an `async` method. Do not replace `requests` with `aiohttp` without refactoring every call site.

**Web scraping auth.** Token is extracted with a regex from an HTML page, not from a JSON response. If `salus-it500.com` changes its HTML, `_get_token` in `__init__.py` silently fails. The regex is the most fragile line in the codebase.

**Multiple inheritance MRO.** Both entity classes inherit `(HAEntityClass, Salus)`. HA entity classes define `__init__` — `Salus.__init__` must be called explicitly via `super(SalusX, self).__init__(username, password, deviceId)`. Don't change the inheritance order without checking the MRO.

**Water heater temperatures are synthetic.** `current_temperature` and `target_temperature` in `water_heater.py` are not read from the device — they return converted HA defaults based on the on/off state. The Salus API does not expose a water temperature value.

**Retry depth.** All three HTTP methods (`_get_token`, `_get_data`, `_set_data`) use recursive retries up to 10 attempts. A stack overflow is theoretically possible under sustained failures, though unlikely in practice.

## How to make changes

1. **Adding a new sensor value**: add a key to `get_data()` in the relevant entity file, sourced from the JSON returned by `ajax_device_values.php`. Find the key name by inspecting the actual response from the device.

2. **Adding a new platform** (e.g., `sensor`): add a new file `sensor.py` following the same pattern as `climate.py`, then register it in `async_setup` in `__init__.py` and add it to `DEFAULT_PLATFORMS`.

3. **Adding a new service**: define the action in `services.yaml` and implement the handler in the relevant entity file.

4. **Changing poll interval**: modify `SCAN_INTERVAL` at the top of the relevant platform file.

## Testing

No automated tests exist. To verify a change:
- Copy `custom_components/salus_it500/` to a running HA instance's `config/custom_components/` directory.
- Restart HA and check the logs (`Settings → System → Logs`) for errors from `custom_components.salus_it500`.
- A real Salus iT500 device and valid credentials are required for end-to-end validation.

## What not to change without careful review

- The `_get_token` regex — any change breaks authentication for all users.
- The `CONFIG_SCHEMA` in `__init__.py` — changes here affect how HA validates `configuration.yaml` entries.
- `manifest.json` `version` field — HACS uses this to detect updates.
