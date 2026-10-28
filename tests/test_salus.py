"""Unit tests for the shared Salus HTTP client (login + data caching + retries)."""
import hashlib
import threading
import time

import pytest

from fakes import FakeResponse, FakeSession, attributes_xml, count, calls_to

LOGIN = "SalusService/sessions"
VALUES = "getDeviceAttributesWithValues"
SET = "setMultiDeviceAttributes2"


def written(fake):
    """Attribute name -> value pairs of every write, in order."""
    pairs = []
    for _, _, params in calls_to(fake, SET):
        i = 1
        while f"name{i}" in params:
            pairs.append((params[f"name{i}"], params[f"value{i}"]))
            i += 1
    return pairs


# --- login -------------------------------------------------------------------

def test_first_read_logs_in_and_forwards_token(salus):
    client, fake = salus

    data = client._get_data()

    assert data["HWonOffStatus"] == "1"
    assert client._token == "TOK123"
    assert count(fake, LOGIN) == 1
    # the password is sent as an MD5 hex digest, never in clear text
    (_, _, body) = calls_to(fake, LOGIN)[0]
    assert body == {"username": "user@example.com", "password": hashlib.md5(b"secret").hexdigest()}
    # the token is forwarded to the attribute request, which must be a GET
    (method, _, params) = calls_to(fake, VALUES)[0]
    assert method == "GET"
    assert params["secToken"] == "TOK123"
    assert params["userId"] == 42
    assert params["devId"] == "DEV1"


# --- attribute mapping -------------------------------------------------------

def test_attributes_are_mapped_to_portal_keys(salus):
    client, fake = salus

    data = client._get_data()

    assert data["CH1currentRoomTemp"] == "20.5"
    assert data["CH1currentSetPoint"] == "21.0"
    assert data["frost"] == "5.0"
    assert data["CH1heatOnOffStatus"] == "1"
    assert data["CH1heatOnOff"] == "0"
    assert data["HWonOffStatus"] == "1"


def test_off_with_relay_on_is_reported_pending(salus):
    client, fake = salus
    fake.attrs.update({"A89": "1", "A87": "1"})  # cloud says off, device still heating

    assert client._get_data()["CH1offPending"] == "1"


@pytest.mark.parametrize("a89, a87", [("1", "0"), ("0", "1"), ("0", "0")])
def test_consistent_states_are_not_pending(salus, a89, a87):
    client, fake = salus
    fake.attrs.update({"A89": a89, "A87": a87})

    assert client._get_data()["CH1offPending"] == "0"


def test_update_times_are_mapped_to_utc_iso(salus):
    client, fake = salus
    fake.times = {"A84": "1793198373462", "online": "1793197494220", "A85": "0"}

    data = client._get_data()

    assert data["lastReport"] == "2026-10-28T14:39:33+00:00"
    assert data["onlineSince"] == "2026-10-28T14:24:54+00:00"


def test_missing_update_times_are_none(salus):
    client, fake = salus
    fake.times = {"online": "0"}  # never-set attributes report updTime 0

    data = client._get_data()

    assert data["lastReport"] is None
    assert data["onlineSince"] is None


# --- data cache --------------------------------------------------------------

def test_second_read_within_ttl_is_served_from_cache(salus):
    client, fake = salus

    first = client._get_data()
    second = client._get_data()

    assert second is first  # same cached object, no re-parse
    assert count(fake, VALUES) == 1
    assert count(fake, LOGIN) == 1


def test_expired_data_cache_refetches_but_reuses_token(salus, mod):
    client, fake = salus

    client._get_data()
    client._data_time -= mod.DATA_TTL + 1  # simulate the data cache going stale

    client._get_data()

    assert count(fake, VALUES) == 2  # fresh fetch
    assert count(fake, LOGIN) == 1   # token still valid -> no re-login


# --- token cache -------------------------------------------------------------

def test_expired_token_triggers_relogin(salus, mod):
    client, fake = salus

    client._get_data()
    client._token_time -= mod.TOKEN_TTL + 1  # token past its TTL
    client._data_time -= mod.DATA_TTL + 1    # force an actual fetch

    client._get_data()

    assert count(fake, LOGIN) == 2  # re-authenticated


