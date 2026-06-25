"""Test bootstrap for the salus_it500 integration.

Home Assistant is not installed in the dev venv (it is a heavy dependency and
the integration only needs a handful of symbols at import time), so we stub the
modules that ``custom_components/salus_it500/__init__.py`` imports. This lets us
import and unit-test the ``Salus`` HTTP client — session/token caching, the
data cache and the retry logic — without pulling in all of HA.
"""
import sys
import types
from pathlib import Path

import pytest


def _stub(name):
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


# --- minimal homeassistant stubs (must exist before the integration imports) ---
ha = _stub("homeassistant")
ha_components = _stub("homeassistant.components")
climate = _stub("homeassistant.components.climate")
climate.DOMAIN = "climate"
water_heater = _stub("homeassistant.components.water_heater")
water_heater.DOMAIN = "water_heater"
helpers = _stub("homeassistant.helpers")
discovery = _stub("homeassistant.helpers.discovery")
config_validation = _stub("homeassistant.helpers.config_validation")
config_validation.string = str
config_validation.ensure_list = lambda v: v if isinstance(v, list) else [v]
const = _stub("homeassistant.const")
const.CONF_PASSWORD = "password"
const.CONF_USERNAME = "username"
const.CONF_ID = "id"

ha.components = ha_components
ha.helpers = helpers
ha.const = const
ha_components.climate = climate
ha_components.water_heater = water_heater
helpers.discovery = discovery
helpers.config_validation = config_validation

# Make `import salus_it500` resolve to the custom component package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "custom_components"))


@pytest.fixture(scope="session")
def mod():
    """The imported integration module (stubs are already in place)."""
    import salus_it500

    return salus_it500


@pytest.fixture
def salus(mod):
    """A ``Salus`` client wired to a fake HTTP session."""
    from fakes import FakeSession

    client = mod.Salus("user@example.com", "secret", "DEV1")
    fake = FakeSession()
    client._session = fake
    return client, fake
