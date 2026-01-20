"""
Adds support for the Salus water heater units.
"""
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
from homeassistant.helpers.device_registry import DeviceInfo
from . import Salus

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = WaterHeaterEntityFeature.OPERATION_MODE

async def async_setup_platform(hass, hass_config, async_add_entities, discovery_info=None):    
    name = "Salus water heater"

    if discovery_info != None: 
        username = discovery_info[CONF_USERNAME]
        password = discovery_info[CONF_PASSWORD]
        id = discovery_info[CONF_ID]

        async_add_entities(
            [SalusWaterHeater(hass, name, username, password, id)]
        )


class SalusWaterHeater(WaterHeaterEntity, Salus):
    """Representation of a Salus water heater device."""

    def __init__(self, hass, name, username, password, deviceId):
        super(SalusWaterHeater, self).__init__(username, password, deviceId)

        self._attr_unique_id=f"salus_it500_{deviceId}_water_heater"
        self._attr_available = False
        self._hass = hass
        self._name = name
        self._current_operation = None
        self._operation_list = [
            STATE_ON,
            STATE_OFF,
        ]
        self._min_temp = None
        self._max_temp = None
        self._unit_of_measurement = UnitOfTemperature.CELSIUS
    
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
    def supported_features(self) -> WaterHeaterEntityFeature:
        return SUPPORT_FLAGS

    @property
    def name(self):
        return self._name

    @property
    def should_poll(self):
        return True

    @property
    def current_operation(self):
        return self._current_operation

    @property
    def operation_list(self):
        return self._operation_list

    def turn_on(self):
        try: 
            if self._set_data({"hwmode_once": "1"}):
                self._current_operation = STATE_ON
        except Exception as e:
            _LOGGER.error("Error setting mode ON.", e)

    def turn_off(self):
        try: 
            if self._set_data({"hwmode_off": "1"}):
                self._current_operation = STATE_ON
        except Exception as e:
            _LOGGER.error("Error setting mode OFF.", e)

    def set_operation_mode(self, operation_mode: str) -> None:
        if operation_mode == STATE_ON:
            self.turn_on()
        elif (
            operation_mode == STATE_OFF
        ):        
            self.turn_off()

    @property
    def current_temperature(self):
        if self._current_operation == STATE_ON:
            return TemperatureConverter.convert(DEFAULT_MAX_TEMP, UnitOfTemperature.FAHRENHEIT, self._unit_of_measurement)
        else
            return TemperatureConverter.convert(DEFAULT_MIN_TEMP, UnitOfTemperature.FAHRENHEIT, self._unit_of_measurement)

    @property
    def temperature_unit(self):
        return self._unit_of_measurement

    @property
    def min_temp(self):
        if not self._min_temp:
            self._min_temp = TemperatureConverter.convert(DEFAULT_MIN_TEMP, UnitOfTemperature.FAHRENHEIT, self._unit_of_measurement) 

        return self._min_temp

    @property
    def max_temp(self):
        if not self._max_temp:
            self._max_temp = TemperatureConverter.convert(DEFAULT_MAX_TEMP, UnitOfTemperature.FAHRENHEIT, self._unit_of_measurement) 
            
        return self._max_temp
            
    async def get_data(self):
        try: 
            data = await self._hass.async_add_executor_job(self._get_data)

            if data['HWonOffStatus'] == "1":
                self._current_operation = STATE_ON
            else:
                self._current_operation = STATE_OFF

            self._attr_available = True
        except Exception as e:
            _LOGGER.error(e)   

    async def async_update(self) -> None:
        await self.get_data()

