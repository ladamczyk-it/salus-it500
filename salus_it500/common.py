"""
Adds support for the Salus Thermostat units.
"""
import datetime
import time
import logging
import re
import requests
import json 

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ID,
)

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

__version__ = "0.0.1"

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_ID): cv.string,
    }
)

DOMAIN = "salus_it500"
PLATFORMS = ["climate", "water_heater"]

class Salus():
    """Salus abstraction."""

    def __init__(self, username, password, deviceId):
        self._username = username
        self._password = password
        self._deviceId = deviceId
        self._token = None
        self._retryCount = 0
        
        self._session = requests.Session()
         
    def _get_token(self) -> None:
        """Get the Session Token."""
        headers = {"content-type": "application/x-www-form-urlencoded"}
        payload = {"IDemail": self._username, "password": self._password, "login": "Login", "keep_logged_in": "1"}
        
        try:
            self._session.post("https://salus-it500.com/public/login.php", data=payload, headers=headers)
            
            params={"devId": self._deviceId}
            getToken = self._session.get("https://salus-it500.com/public/control.php", params=params)
            
            result = re.search('<input id="token" type="hidden" value="(.*)" />', getToken.text)
            
            self._token = result.group(1)
            self._retryCount = 0
        except:
            self._retryCount = self._retryCount + 1

            if self._retryCount < 11:
                self._get_token()
            else:
                raise Exception("Error geting session token.")

    def _get_data(self) -> object:
        if self._token is None:
            self._get_token()

        params = {"devId": self._deviceId, "token": self._token, "&_": str(int(round(time.time() * 1000)))}
        
        try:
            r = self._session.get("https://salus-it500.com/public/ajax_device_values.php", params = params)
            
            try:
                if r:
                    self._retryCount = 0
                    return json.loads(r.text)
                else:
                    raise Exception("Could not get data from Salus.")

            except:
                self._token = None
                self._retryCount = self._retryCount + 1

                if self._retryCount < 11:
                    return self._get_data()
                else:
                    raise Exception("Error geting data from the web. Please check the connection to salus-it500.com manually.")
        except:
            self._token = None
            self._retryCount = self._retryCount + 1

            if self._retryCount < 11:
                return self._get_data()
            else:
                raise Exception("Error geting data from the web. Please check the connection to salus-it500.com manually.")

    def _set_data(self, data) -> bool:
        if self._token is None:
            self._get_token()

        headers = {"content-type": "application/x-www-form-urlencoded"}
        payload = {"token": self._token, "devId": self._id, **data}

        try:
            self._session.post("https://salus-it500.com/includes/set.php", data=payload, headers=headers)
            self._retryCount = 0
        except:
            self._token = None
            self._retryCount = self._retryCount + 1

            if self._retryCount < 11:
                return self._set_data(data)
            else:
                raise Exception("Error while pushing config.")
