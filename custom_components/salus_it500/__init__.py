"""The Salus iT500 component."""
import time
import hashlib
import logging
import threading
import requests
import xml.etree.ElementTree as ET
import voluptuous as vol

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ID,
)

_LOGGER = logging.getLogger(__name__)

__version__ = "0.1.0"

DOMAIN = "salus_it500"
PLATFORMS = "platforms"
DEFAULT_PLATFORMS = [CLIMATE_DOMAIN, WATER_HEATER_DOMAIN]

# A single getDeviceAttributesWithValues call carries both the thermostat (A*)
# and water heater (C*) data, so we cache it briefly and serve both entities
# from one network call. Keep below the fastest poll interval (water_heater = 60s)
# so each poll still gets reasonably fresh data.
DATA_TTL = 115          # seconds
# Refresh the session token proactively instead of only after a call fails.
TOKEN_TTL = 30 * 60    # seconds

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_ID): cv.string,
                vol.Optional(PLATFORMS, default=DEFAULT_PLATFORMS): vol.All(cv.ensure_list, [cv.string]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass, hass_config):
    """Set up Generic Water Heaters."""
    config = hass_config.get(DOMAIN)

    # Build a single shared client so both platforms reuse one session, one
    # login and one cached data fetch instead of authenticating separately.
    salus = Salus(config[CONF_USERNAME], config[CONF_PASSWORD], config[CONF_ID])
    hass.data.setdefault(DOMAIN, {})[config[CONF_ID]] = salus

    if CLIMATE_DOMAIN in config[PLATFORMS]:
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                CLIMATE_DOMAIN,
                DOMAIN,
                config,
                hass_config,
            )
        )

    if WATER_HEATER_DOMAIN in config[PLATFORMS]:
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                WATER_HEATER_DOMAIN,
                DOMAIN,
                config,
                hass_config,
            )
        )
        
    return True

