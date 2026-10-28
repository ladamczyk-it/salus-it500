# Home Assistant custom integration for Salus iT500
Since I've didn't find anything that will support my current home thermostat and setup (thermostat + water heater), based on [salusfy](https://github.com/floringhimie/salusfy) and couple of other inspirations (since I'm python newbie) I've created this custom component.

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ladamczyk-it&repository=https%3A%2F%2Fgithub.com%2Fladamczyk-it%2Fsalus-it500&category=climate%2C+water_heater)

or manually copy contents of `custom_components/salus_it500` into `config/custom_components/salus_it500`

## Configuration
Edit your `config/configuration.yaml` and add there:
```
salus_it500:
  username: "EMAIL"
  password: "PASSWORD"
  id: "DEVICEID"
```
where EMAIL and PASSWORD are your Salus iT500 mobile app credentials.

DEVICEID is the device's `devId`. It is the same number that the old [salus-it500.com](https://salus-it500.com) portal showed in its URL (`control.php?devId=...`). If you have it from there, use it. If the portal is unavailable, you can list your devices from the Arrayent API, which the integration uses:
```
TOKEN=$(curl -s -X POST https://sal-emea-p01-api.arrayent.com/acc/applications/SalusService/sessions \
  -H 'Authorization: 687886-679716122' -H 'Content-Type: application/json' \
  -d "{\"username\":\"EMAIL\",\"password\":\"$(printf %s 'PASSWORD' | md5sum | cut -d' ' -f1)\"}")
curl -s "https://sal-emea-p01-api.arrayent.com/zdk/services/zamapi/getDeviceList?secToken=$(echo "$TOKEN" | jq -r .securityToken)&userId=$(echo "$TOKEN" | jq -r .userId)"
```
and take the `<devId>` from the response.

### How it talks to Salus

The integration uses the same cloud backend as the Salus iT500 mobile app: the Arrayent "App API" at `sal-emea-p01-api.arrayent.com`. Earlier versions scraped the salus-it500.com web portal, which stopped working in October 2026 while the app kept working. The API is undocumented and not endorsed by Salus, so it may change without notice. Thanks to [gvasilakiss/salus-it500](https://github.com/gvasilakiss/salus-it500) for the attribute map.

### Platforms

By default both `climate` and `water_heater` are enabled. You can change that by specifing platforms array eg
```
salus_it500:
  username: "EMAIL"
  password: "PASSWORD"
  id: "DEVICEID"
  platforms:
    - climate
```
will give you thermostat entity only.

### Thermostat attributes

| Attribute | Meaning |
|---|---|
| `command_pending` | `true` when the thermostat is off in the cloud but the boiler relay is still on. The cloud stores an "off" as soon as it is written, but the gateway may not have applied it. If it stays `true`, the gateway has probably lost its cloud session (this happens after internet outages); power-cycle it. A warning is logged when it first appears. |
| `last_report` | When the thermostat last reported its state (UTC). |
| `online_since` | When the gateway last (re)connected to the cloud (UTC). |

Example automation that re-sends "off" and sends a notification:
```yaml
triggers:
  - trigger: state
    entity_id: climate.salus_thermostat
    attribute: command_pending
    to: true
    for: "00:15:00"
actions:
  - action: climate.set_hvac_mode
    target:
      entity_id: climate.salus_thermostat
    data:
      hvac_mode: "off"
  - action: notify.notify
    data:
      message: Salus is off but the boiler is still heating. Power-cycle the gateway.
```

Enjoy your automation.