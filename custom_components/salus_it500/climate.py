"""
Adds support for the Salus Thermostat units.
"""
import logging
from datetime import timedelta

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

from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.climate import ClimateEntity
from . import Salus

_LOGGER = logging.getLogger(__name__)

# Values from web interface
MIN_TEMP = 5
MAX_TEMP = 34.5

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE
SCAN_INTERVAL = timedelta(minutes=10)

async def async_setup_platform(hass, hass_config, async_add_entities, discovery_info=None):    
    name = "Salus thermostat"

    if discovery_info != None: 
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
        return SUPPORT_FLAGS

    @property
    def name(self):
        return self._name

    @property
    def should_poll(self):
        return True

    @property
    def min_temp(self):
        return MIN_TEMP

    @property
    def max_temp(self):
        return MAX_TEMP

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        return self._current_temperature

    @property
    def target_temperature(self):
        return self._target_temperature

    @property
    def hvac_mode(self):
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
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def hvac_action(self):
        if self._status == "ON":
            return HVACAction.HEATING
        
        return HVACAction.IDLE

    def set_temperature(self, **kwargs):
        temperature = kwargs.get(ATTR_TEMPERATURE)
        
        if temperature is None:
            return

        try:
            if self._set_data({"tempUnit": "0", "current_tempZ1_set": "1", "current_tempZ1": temperature}):
                self._target_temperature = temperature
        except Exception as e:
            _LOGGER.error("Error Setting the temperature.", e)
        

    def set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            try:
                if self._set_data({"auto": "1", "auto_setZ1": "1"}):
                    self._current_operation_mode = STATE_OFF
            except Exception as e:
                _LOGGER.error("Error Setting HVAC mode OFF.", e)
        elif hvac_mode == HVACMode.HEAT:
            try:
                if self._set_data({"auto": "0", "auto_setZ1": "1"}):
                    self._current_operation_mode = STATE_ON
            except Exception as e:
                _LOGGER.error("Error Setting HVAC mode HEAT.", e)

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
        except Exception as e:
            _LOGGER.error(e)

    async def async_update(self) -> None:
        await self.get_data()

