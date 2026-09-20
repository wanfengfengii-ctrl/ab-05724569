"""API-level tests using the FastAPI test client."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_solve_unique_exact_response():
    payload = {
        "range": {"lo": "0", "hi": "4"},
        "channels": [
            {"wavelength": "2", "phase": "0.5", "epsilon": "0.05"},
            {"wavelength": "3", "phase": "0.3", "epsilon": "0.05"},
        ],
    }
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unique"
    assert body["total_classes"] == 1
    (w,) = body["witnesses"]
    assert w["integers"] == [0, 0]
    assert w["interval"]["lo"] == {"exact": "9/10", "approx": 0.9}
    assert w["interval"]["hi"] == {"exact": "21/20", "approx": 1.05}
    # Per-channel residuals and bands are reported.
    assert len(w["channels"]) == 2
    assert w["channels"][0]["integer"] == 0
    assert w["channels"][0]["residual"]["lo"]["exact"] == "-1/20"
    assert w["channels"][0]["residual"]["hi"]["exact"] == "1/40"
    assert w["channels"][1]["residual"]["lo"]["exact"] == "0"
    assert w["channels"][1]["residual"]["hi"]["exact"] == "1/20"


def test_solve_multiple_response():
    payload = {
        "range": {"lo": 0, "hi": 10},
        "channels": [
            {"wavelength": 2, "phase": "0.5", "epsilon": "0.1"},
            {"wavelength": 3, "phase": "0.25", "epsilon": "0.1"},
        ],
    }
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "multiple"
    assert body["total_classes"] == 2
    assert [w["integers"] for w in body["witnesses"]] == [[0, 0], [3, 2]]
    assert body["witnesses"][0]["interval"]["lo"]["exact"] == "4/5"
    assert body["witnesses"][1]["interval"]["hi"]["exact"] == "141/20"


def test_solve_none_response():
    payload = {
        "range": {"lo": "0", "hi": "4"},
        "channels": [
            {"wavelength": "2", "phase": "0.5", "epsilon": "0.05"},
            {"wavelength": "3", "phase": "0.5", "epsilon": "0.05"},
        ],
    }
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "none"
    assert body["total_classes"] == 0
    assert body["witnesses"] == []


def test_json_numbers_are_treated_as_exact_decimals():
    # 0.1 as a JSON number must mean exactly 1/10, not the binary float.
    payload = {
        "range": {"lo": 0, "hi": 1},
        "channels": [
            {"wavelength": 1, "phase": 0.1, "epsilon": 0.1},
            {"wavelength": 2, "phase": 0.2, "epsilon": 0.1},
        ],
    }
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "unique"
    w = body["witnesses"][0]
    # ch1 tooth: [0, 0.2]; ch2 tooth: [0.2, 0.6] -> touch at 1/5 exactly.
    assert w["interval"]["lo"]["exact"] == "1/5"
    assert w["interval"]["hi"]["exact"] == "1/5"


def test_scientific_notation_input():
    payload = {
        "range": {"lo": "0", "hi": "1e1"},
        "channels": [
            {"wavelength": "2", "phase": "5e-1", "epsilon": "0.1"},
            {"wavelength": "3", "phase": "0.25", "epsilon": "0.1"},
        ],
    }
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 200
    assert resp.json()["total_classes"] == 2


def test_long_range_not_enumerated():
    payload = {
        "range": {"lo": "0", "hi": "1000000000"},
        "channels": [
            {"wavelength": "1000", "phase": "0", "epsilon": "0.01"},
            {"wavelength": "1001", "phase": "0", "epsilon": "0.01"},
        ],
    }
    resp = client.post("/api/solve", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "periodic"
    assert body["total_classes"] == 40961
    assert body["candidates_examined"] < 10_000
    assert body["elapsed_ms"] < 10_000


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def _solve(payload):
    return client.post("/api/solve", json=payload)


def _base():
    return {
        "range": {"lo": "0", "hi": "10"},
        "channels": [
            {"wavelength": "2", "phase": "0.5", "epsilon": "0.1"},
            {"wavelength": "3", "phase": "0.25", "epsilon": "0.1"},
        ],
    }


def test_validation_rejects_bad_inputs():
    cases = []
    p = _base(); p["range"] = {"lo": "10", "hi": "0"}; cases.append(p)            # lo > hi
    p = _base(); p["channels"][0]["wavelength"] = "0"; cases.append(p)            # λ = 0
    p = _base(); p["channels"][0]["wavelength"] = "-2"; cases.append(p)           # λ < 0
    p = _base(); p["channels"][0]["phase"] = "1"; cases.append(p)                 # p = 1
    p = _base(); p["channels"][0]["phase"] = "-0.1"; cases.append(p)              # p < 0
    p = _base(); p["channels"][0]["epsilon"] = "0.25"; cases.append(p)            # ε = 1/4
    p = _base(); p["channels"][0]["epsilon"] = "-0.1"; cases.append(p)            # ε < 0
    p = _base(); p["channels"][0]["wavelength"] = "1/3"; cases.append(p)          # not a decimal
    p = _base(); p["channels"][0]["phase"] = "abc"; cases.append(p)               # not a number
    p = _base(); p["channels"][0]["phase"] = "nan"; cases.append(p)               # not finite
    p = _base(); p["channels"][0]["phase"] = "inf"; cases.append(p)               # not finite
    p = _base(); p["channels"] = p["channels"][:1]; cases.append(p)               # < 2 channels
    p = _base(); p["channels"] = p["channels"] * 17; cases.append(p)              # > 32 channels
    p = _base(); p["range"]["lo"] = "0.1.2"; cases.append(p)                      # malformed
    for payload in cases:
        resp = _solve(payload)
        assert resp.status_code == 422, f"expected 422 for {payload}, got {resp.status_code}"


def test_validation_accepts_boundary_values():
    p = _base()
    p["channels"][0]["phase"] = "0"
    p["channels"][0]["epsilon"] = "0"
    p["channels"][1]["phase"] = "0.999999"
    p["channels"][1]["epsilon"] = "0.249999"
    p["channels"] = p["channels"] * 16  # exactly 32 channels
    resp = _solve(p)
    assert resp.status_code == 200
