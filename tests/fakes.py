"""A fake ``requests.Session`` for exercising the Salus client offline."""


def attributes_xml(attrs):
    """Build a getDeviceAttributesWithValues body from a name -> value dict."""
    items = "".join(
        f"<attrList><name>{name}</name><value>{value}</value></attrList>"
        for name, value in attrs.items()
    )
    return (
        '<ns1:getDeviceAttributesWithValuesResponse xmlns:ns1="http://arrayent.com/zamapi/">'
        f"{items}</ns1:getDeviceAttributesWithValuesResponse>"
    )


SET_OK = (
    '<ns1:setMultiDeviceAttributes2Response xmlns:ns1="http://arrayent.com/zamapi/">'
    "<retCode>0</retCode></ns1:setMultiDeviceAttributes2Response>"
)


class FakeResponse:
    def __init__(self, text="", status_code=200, json_body=None):
        self.text = text
        self.status_code = status_code
        self._json = json_body

    def json(self):
        if self._json is None:
            raise ValueError("no JSON body")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class FakeSession:
    """Records every call and returns programmable bodies per endpoint.

    Set ``attrs`` to control the device attributes, and ``values_queue`` to a
    list to hand out per-call bodies (used for retry tests); otherwise
    ``attrs`` is rendered for every attribute request. ``set_status`` controls
    the HTTP status of setMultiDeviceAttributes2.
    """

    DEFAULT_ATTRS = {
        "A84": "2050", "A85": "2100", "A87": "1", "A88": "0", "A89": "0",
        "A92": "0", "A93": "2100", "S09": "500", "C42": "0", "C45": "1",
        "online": "1",
    }

    def __init__(self):
        self.calls = []  # list of (method, url, payload-or-params)
        self.login_body = {"securityToken": "TOK123", "userId": 42}
        self.attrs = dict(self.DEFAULT_ATTRS)
        self.values_queue = None
        self.set_status = 200

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json))
        return FakeResponse(json_body=self.login_body)

    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, params))
        if "getDeviceAttributesWithValues" in url:
            if self.values_queue is not None:
                return self.values_queue.pop(0)
            return FakeResponse(attributes_xml(self.attrs))
        if "setMultiDeviceAttributes2" in url:
            return FakeResponse(SET_OK, status_code=self.set_status)
        return FakeResponse("", status_code=404)


def count(session, substr, method=None):
    """Number of recorded calls whose URL contains ``substr``."""
    return sum(
        1
        for m, url, _ in session.calls
        if substr in url and (method is None or m == method)
    )


def calls_to(session, substr):
    """All recorded calls whose URL contains ``substr``."""
    return [c for c in session.calls if substr in c[1]]
