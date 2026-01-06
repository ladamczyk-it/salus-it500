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
    Salus,
    DOMAIN, 
    PLATFORMS,
    PLATFORM_SCHEMA
)

__version__ = "0.0.1"


_LOGGER = logging.getLogger(__name__)

# Values from web interface
MIN_TEMP = 5
MAX_TEMP = 34.5

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE

# def setup_platform(hass, config, add_entities, discovery_info=None):
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    
    name = "Salus Thermostat"
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    id = config.get(CONF_ID)

    async_add_entities(
        [SalusThermostat(hass, name, username, password, id)]
    )

class SalusThermostat(ClimateEntity, Salus):
    """Representation of a Salus Thermostat device."""

    def __init__(self, hass, name, username, password, deviceId):
        """Initialize the thermostat."""
        super(SalusThermostat, self).__init__(username, password, deviceId)

        self._attr_unique_id=f"salus_it500_{deviceId}_thermostat"
        self._hass = hass
        self._name = name
        self._current_temperature = None
        self._status = None
        self._current_operation_mode = None
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information for this entity."""
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
    def unique_id(self) -> str:
        """Return the unique ID for this thermostat."""
        return "_".join([self._name, "climate"])

    @property
    def should_poll(self):
        """Return if polling is required."""
        return True

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature


    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        try:
            curr_hvac_mode = HVACMode.OFF
            
            if self._current_operation_mode == STATE_ON:
                curr_hvac_mode = HVACMode.AUTO
            else:
                curr_hvac_mode = HVACMode.OFF
        except KeyError:
            return HVACMode.OFF
        return curr_hvac_mode
        
    @property
    def hvac_modes(self):
        """HVAC modes."""
        return [HVACMode.AUTO, HVACMode.OFF]

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if self._status == "ON":
            return HVACAction.HEATING
        return HVACAction.IDLE

    def set_hvac_mode(self, hvac_mode):
        """Set HVAC mode, via URL commands."""
        if hvac_mode == HVACMode.OFF:
            if self._set_data({"auto": "1", "auto_setZ1": "1"}):
                self._current_operation_mode = STATE_OFF
            else:
                _LOGGER.error("Error Setting HVAC mode OFF.")
        elif hvac_mode == HVACMode.AUTO:
            if self._set_data({"auto": "0", "auto_setZ1": "1"}):
                self._current_operation_mode = STATE_ON
            else:
                _LOGGER.error("Error Setting HVAC mode ON.")

    async def get_data(self):
        try: 
            data = await self._hass.async_add_executor_job(self._get_data)

            self._current_temperature = float(data["CH1currentRoomTemp"])
                        
            if data['CH1heatOnOffStatus'] == "1":
                self._status = "ON"
            else:
                self._status = "OFF"

            if data['CH1heatOnOff'] == "1":
                self._current_operation_mode = STATE_OFF
            else:
                self._current_operation_mode = STATE_ON
        except:
            _LOGGER.error("Error geting data from the web. Please check the connection to salus-it500.com manually.")

    async def async_update(self) -> None:
        """Get the latest data."""
        await self.get_data()

