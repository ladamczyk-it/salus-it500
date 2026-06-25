"""The Salus iT500 component."""
import time
import logging
import re
import threading
import requests
import json
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

__version__ = "0.0.1"

DOMAIN = "salus_it500"
PLATFORMS = "platforms"
DEFAULT_PLATFORMS = [CLIMATE_DOMAIN, WATER_HEATER_DOMAIN]

# A single fetch of ajax_device_values.php carries both the thermostat (CH1*)
# and water heater (HW*) data, so we cache it briefly and serve both entities
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
    """HTTP client for salus-it500.com, shared by all entities of one device.

    Caches the session token and the most recent device-values fetch so that
    the climate and water_heater entities reuse a single login and, most of
    the time, a single read per cache window instead of calling out separately.
    All public methods run in HA's executor (blocking I/O), so a lock guards
    the shared token/data state against overlapping polls.
    """

    LOGIN_URL = "https://salus-it500.com/public/login.php"
    CONTROL_URL = "https://salus-it500.com/public/control.php"
    VALUES_URL = "https://salus-it500.com/public/ajax_device_values.php"
    SET_URL = "https://salus-it500.com/includes/set.php"

    def __init__(self, username, password, deviceId):
        self._username = username
        self._password = password
        self._deviceId = deviceId
        self._session = requests.Session()
        self._lock = threading.Lock()
        self._token = None
        self._token_time = 0.0
        self._data = None
        self._data_time = 0.0

    def _token_valid(self) -> bool:
        return self._token is not None and (time.monotonic() - self._token_time) < TOKEN_TTL

    def _get_token(self) -> None:
        """(Re)authenticate and scrape a fresh token. Caller must hold the lock."""
        headers = {"content-type": "application/x-www-form-urlencoded"}
        payload = {
            "IDemail": self._username,
            "password": self._password,
            "login": "Login",
            "keep_logged_in": "1",
        }

        for attempt in range(10):
            try:
                self._session.post(self.LOGIN_URL, data=payload, headers=headers)
                page = self._session.get(self.CONTROL_URL, params={"devId": self._deviceId})
                result = re.search('<input id="token" type="hidden" value="(.*)" />', page.text)
                self._token = result.group(1)
                self._token_time = time.monotonic()
                return
            except Exception:
                self._token = None
                _LOGGER.debug("Token fetch failed (attempt %s/10)", attempt + 1)

        raise Exception("Error getting session token.")

    def _get_data(self) -> object:
        """Return device values, served from cache when still warm."""
        with self._lock:
            if self._data is not None and (time.monotonic() - self._data_time) < DATA_TTL:
                return self._data

            for attempt in range(10):
                try:
                    if not self._token_valid():
                        self._get_token()

                    params = {
                        "devId": self._deviceId,
                        "token": self._token,
                        "&_": str(int(round(time.time() * 1000))),
                    }
                    r = self._session.get(self.VALUES_URL, params=params)
                    data = json.loads(r.text)  # raises if the session expired (non-JSON body)

                    self._data = data
                    self._data_time = time.monotonic()
                    return data
                except Exception:
                    self._token = None  # force re-auth on the next attempt
                    _LOGGER.debug("Data fetch failed (attempt %s/10)", attempt + 1)

            raise Exception(
                "Error getting data from the web. Please check the connection to salus-it500.com manually."
            )

    def _set_data(self, data) -> bool:
        """Push a config change, then invalidate the cache so the next read is fresh."""
        with self._lock:
            headers = {"content-type": "application/x-www-form-urlencoded"}

            for attempt in range(10):
                try:
                    if not self._token_valid():
                        self._get_token()

                    payload = {"token": self._token, "devId": self._deviceId, **data}
                    self._session.post(self.SET_URL, data=payload, headers=headers)
                    self._data = None  # device state changed; drop the cached read
                    return True
                except Exception:
                    self._token = None
                    _LOGGER.debug("Config push failed (attempt %s/10)", attempt + 1)

            raise Exception("Error while pushing config.")