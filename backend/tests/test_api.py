"""API 层测试：校验、健康检查、三类裁决与精确有理输出。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_examples_well_formed():
    r = client.get("/api/examples")
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert {"unique-block", "multi-coincidence", "infeasible", "long-heterodyne"} <= set(ids)


def test_unique_payload():
    r = client.post(
        "/api/solve",
        json={
            "distance": {"min": "0", "max": "1.2"},
            "channels": [
                {"wavelength": "1", "phase": "0.25", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0.35", "epsilon": "0.1"},
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "unique"
    assert body["total_solutions"] == 1
    w = body["witnesses"][0]
    assert w["orders"] == [0, 0]
    assert w["distance_band"]["lower"]["fraction"] == "1/4"
    assert w["distance_band"]["upper"]["fraction"] == "7/20"
    assert w["verified"] is True
    for row in w["per_channel"]:
        assert row["within_tolerance"] is True


def test_multiple_returns_two_witnesses_sorted():
    r = client.post(
        "/api/solve",
        json={
            "distance": {"min": "0", "max": "3"},
            "channels": [
                {"wavelength": "1", "phase": "0", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0", "epsilon": "0.1"},
            ],
        },
    )
    body = r.json()
    assert body["status"] == "multiple"
    assert body["total_solutions"] == 4
    assert len(body["witnesses"]) == 2
    assert [x["orders"] for x in body["witnesses"]] == [[0, 0], [1, 1]]


def test_infeasible_verdict():
    r = client.post(
        "/api/solve",
        json={
            "distance": {"min": "0", "max": "3"},
            "channels": [
                {"wavelength": "1", "phase": "0.25", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0.8", "epsilon": "0.1"},
            ],
        },
    )
    body = r.json()
    assert body["status"] == "infeasible"
    assert body["witnesses"] == []
    assert "无解" in body["verdict"]


def test_long_range_verdict_and_stats():
    r = client.post(
        "/api/solve",
        json={
            "distance": {"min": "41230", "max": "41240"},
            "channels": [
                {"wavelength": "0.000633", "phase": "0.150078988941548", "epsilon": "0.000002"},
                {"wavelength": "0.000532", "phase": "0.571428571428571", "epsilon": "0.000002"},
                {"wavelength": "0.000502", "phase": "0.254980079681275", "epsilon": "0.000002"},
            ],
        },
    )
    body = r.json()
    assert body["status"] == "unique"
    stats = body["stats"]
    assert stats["cells_refined"] < stats["naive_shortest_wavelength_integers"] // 100
    band = body["witnesses"][0]["distance_band"]
    assert band["lower"]["decimal"].startswith("41234.7499")
    assert band["upper"]["decimal"].startswith("41234.7500")


@pytest.mark.parametrize(
    "payload",
    [
        # 非有限十进制
        {
            "distance": {"min": "0", "max": "inf"},
            "channels": [
                {"wavelength": "1", "phase": "0.1", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0.2", "epsilon": "0.1"},
            ],
        },
        # 波长必须为正
        {
            "distance": {"min": "0", "max": "1"},
            "channels": [
                {"wavelength": "0", "phase": "0.1", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0.2", "epsilon": "0.1"},
            ],
        },
        # 相位越界
        {
            "distance": {"min": "0", "max": "1"},
            "channels": [
                {"wavelength": "1", "phase": "1", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0.2", "epsilon": "0.1"},
            ],
        },
        # 误差必须小于 1/4 周
        {
            "distance": {"min": "0", "max": "1"},
            "channels": [
                {"wavelength": "1", "phase": "0.1", "epsilon": "0.25"},
                {"wavelength": "1", "phase": "0.2", "epsilon": "0.1"},
            ],
        },
        # 通道数必须 2..32
        {
            "distance": {"min": "0", "max": "1"},
            "channels": [
                {"wavelength": "1", "phase": "0.1", "epsilon": "0.1"},
            ],
        },
        # 区间反向
        {
            "distance": {"min": "2", "max": "1"},
            "channels": [
                {"wavelength": "1", "phase": "0.1", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0.2", "epsilon": "0.1"},
            ],
        },
        # 数字而非字符串（拒绝浮点）
        {
            "distance": {"min": 0, "max": 1},
            "channels": [
                {"wavelength": "1", "phase": "0.1", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0.2", "epsilon": "0.1"},
            ],
        },
    ],
)
def test_validation_rejects(payload):
    r = client.post("/api/solve", json=payload)
    assert r.status_code == 422


def test_channel_count_upper_bound():
    r = client.post(
        "/api/solve",
        json={
            "distance": {"min": "0", "max": "0.0001"},
            "channels": [
                {"wavelength": "1", "phase": "0.1", "epsilon": "0.1"}
                for _ in range(33)
            ],
        },
    )
    assert r.status_code == 422
