"""Unit tests for the shared Salus HTTP client (login + data caching + retries)."""
import threading
import time

import pytest

from fakes import FakeSession, count, calls_to

LOGIN = "login.php"
CONTROL = "control.php"
VALUES = "ajax_device_values.php"
SET = "set.php"


# --- token scraping / login -------------------------------------------------

def test_first_read_logs_in_and_scrapes_token(salus):
    client, fake = salus

    data = client._get_data()

    assert data["HWonOffStatus"] == "1"
    assert client._token == "TOK123"
    # exactly one login round-trip: POST login + GET control page
    assert count(fake, LOGIN) == 1
    assert count(fake, CONTROL) == 1
    # the scraped token is forwarded to the values request
    (_, _, params) = calls_to(fake, VALUES)[0]
    assert params["token"] == "TOK123"
    assert params["devId"] == "DEV1"


# --- data cache -------------------------------------------------------------

def test_second_read_within_ttl_is_served_from_cache(salus):
    client, fake = salus

    first = client._get_data()
    second = client._get_data()

    assert second is first  # same cached object, no re-parse
    # no extra network calls of any kind on the cached read
    assert count(fake, VALUES) == 1
    assert count(fake, LOGIN) == 1


def test_expired_data_cache_refetches_but_reuses_token(salus, mod):
    client, fake = salus

    client._get_data()
    client._data_time -= mod.DATA_TTL + 1  # simulate the data cache going stale

    client._get_data()

    assert count(fake, VALUES) == 2  # fresh fetch
    assert count(fake, LOGIN) == 1   # token still valid -> no re-login


# --- token cache ------------------------------------------------------------

def test_expired_token_triggers_relogin(salus, mod):
    client, fake = salus

    client._get_data()
    client._token_time -= mod.TOKEN_TTL + 1  # token past its TTL
    client._data_time -= mod.DATA_TTL + 1    # force an actual fetch

    client._get_data()

    assert count(fake, LOGIN) == 2  # re-authenticated


# --- writes invalidate the cache -------------------------------------------

def test_set_data_sends_token_and_invalidates_cache(salus):
    client, fake = salus

    client._get_data()
    assert client._set_data({"hwmode_off": "1"}) is True

    # cache dropped so the device's new state is read back fresh
    assert client._data is None
    client._get_data()
    assert count(fake, VALUES) == 2

    (_, _, payload) = calls_to(fake, SET)[0]
    assert payload["token"] == "TOK123"
    assert payload["devId"] == "DEV1"
    assert payload["hwmode_off"] == "1"
    assert count(fake, LOGIN) == 1  # reused the existing valid token


# --- retry logic ------------------------------------------------------------

def test_bad_response_resets_token_and_retries(salus):
    client, fake = salus
    fake.values_queue = ["<html>session expired</html>", '{"HWonOffStatus": "0"}']

    data = client._get_data()

    assert data["HWonOffStatus"] == "0"
    assert count(fake, VALUES) == 2
    assert count(fake, LOGIN) == 2  # token was reset, so it re-logged in


def test_persistent_bad_response_raises_after_10_attempts(salus):
    client, fake = salus
    fake.values_queue = ["not json"] * 20

    with pytest.raises(Exception):
        client._get_data()

    assert count(fake, VALUES) == 10  # bounded retry budget


def test_unparseable_token_page_raises(salus):
    client, fake = salus
    fake.token_html = "<html>no token field here</html>"

    with pytest.raises(Exception):
        client._get_data()


# --- concurrency (the thundering-herd fix) ----------------------------------

def test_concurrent_reads_share_a_single_login(mod):
    fake = FakeSession()

    # Make the control-page fetch slow so threads genuinely overlap and would,
    # without the lock, each kick off their own login.
    real_get = fake.get

    def slow_get(url, params=None):
        if CONTROL in url:
            time.sleep(0.05)
        return real_get(url, params=params)

    fake.get = slow_get

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
