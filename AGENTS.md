# AGENTS.md

Context for AI coding agents working in this repository.

## Project summary

Home Assistant custom integration for the Salus iT500 thermostat and water heater. Communicates with the Arrayent "App API" (`sal-emea-p01-api.arrayent.com`), the undocumented backend the Salus mobile app uses. There is no official API. All integration code is under `custom_components/salus_it500/`.

## File map

| File | Purpose |
|---|---|
| `__init__.py` | HA entry point + shared `Salus` HTTP client |
| `climate.py` | `SalusThermostat` entity (polls every 10 min) |
| `water_heater.py` | `SalusWaterHeater` entity (polls every 1 min) |
| `manifest.json` | Integration metadata (domain, version, HACS) |
| `services.yaml` | HA service schema for water heater |

## Non-obvious constraints

**No async HTTP.** The `Salus` base class uses `requests` (synchronous). Any call to `_get_data` or `_set_data` must be wrapped in `hass.async_add_executor_job(...)` — never called directly from an `async` method. Do not replace `requests` with `aiohttp` without refactoring every call site.

**Portal key translation.** The entities still read the old salus-it500.com JSON keys (`CH1currentRoomTemp`, `HWonOffStatus`, ...) and send portal-style payloads (`current_tempZ1`, `auto`, `hwmode_off`, ...). `Salus._to_portal` and `Salus._to_attributes` translate to and from Arrayent attributes. Add new keys there, not in the entities.

**GET, not POST.** zamapi calls must be GET with query parameters. A POST without a body returns a SOAP 500.

**Mode flags.** `A89` off, `A92` manual, `A88` temp-hold. "Heat" means manual mode (`A89=0, A92=1, A88=0`), which is what the portal did. Setpoint writes depend on the current mode (see `_to_attributes`).

**Shared client.** One `Salus` instance per device lives in `hass.data[DOMAIN][id]` and is shared by both entities.

**Water heater temperatures are synthetic.** `current_temperature` and `target_temperature` in `water_heater.py` are not read from the device — they return converted HA defaults based on the on/off state. The Salus API does not expose a water temperature value.

**Retry depth.** `_get_data` and `_set_data` use bounded loops of 3 attempts. `setMultiDeviceAttributes2` often answers 500 even when the write was applied, so a 500 there is accepted and not retried.

## How to make changes

1. **Adding a new sensor value**: map the attribute in `Salus._to_portal` and read it in the entity's `get_data()`. Find the attribute by inspecting `getDeviceAttributesWithValues` for a real device.

2. **Adding a new platform** (e.g., `sensor`): add a new file `sensor.py` following the same pattern as `climate.py`, then register it in `async_setup` in `__init__.py` and add it to `DEFAULT_PLATFORMS`.

3. **Adding a new service**: define the action in `services.yaml` and implement the handler in the relevant entity file.

4. **Changing poll interval**: modify `SCAN_INTERVAL` at the top of the relevant platform file.

## Testing

Run `pytest` (unit tests for the `Salus` client; HA is stubbed in `tests/conftest.py`). To verify end to end:
- Copy `custom_components/salus_it500/` to a running HA instance's `config/custom_components/` directory.
- Restart HA and check the logs (`Settings → System → Logs`) for errors from `custom_components.salus_it500`.
- A real Salus iT500 device and valid credentials are required for end-to-end validation.

## What not to change without careful review

- `APP_AUTHORIZATION` and the login payload in `_get_token` — any change breaks authentication for all users.
- The `CONFIG_SCHEMA` in `__init__.py` — changes here affect how HA validates `configuration.yaml` entries.
- `manifest.json` `version` field — HACS uses this to detect updates.
