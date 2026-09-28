"""Explicit Kismet capture-source lock. No process is launched."""
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import utils.kismet.client as kc


@pytest.fixture(autouse=True)
def _clear_lock():
    kc._locked_source = ""
    yield
    kc._locked_source = ""


def test_empty_start_is_400_and_does_not_launch():
    from dashboard.app import app

    app.config["TESTING"] = True
    with mock.patch("utils.auth.auth_enabled", return_value=False), \
         mock.patch("utils.kismet.client.ensure_kismet") as start, \
         mock.patch("utils.kismet.client.subprocess.Popen") as popen:
        client = app.test_client()
        resp = client.post("/api/kismet_start", json={})
        resp2 = client.post("/api/kismet_start", data="{}", content_type="application/json")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False
    assert resp2.status_code == 400
    start.assert_not_called()
    popen.assert_not_called()


def test_empty_source_does_not_launch_and_has_no_fallback():
    with mock.patch("utils.device_detector.get_device_summary") as detected, \
         mock.patch("utils.kismet.client.subprocess.Popen") as popen:
        assert kc.source_def("") == ""
        assert kc.source_def("   ") == ""
        ok, msg = kc.ensure_kismet("")
    assert ok is False
    assert msg == "Select a capture source"
    detected.assert_not_called()
    popen.assert_not_called()
    assert "wlan1" not in kc.source_def("")


def test_same_running_source_is_idempotent():
    kc._locked_source = "wlan1"
    with mock.patch.object(kc.KismetClient, "is_port_open", return_value=True), \
         mock.patch.object(kc.KismetClient, "ensure_source") as add, \
         mock.patch("utils.kismet.client.subprocess.Popen") as popen:
        ok, msg = kc.ensure_kismet("wlan1")
    assert ok is True
    assert "already running" in msg
    assert kc.get_locked_source() == "wlan1"
    add.assert_not_called()
    popen.assert_not_called()


def test_other_or_unknown_running_source_is_rejected():
    with mock.patch.object(kc.KismetClient, "is_port_open", return_value=True), \
         mock.patch.object(kc.KismetClient, "ensure_source") as add, \
         mock.patch("utils.kismet.client.subprocess.Popen") as popen:
        kc._locked_source = ""
        ok, msg = kc.ensure_kismet("wlan1")
        assert ok is False
        assert "Stop Kismet before changing source" in msg
        kc._locked_source = "wlan1"
        ok2, msg2 = kc.ensure_kismet("wlan1mon")
        assert ok2 is False
        assert "Stop Kismet before changing source" in msg2
    add.assert_not_called()
    popen.assert_not_called()


def test_stop_clears_lock():
    kc._locked_source = "wlan1mon"
    with mock.patch.object(kc.KismetClient, "is_port_open", return_value=False), \
         mock.patch("utils.kismet.client.subprocess.run"):
        ok, msg = kc.stop_kismet()
    assert ok is True
    assert kc.get_locked_source() == ""


def test_launch_requires_explicit_source_definition():
    calls = []
    state = {"up": False}

    def is_open(self, *args, **kwargs):
        return state["up"]

    def popen(cmd, **kwargs):
        calls.append(list(cmd))
        state["up"] = True
        return mock.Mock()

    with mock.patch.object(kc.KismetClient, "is_port_open", is_open), \
         mock.patch("utils.kismet.client.subprocess.Popen", popen), \
         mock.patch("utils.kismet.client.time.sleep"), \
         mock.patch("utils.kismet.client.ensure_data_dirs"), \
         mock.patch("builtins.open", mock.mock_open()):
        ok, msg = kc.ensure_kismet("wlan1mon")
    assert ok is True
    assert calls
    assert kc.get_locked_source() == "wlan1mon"
    for cmd in calls:
        assert "-c" in cmd
        assert "wlan1mon:name=wlan1mon" in cmd
        assert cmd != ["sudo", "-n", "kismet", "--no-ncurses"]
        assert cmd != ["kismet", "--no-ncurses"]
