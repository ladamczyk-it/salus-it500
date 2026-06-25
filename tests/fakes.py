"""A fake ``requests.Session`` for exercising the Salus client offline."""


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def __bool__(self):
        return True


class FakeSession:
    """Records every call and returns programmable bodies per endpoint.

    Set ``token_html`` to control what the control page scrape sees, and
    ``values_queue`` to a list to hand out per-call bodies (used for retry
    tests); otherwise ``values_text`` is returned for every values request.
    """

    DEFAULT_VALUES = '{"CH1currentRoomTemp": "20.5", "CH1currentSetPoint": "21.0", "HWonOffStatus": "1"}'

    def __init__(self):
        self.calls = []  # list of (method, url, payload-or-params)
        self.token_html = '<input id="token" type="hidden" value="TOK123" />'
        self.values_text = self.DEFAULT_VALUES
        self.values_queue = None

    def post(self, url, data=None, headers=None):
        self.calls.append(("POST", url, data))
        return FakeResponse("ok")

    def get(self, url, params=None):
        self.calls.append(("GET", url, params))
        if "control.php" in url:
            return FakeResponse(self.token_html)
        if "ajax_device_values.php" in url:
            if self.values_queue is not None:
                return FakeResponse(self.values_queue.pop(0))
            return FakeResponse(self.values_text)
        return FakeResponse("ok")


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
