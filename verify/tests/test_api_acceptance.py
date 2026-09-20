"""End-to-end API acceptance tests (run inside the compose network)."""

from __future__ import annotations

import os
import time

import requests

API_BASE = os.environ.get("API_BASE", "http://api:8000")
WEB_BASE = os.environ.get("WEB_BASE", "http://web")


def test_api_health():
    resp = requests.get(f"{API_BASE}/api/health", timeout=5)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_web_health():
    resp = requests.get(f"{WEB_BASE}/healthz", timeout=5)
    assert resp.status_code == 200


def test_web_serves_frontend():
    resp = requests.get(f"{WEB_BASE}/", timeout=5)
    assert resp.status_code == 200
    resp.encoding = "utf-8"
    assert "整周数解算工作台" in resp.text


def _solve(payload: dict) -> dict:
    resp = requests.post(f"{API_BASE}/api/solve", json=payload, timeout=30)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_unique_class_exact_intersection():
    body = _solve(
        {
            "range": {"lo": "0", "hi": "4"},
            "channels": [
                {"wavelength": "2", "phase": "0.5", "epsilon": "0.05"},
                {"wavelength": "3", "phase": "0.3", "epsilon": "0.05"},
            ],
        }
    )
    assert body["status"] == "unique"
    assert body["total_classes"] == 1
    (w,) = body["witnesses"]
    assert w["integers"] == [0, 0]
    assert w["interval"]["lo"]["exact"] == "9/10"
    assert w["interval"]["hi"]["exact"] == "21/20"
    # Residual intervals are exact as well.
    assert w["channels"][0]["residual"]["lo"]["exact"] == "-1/20"
    assert w["channels"][1]["residual"]["hi"]["exact"] == "1/20"


def test_multiple_classes_first_two_witnesses_ordered():
    body = _solve(
        {
            "range": {"lo": "0", "hi": "10"},
            "channels": [
                {"wavelength": "2", "phase": "0.5", "epsilon": "0.1"},
                {"wavelength": "3", "phase": "0.25", "epsilon": "0.1"},
            ],
        }
    )
    assert body["status"] == "multiple"
    assert body["total_classes"] == 2
    first, second = body["witnesses"]
    assert first["integers"] == [0, 0]
    assert first["interval"]["lo"]["exact"] == "4/5"
    assert first["interval"]["hi"]["exact"] == "21/20"
    assert second["integers"] == [3, 2]
    assert second["interval"]["lo"]["exact"] == "34/5"
    assert second["interval"]["hi"]["exact"] == "141/20"


def test_none_verdict():
    body = _solve(
        {
            "range": {"lo": "0", "hi": "4"},
            "channels": [
                {"wavelength": "2", "phase": "0.5", "epsilon": "0.05"},
                {"wavelength": "3", "phase": "0.5", "epsilon": "0.05"},
            ],
        }
    )
    assert body["status"] == "none"
    assert body["total_classes"] == 0
    assert body["witnesses"] == []


def test_exact_rational_arithmetic_with_decimal_wavelengths():
    body = _solve(
        {
            "range": {"lo": "0", "hi": "1"},
            "channels": [
                {"wavelength": "0.3", "phase": "0", "epsilon": "0.1"},
                {"wavelength": "0.4", "phase": "0", "epsilon": "0.1"},
            ],
        }
    )
    assert body["status"] == "unique"
    w = body["witnesses"][0]
    assert w["interval"]["lo"]["exact"] == "0"
    assert w["interval"]["hi"]["exact"] == "3/100"


def test_long_range_is_not_enumerated():
    """The range spans ~1e6 fringe orders of the shortest wavelength; a naive
    per-order scan would be far slower and is explicitly forbidden."""
    started = time.monotonic()
    body = _solve(
        {
            "range": {"lo": "0", "hi": "1000000000"},
            "channels": [
                {"wavelength": "1000", "phase": "0", "epsilon": "0.01"},
                {"wavelength": "1001", "phase": "0", "epsilon": "0.01"},
            ],
        }
    )
    elapsed = time.monotonic() - started
    assert body["status"] == "multiple"
    assert body["mode"] == "periodic"
    assert body["total_classes"] == 40961
    assert body["candidates_examined"] < 10_000
    assert elapsed < 10, f"long-range solve took too long: {elapsed:.1f}s"
    assert body["witnesses"][0]["integers"] == [0, 0]
    assert body["witnesses"][0]["interval"]["hi"]["exact"] == "10"


def test_input_validation_is_enforced():
    base = {
        "range": {"lo": "0", "hi": "10"},
        "channels": [
            {"wavelength": "2", "phase": "0.5", "epsilon": "0.1"},
            {"wavelength": "3", "phase": "0.25", "epsilon": "0.1"},
        ],
    }
    bad_payloads = []

    p = {**base, "range": {"lo": "10", "hi": "0"}}
    bad_payloads.append(p)

    import copy

    p = copy.deepcopy(base); p["channels"][0]["wavelength"] = "-1"
    bad_payloads.append(p)
    p = copy.deepcopy(base); p["channels"][0]["phase"] = "1"
    bad_payloads.append(p)
    p = copy.deepcopy(base); p["channels"][0]["epsilon"] = "0.25"
    bad_payloads.append(p)
    p = copy.deepcopy(base); p["channels"][0]["wavelength"] = "1/3"
    bad_payloads.append(p)
    p = copy.deepcopy(base); p["channels"][0]["phase"] = "nan"
    bad_payloads.append(p)
    p = copy.deepcopy(base); p["channels"] = base["channels"][:1]
    bad_payloads.append(p)
    p = copy.deepcopy(base); p["channels"] = base["channels"] * 17
    bad_payloads.append(p)

    for payload in bad_payloads:
        resp = requests.post(f"{API_BASE}/api/solve", json=payload, timeout=10)
        assert resp.status_code == 422, f"expected 422, got {resp.status_code}: {payload}"
