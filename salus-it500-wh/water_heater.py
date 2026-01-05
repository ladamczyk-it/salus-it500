"""
Adds support for the Salus water heater units.
"""
import datetime
import time
import logging
import re
import requests
import json 

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ID,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)

from homeassistant.components.water_heater import (
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    PLATFORM_SCHEMA,
)


from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.util.unit_conversion import TemperatureConverter

__version__ = "0.0.1"


_LOGGER = logging.getLogger(__name__)

URL_LOGIN = "https://salus-it500.com/public/login.php"
URL_GET_TOKEN = "https://salus-it500.com/public/control.php"
URL_GET_DATA = "https://salus-it500.com/public/ajax_device_values.php"
URL_SET_DATA = "https://salus-it500.com/includes/set.php"

DEFAULT_NAME = "Salus water heater"


CONF_NAME = "name"

SUPPORT_FLAGS = WaterHeaterEntityFeature.OPERATION_MODE

DOMAIN = "salusfy-wf"
PLATFORMS = ["water_heater"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_ID): cv.string,
    }
)


# def setup_platform(hass, config, add_entities, discovery_info=None):
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    """Set up the E-Thermostaat platform."""
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    id = config.get(CONF_ID)

    async_add_entities(
    [SalusWaterHeater(name, username, password, id)]
    )


class SalusWaterHeater(WaterHeaterEntity):
    """Representation of a Salus water heater device."""

    def __init__(self, name, username, password, id):
        """Initialize the water heater."""
        self._name = name
        self._username = username
        self._password = password
        self._id = id
        self._current_operation = STATE_ON
        self._operation_list = [
            STATE_ON,
            STATE_OFF,
        ]
        self._min_temp = None
        self._max_temp = None
        self._unit_of_measurement = UnitOfTemperature.CELSIUS
        self._token = None
        self._session = requests.Session()
        self.update()
    
    @property
    def supported_features(self) -> WaterHeaterEntityFeature:
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name
        
    @property
    def unique_id(self) -> str:
        """Return the unique ID for this thermostat."""
        return "_".join([self._name, "water_heater"])

    @property
    def should_poll(self):
        """Return if polling is required."""
        return True

    @property
    def current_operation(self):
        """Return current operation ie. on, off."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        headers = {"content-type": "application/x-www-form-urlencoded"}

        if operation_mode == STATE_ON and self._current_operation != STATE_ON:
            payload = {"token": self._token, "devId": self._id, "hwmode_once": "1"}

            try:
                if self._session.post(URL_SET_DATA, data=payload, headers=headers):
                    self._current_operation_mode = STATE_ON
            except:
                _LOGGER.error("Error setting mode ON.")
        elif (
            operation_mode == STATE_OFF and self._current_operation != STATE_OFF
        ):
            payload = {"token": self._token, "devId": self._id, "hwmode_off": "1"}
        
            try:
                if self._session.post(URL_SET_DATA, data=payload, headers=headers):
                    self._current_operation_mode = STATE_OFF
            except:
                _LOGGER.error("Error setting mode OFF.")

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def min_temp(self):
        """Return the minimum targetable temperature."""
        """If the min temperature is not set on the config, returns the HA default for Water Heaters."""
        if not self._min_temp:
            self._min_temp = TemperatureConverter.convert(DEFAULT_MIN_TEMP, UnitOfTemperature.FAHRENHEIT, self._unit_of_measurement) 
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum targetable temperature."""
        """If the max temperature is not set on the config, returns the HA default for Water Heaters."""
        if not self._max_temp:
            self._max_temp = TemperatureConverter.convert(DEFAULT_MAX_TEMP, UnitOfTemperature.FAHRENHEIT, self._unit_of_measurement) 
        return self._max_temp
            
    def get_token(self):
        """Get the Session Token of the Thermostat."""
        payload = {"IDemail": self._username, "password": self._password, "login": "Login", "keep_logged_in": "1"}
        headers = {"content-type": "application/x-www-form-urlencoded"}
        
        try:
            self._session.post(URL_LOGIN, data=payload, headers=headers)
            params = {"devId": self._id}
            getTkoken = self._session.get(URL_GET_TOKEN,params=params)
            result = re.search('<input id="token" type="hidden" value="(.*)" />', getTkoken.text)
            _LOGGER.info("Salusfy get_token OK")
            self._token = result.group(1)
        except:
            _LOGGER.error("Error Geting the Session Token.")

    def _get_data(self):
        if self._token is None:
            self.get_token()
        params = {"devId": self._id, "token": self._token, "&_": str(int(round(time.time() * 1000)))}
        try:
            r = self._session.get(url = URL_GET_DATA, params = params)
            try:
                if r:
                    data = json.loads(r.text)
                    _LOGGER.info("Salusfy get_data output OK")
                    
                    mode = data['HWmode']
                    if mode == "1":
                      self._current_operation_mode = STATE_ON
                    else:
                      self._current_operation_mode = STATE_OFF
                else:
                    _LOGGER.error("Could not get data from Salus.")
            except:
                self.get_token()
                self._get_data()
        except:
            _LOGGER.error("Error Geting the data from Web. Please check the connection to salus-it500.com manually.")

    def update(self):
        """Get the latest data."""
        self._get_data()

