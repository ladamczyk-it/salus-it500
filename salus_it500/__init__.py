"""The Salus iT500 component."""
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

DOMAIN = "salus_it500"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_ID): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass, hass_config):
    """Set up Generic Water Heaters."""
    hass_config.get(DOMAIN)
    
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            CLIMATE_DOMAIN,
            DOMAIN,
            [conf],
            hass_config,
        )
    )

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            WATER_HEATER_DOMAIN,
            DOMAIN,
            [conf],
            hass_config,
        )
    )
        
    return True