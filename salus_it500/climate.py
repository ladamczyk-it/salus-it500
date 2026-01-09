"""
Adds support for the Salus Thermostat units.
"""
import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )

import logging

from homeassistant.components.climate.const import (
    HVACAction,
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ID,
    STATE_OFF,
    STATE_ON,
    UnitOfTemperature,
)

try:
    from homeassistant.components.climate import (
        ClimateEntity,
    )
except ImportError:
    from homeassistant.components.climate import (
        ClimateDevice as ClimateEntity,
    )


from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.device_registry import DeviceInfo
from salus_it500.common import (
    Salus
)

__version__ = "0.0.1"


_LOGGER = logging.getLogger(__name__)

# Values from web interface
MIN_TEMP = 5
MAX_TEMP = 34.5

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE

async def async_setup_platform(hass, hass_config, async_add_entities, discovery_info):    
    name = "Salus thermostat"

    username = discovery_info[CONF_USERNAME]
    password = discovery_info[CONF_PASSWORD]
    id = discovery_info[CONF_ID]

    async_add_entities(
        [SalusThermostat(hass, name, username, password, id)]
    )

class SalusThermostat(ClimateEntity, Salus):
    """Representation of a Salus Thermostat device."""

    def __init__(self, hass, name, username, password, deviceId):
        """Initialize the thermostat."""
        super(SalusThermostat, self).__init__(username, password, deviceId)

        self._attr_unique_id=f"salus_it500_{deviceId}_thermostat"
        self._attr_available = False
        self._hass = hass
        self._name = name
        self._current_temperature = None
        self._target_temperature = None
        self._frost = None
        self._status = None
        self._current_operation_mode = None
    
    @property
    def unique_id(self) -> str:
        return self._attr_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Salus",
            model="IT500",
            name=self.name,
        )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def should_poll(self):
        """Return if polling is required."""
        return True

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        try:
            curr_hvac_mode = HVACMode.OFF
            
            if self._current_operation_mode == STATE_ON:
                curr_hvac_mode = HVACMode.HEAT
            else:
                curr_hvac_mode = HVACMode.OFF
        except KeyError:
            return HVACMode.OFF
        return curr_hvac_mode
        
    @property
    def hvac_modes(self):
        """HVAC modes."""
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if self._status == "ON":
            return HVACAction.HEATING
        return HVACAction.IDLE

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        
        if temperature is None:
            return

        try:
            if self._set_data({"tempUnit": "0", "current_tempZ1_set": "1", "current_tempZ1": temperature}):
                self._target_temperature = temperature
        except:
            _LOGGER.error("Error Setting the temperature.")
        

    def set_hvac_mode(self, hvac_mode):
        """Set HVAC mode, via URL commands."""
        if hvac_mode == HVACMode.OFF:
            try:
                if self._set_data({"auto": "1", "auto_setZ1": "1"}):
                    self._current_operation_mode = STATE_OFF
            except:
                _LOGGER.error("Error Setting HVAC mode OFF.")
        elif hvac_mode == HVACMode.HEAT:
            try:
                if self._set_data({"auto": "0", "auto_setZ1": "1"}):
                    self._current_operation_mode = STATE_ON
            except:
                _LOGGER.error("Error Setting HVAC mode HEAT.")

    async def get_data(self):
        try: 
            data = await self._hass.async_add_executor_job(self._get_data)

            self._target_temperature = float(data["CH1currentSetPoint"])
            self._current_temperature = float(data["CH1currentRoomTemp"])
            self._frost = float(data["frost"])
                        
            if data['CH1heatOnOffStatus'] == "1":
                self._status = "ON"
            else:
                self._status = "OFF"

            if data['CH1heatOnOff'] == "1":
                self._current_operation_mode = STATE_OFF
            else:
                self._current_operation_mode = STATE_ON

            self._attr_available = True
        except:
            _LOGGER.error("Error geting data from the web. Please check the connection to salus-it500.com manually.")

    async def async_update(self) -> None:
        """Get the latest data."""
        await self.get_data()