# --- writes ------------------------------------------------------------------

def test_set_data_sends_token_and_invalidates_cache(salus):
    client, fake = salus

    client._get_data()
    assert client._set_data({"hwmode_off": "1"}) is True

    # cache dropped so the device's new state is read back fresh
    assert client._data is None
    client._get_data()
    assert count(fake, VALUES) == 2

    (method, _, params) = calls_to(fake, SET)[0]
    assert method == "GET"
    assert params["secToken"] == "TOK123"
    assert params["devId"] == "DEV1"
    assert written(fake) == [("C42", "3")]
    assert count(fake, LOGIN) == 1  # reused the existing valid token


def test_setpoint_in_schedule_mode_uses_temp_hold(salus):
    client, fake = salus
    client._get_data()  # A92=0: following the schedule

    client._set_data({"tempUnit": "0", "current_tempZ1_set": "1", "current_tempZ1": 22.5})

    assert written(fake) == [("A88", "1"), ("A85", "2250")]


def test_setpoint_in_manual_mode_keeps_manual(salus):
    client, fake = salus
    fake.attrs["A92"] = "1"
    client._get_data()

    client._set_data({"tempUnit": "0", "current_tempZ1_set": "1", "current_tempZ1": 26.0})

    # manual + temp-hold together is an undefined mode; write like the app does
    assert written(fake) == [("A85", "2600"), ("A93", "2600")]


def test_hvac_off_and_heat(salus):
    client, fake = salus

    client._set_data({"auto": "1", "auto_setZ1": "1"})
    client._set_data({"auto": "0", "auto_setZ1": "1"})

    assert written(fake) == [
        ("A89", "1"), ("A92", "0"), ("A88", "0"),  # off
        ("A89", "0"), ("A92", "1"), ("A88", "0"),  # heat -> manual mode
    ]


def test_hot_water_once(salus):
    client, fake = salus

    client._set_data({"hwmode_once": "1"})

    assert written(fake) == [("C42", "1")]


def test_unknown_command_is_rejected_without_network(salus):
    client, fake = salus

    with pytest.raises(ValueError):
        client._set_data({"something": "1"})

    assert fake.calls == []


def test_set_500_is_tolerated(salus):
    client, fake = salus
    fake.set_status = 500  # known false negative from Arrayent

    assert client._set_data({"hwmode_off": "1"}) is True
    assert count(fake, SET) == 1  # not retried


# --- retry logic -------------------------------------------------------------

def test_bad_response_resets_token_and_retries(salus):
    client, fake = salus
    fake.values_queue = [
        FakeResponse("", status_code=500),
        FakeResponse(attributes_xml({**FakeSession.DEFAULT_ATTRS, "C45": "0"})),
    ]

    data = client._get_data()

    assert data["HWonOffStatus"] == "0"
    assert count(fake, VALUES) == 2
    assert count(fake, LOGIN) == 2  # token was reset, so it re-logged in


def test_persistent_bad_response_raises_after_3_attempts(salus):
    client, fake = salus
    fake.values_queue = [FakeResponse("not xml") for _ in range(10)]

    with pytest.raises(Exception):
        client._get_data()

    assert count(fake, VALUES) == 3  # bounded retry budget


def test_rejected_login_raises(salus):
    client, fake = salus
    fake.login_body = {"error": "invalid"}

    with pytest.raises(Exception):
        client._get_data()

    assert count(fake, VALUES) == 0


# --- concurrency (the thundering-herd fix) -----------------------------------

def test_concurrent_reads_share_a_single_login(mod):
    fake = FakeSession()

    # Make the login slow so threads genuinely overlap and would, without the
    # lock, each kick off their own login.
    real_post = fake.post

    def slow_post(url, json=None, headers=None, timeout=None):
        time.sleep(0.05)
        return real_post(url, json=json, headers=headers, timeout=timeout)

    fake.post = slow_post

    client = mod.Salus("user", "pass", "DEV1")
    client._session = fake

    results = []

    def worker():
        results.append(client._get_data())

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert count(fake, LOGIN) == 1   # lock serialized the herd into one login
    assert count(fake, VALUES) == 1  # and one shared fetch
    assert all(r is results[0] for r in results)
