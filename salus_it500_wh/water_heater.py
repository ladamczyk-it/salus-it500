"""
Adds support for the Salus water heater units.
"""
import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )

import logging

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
)

from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.util.unit_conversion import TemperatureConverter

from salus_it500.common import (
    Salus,
    DOMAIN, 
    PLATFORMS,
    PLATFORM_SCHEMA
)

__version__ = "0.0.1"


_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = WaterHeaterEntityFeature.OPERATION_MODE

# def setup_platform(hass, config, add_entities, discovery_info=None):
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    
    name = "Salus water heater"
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
        super(SalusWaterHeater, self).__init__(username, password, deviceId)

        self._name = name
        self._current_operation = STATE_ON
        self._operation_list = [
            STATE_ON,
            STATE_OFF,
        ]
        self._min_temp = None
        self._max_temp = None
        self._unit_of_measurement = UnitOfTemperature.CELSIUS
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
        if operation_mode == STATE_ON and self._current_operation != STATE_ON:
            if self._set_data({"hwmode_once": "1"}):
                self._current_operation_mode = STATE_ON
            else:
                _LOGGER.error("Error setting mode ON.")
        elif (
            operation_mode == STATE_OFF and self._current_operation != STATE_OFF
        ):        
            if self._set_data({"hwmode_off": "1"}):
                self._current_operation_mode = STATE_OFF
            else:
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
            

    async def get_data(self):
        try: 
            data = self._get_data()

            if data['HWmode'] == "1":
                self._current_operation_mode = STATE_ON
            else:
                self._current_operation_mode = STATE_OFF
        except:
            _LOGGER.error("Error geting data from the web. Please check the connection to salus-it500.com manually.")   

    def update(self):
        """Get the latest data."""
        self.get_data()