class Salus:
    """HTTP client for the Arrayent "App API" behind the Salus iT500 phone app.

    salus-it500.com (the old web portal) went down on 2026-10-22, while the
    Arrayent backend the app and gateway use kept working. Reads and writes go
    to sal-emea-p01-api.arrayent.com instead.

    The entities were written against the portal's JSON, so _get_data()
    translates Arrayent attributes back to the portal key names and
    _set_data() translates portal-style payloads to attribute writes. That keeps
    climate.py / water_heater.py unchanged.

    Caches the session token and the most recent attribute fetch so that
    the climate and water_heater entities reuse a single login and, most of
    the time, a single read per cache window instead of calling out separately.
    All public methods run in HA's executor (blocking I/O), so a lock guards
    the shared token/data state against overlapping polls.
    """

    HOST = "https://sal-emea-p01-api.arrayent.com"
    LOGIN_URL = HOST + "/acc/applications/SalusService/sessions"
    API_URL = HOST + "/zdk/services/zamapi/"
    # Identifies the Salus tenant on Arrayent; same value the iT500 app sends.
    APP_AUTHORIZATION = "687886-679716122"
    TIMEOUT = 30

    def __init__(self, username, password, deviceId):
        self._username = username
        self._password_md5 = hashlib.md5(password.encode("utf-8")).hexdigest()
        self._deviceId = deviceId
        self._session = requests.Session()
        self._lock = threading.Lock()
        self._token = None
        self._user_id = None
        self._token_time = 0.0
        self._data = None
        self._data_time = 0.0
        self._attrs = {}  # last raw attribute map; writes depend on the current mode

    def _token_valid(self) -> bool:
        return self._token is not None and (time.monotonic() - self._token_time) < TOKEN_TTL

    def _get_token(self) -> None:
        """(Re)authenticate and store a fresh token. Caller must hold the lock."""
        headers = {
            "Authorization": self.APP_AUTHORIZATION,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {"username": self._username, "password": self._password_md5}

        r = self._session.post(self.LOGIN_URL, json=payload, headers=headers, timeout=self.TIMEOUT)
        r.raise_for_status()
        data = r.json()
        self._token = data["securityToken"]
        self._user_id = data["userId"]
        self._token_time = time.monotonic()

    def _call(self, method, params) -> str:
        """GET a zamapi method. POST without a body is rejected with a SOAP 500."""
        query = {**params, "secToken": self._token, "userId": self._user_id}
        r = self._session.get(self.API_URL + method, params=query, timeout=self.TIMEOUT)
        if method == "setMultiDeviceAttributes2" and r.status_code == 500:
            # Known false negative: the write is usually applied anyway.
            # The next (uncached) read shows the real state.
            _LOGGER.debug("setMultiDeviceAttributes2 answered 500: %s", r.text[:200])
            return r.text
        r.raise_for_status()
        return r.text

    @staticmethod
    def _attributes(text) -> dict:
        attrs = {}
        for element in ET.fromstring(text).iter():
            if element.tag.rpartition("}")[2] != "attrList":
                continue
            name = element.findtext("name")
            if name:
                attrs[name] = (element.findtext("value") or "").strip()
        return attrs

    @staticmethod
    def _to_portal(attrs) -> dict:
        """Map Arrayent attributes to the salus-it500.com JSON keys the entities read."""
        def temp(name):
            return str(int(attrs[name]) / 100)

        return {
            "CH1currentRoomTemp": temp("A84"),
            "CH1currentSetPoint": temp("A85"),
            "frost": temp("S09"),
            "CH1heatOnOffStatus": attrs.get("A87", "0"),  # boiler relay
            "CH1heatOnOff": attrs.get("A89", "0"),        # 1 = zone switched off
            "HWonOffStatus": attrs.get("C45", "0"),
            "online": attrs.get("online", ""),
        }

    def _to_attributes(self, data) -> dict:
        """Map a portal-style set.php payload to Arrayent attribute writes.

        Mode flags: A89 off, A92 manual, A88 temp-hold (until next schedule step).
        """
        if "current_tempZ1" in data:
            setpoint = int(round(float(data["current_tempZ1"]) * 100))
            if self._attrs.get("A92") == "1":
                # Manual mode: change the manual setpoint, as the phone app does.
                # Setting A88 here would leave manual and temp-hold both on.
                return {"A85": setpoint, "A93": setpoint}
            # Schedule mode: hold until the next scheduled change.
            return {"A88": 1, "A85": setpoint}
        if data.get("auto") == "1":
            # Off: off flag set, manual and temp-hold cleared.
            return {"A89": 1, "A92": 0, "A88": 0}
        if data.get("auto") == "0":
            # Heat: manual mode at the manual setpoint, which is what the
            # portal's "auto=0" left the thermostat in.
            return {"A89": 0, "A92": 1, "A88": 0}
        if "hwmode_once" in data:
            return {"C42": 1}
        if "hwmode_off" in data:
            return {"C42": 3}
        raise ValueError(f"Unsupported Salus command: {data}")

    def _get_data(self) -> object:
        """Return device values, served from cache when still warm."""
        with self._lock:
            if self._data is not None and (time.monotonic() - self._data_time) < DATA_TTL:
                return self._data

            for attempt in range(3):
                try:
                    if not self._token_valid():
                        self._get_token()

                    text = self._call(
                        "getDeviceAttributesWithValues",
                        {"devId": self._deviceId, "deviceTypeId": 1},
                    )
                    attrs = self._attributes(text)
                    data = self._to_portal(attrs)

                    self._attrs = attrs

                    self._data = data
                    self._data_time = time.monotonic()
                    return data
                except Exception as e:
                    self._token = None  # force re-auth on the next attempt
                    _LOGGER.debug("Data fetch failed (attempt %s/3): %s", attempt + 1, e)

            raise Exception(
                "Error getting data from the Salus cloud. Please check the connection to sal-emea-p01-api.arrayent.com manually."
            )

    def _set_data(self, data) -> bool:
        """Push a config change, then invalidate the cache so the next read is fresh."""
        pairs = list(self._to_attributes(data).items())

        with self._lock:
            for attempt in range(3):
                try:
                    if not self._token_valid():
                        self._get_token()

                    # setMultiDeviceAttributes2 takes at most three pairs per call.
                    params = {"devId": self._deviceId}
                    for index, (name, value) in enumerate(pairs, start=1):
                        params[f"name{index}"] = name
                        params[f"value{index}"] = str(value)
                    self._call("setMultiDeviceAttributes2", params)

                    self._data = None  # device state changed; drop the cached read
                    return True
                except Exception as e:
                    self._token = None
                    _LOGGER.debug("Config push failed (attempt %s/3): %s", attempt + 1, e)

            raise Exception("Error while pushing config.")
