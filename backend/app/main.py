"""FastAPI 入口：精确多波长整周解算工作台。

所有数值均以十进制字符串接收并用 fractions.Fraction 精确解析，
响应同时给出精确有理数字符串与十进制近似，避免任何浮点裁决。
"""
from __future__ import annotations

import os
import re
from fractions import Fraction
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .solver import (
    DEFAULT_MAX_CELLS,
    Channel,
    SolveLimit,
    solve,
    shortest_wavelength_integer_count,
)

DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
MAX_DECIMAL_PLACES = 18
# 输入字符串长度上限，防止超长十进制构造出代价高昂的大整数运算。
MAX_INPUT_LENGTH = 64


def parse_decimal(value: Any, loc: list[str], errors: list[dict]) -> Fraction | None:
    """把有限十进制字符串精确解析为 Fraction；非法时登记错误。"""
    if not isinstance(value, str):
        errors.append(
            {"loc": loc, "msg": "必须是十进制字符串（避免浮点丢精度）"}
        )
        return None
    text = value.strip()
    if len(text) > MAX_INPUT_LENGTH:
        errors.append(
            {"loc": loc, "msg": f"十进制数长度不得超过 {MAX_INPUT_LENGTH} 个字符"}
        )
        return None
    if not DECIMAL_RE.match(text):
        errors.append({"loc": loc, "msg": f"不是有限十进制数：{value!r}"})
        return None
    return Fraction(text)


def q_exact(x: Fraction) -> dict[str, str]:
    """精确有理数 → 传输结构（分数字符串 + 四舍五入十进制近似）。"""
    sign = "-" if x.numerator < 0 else ""
    num = abs(x.numerator)
    q = 10 ** MAX_DECIMAL_PLACES
    rounded = (2 * num * q + x.denominator) // (2 * x.denominator)
    whole, frac = divmod(rounded, q)
    decimal = f"{sign}{whole}.{frac:0{MAX_DECIMAL_PLACES}d}".rstrip("0").rstrip(".")
    fraction = str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"
    # 展示用十进制恰为精确值，当且仅当分母整除 10^18。
    return {
        "fraction": fraction,
        "decimal": decimal,
        "exact": q % x.denominator == 0,
    }


class DistanceIn(BaseModel):
    min: str
    max: str


class ChannelIn(BaseModel):
    wavelength: str
    phase: str
    epsilon: str


class SolveIn(BaseModel):
    distance: DistanceIn
    channels: list[ChannelIn]


def _validate(payload: SolveIn) -> tuple[list[Channel], Fraction, Fraction]:
    errors: list[dict] = []
    lo = parse_decimal(payload.distance.min, ["distance", "min"], errors)
    hi = parse_decimal(payload.distance.max, ["distance", "max"], errors)

    if not 2 <= len(payload.channels) <= 32:
        errors.append(
            {"loc": ["channels"], "msg": "波长通道数必须在 2 到 32 之间"}
        )

    channels: list[Channel] = []
    quarter = Fraction(1, 4)
    for i, c in enumerate(payload.channels):
        wl = parse_decimal(c.wavelength, ["channels", i, "wavelength"], errors)
        ph = parse_decimal(c.phase, ["channels", i, "phase"], errors)
        ep = parse_decimal(c.epsilon, ["channels", i, "epsilon"], errors)
        if wl is not None and wl <= 0:
            errors.append(
                {"loc": ["channels", i, "wavelength"], "msg": "波长必须为正数"}
            )
        if ph is not None and not (Fraction(0) <= ph < 1):
            errors.append(
                {"loc": ["channels", i, "phase"], "msg": "相位必须位于 [0, 1)"}
            )
        if ep is not None and not (Fraction(0) <= ep < quarter):
            errors.append(
                {"loc": ["channels", i, "epsilon"], "msg": "误差界必须满足 0 ≤ ε < 1/4 周"}
            )
        if wl is not None and wl > 0 and ph is not None and ep is not None:
            channels.append(Channel(i, wl, ph, ep))

    if lo is not None and lo < 0:
        errors.append({"loc": ["distance", "min"], "msg": "距离下端点不能为负"})
    if lo is not None and hi is not None and lo > hi:
        errors.append({"loc": ["distance"], "msg": "距离闭区间要求 min ≤ max"})

    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert lo is not None and hi is not None
    return channels, lo, hi


def _witness(index: int, sol, channels: list[Channel]) -> dict:
    rows = []
    verified = True
    for ch, nval in zip(channels, sol.orders):
        r_lo = sol.lower / ch.wavelength - nval - ch.phase
        r_hi = sol.upper / ch.wavelength - nval - ch.phase
        within = (r_lo >= -ch.epsilon) and (r_hi <= ch.epsilon)
        verified = verified and within
        rows.append(
            {
                "index": ch.index,
                "wavelength": q_exact(ch.wavelength),
                "phase": q_exact(ch.phase),
                "epsilon": q_exact(ch.epsilon),
                "order": nval,
                "residual_lower": q_exact(r_lo),
                "residual_upper": q_exact(r_hi),
                "within_tolerance": within,
            }
        )
    return {
        "rank": index + 1,
        "orders": list(sol.orders),
        "distance_band": {
            "lower": q_exact(sol.lower),
            "upper": q_exact(sol.upper),
            "width": q_exact(sol.upper - sol.lower),
        },
        "per_channel": rows,
        "verified": verified,
    }


app = FastAPI(title="多波长激光干涉整周解算工作台", version="1.0.0")

_cors = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() or "*" for o in _cors],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "api"}


@app.post("/api/solve")
def solve_endpoint(payload: SolveIn) -> dict:
    channels, lo, hi = _validate(payload)
    try:
        solutions, cells = solve(channels, lo, hi)
    except SolveLimit as exc:
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "loc": ["body"],
                    "code": "solve_limit",
                    "msg": str(exc),
                }
            ],
        )

    naive = shortest_wavelength_integer_count(channels, lo, hi)
    if not solutions:
        return {
            "status": "infeasible",
            "total_solutions": 0,
            "witnesses": [],
            "verdict": "在给定距离闭区间与各路误差界内，不存在任何整周向量，"
            "即被测距离被明确裁决为无解（读数互不一致或区间过窄）。",
            "stats": {
                "channels": len(channels),
                "cells_refined": cells,
                "naive_shortest_wavelength_integers": naive,
                "max_cells": DEFAULT_MAX_CELLS,
            },
        }

    status = "unique" if len(solutions) == 1 else "multiple"
    witnesses = [_witness(i, s, channels) for i, s in enumerate(solutions[:2])]
    if status == "unique":
        verdict = "仅有一个整周向量可行：距离被唯一锁定在下列精确交集内。"
    else:
        verdict = (
            f"共有 {len(solutions)} 个可行整周向量类别（按距离交集下端点、"
            "整周向量字典序排列），下列为前两份见证；候选不唯一，不能给出唯一读数。"
        )
    return {
        "status": status,
        "total_solutions": len(solutions),
        "witnesses": witnesses,
        "verdict": verdict,
        "stats": {
            "channels": len(channels),
            "cells_refined": cells,
            "naive_shortest_wavelength_integers": naive,
            "max_cells": DEFAULT_MAX_CELLS,
        },
    }


EXAMPLES = [
    {
        "id": "unique-block",
        "title": "唯一解（步规校对，可手算复核）",
        "description": "两路波长均为 1，相位 0.25/0.35，误差 0.1，区间 [0, 1.2]。",
        "input": {
            "distance": {"min": "0", "max": "1.2"},
            "channels": [
                {"wavelength": "1", "phase": "0.25", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0.35", "epsilon": "0.1"},
            ],
        },
    },
    {
        "id": "multi-coincidence",
        "title": "多解（粗测重合，返回前两份见证）",
        "description": "两路完全一致的读数，区间 [0, 3] 内存在四个整周类别。",
        "input": {
            "distance": {"min": "0", "max": "3"},
            "channels": [
                {"wavelength": "1", "phase": "0", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0", "epsilon": "0.1"},
            ],
        },
    },
    {
        "id": "infeasible",
        "title": "无解（相位互斥，明确裁决）",
        "description": "两路波长为 1，相位 0.25 与 0.8，误差 0.1，区间 [0, 3]。",
        "input": {
            "distance": {"min": "0", "max": "3"},
            "channels": [
                {"wavelength": "1", "phase": "0.25", "epsilon": "0.1"},
                {"wavelength": "1", "phase": "0.8", "epsilon": "0.1"},
            ],
        },
    },
    {
        "id": "long-heterodyne",
        "title": "长距离三路激光（41 km，禁止枚举最短波长）",
        "description": "633/532/502 nm 三路，真实距离 41234.75 m（粗测区间仅 10 m），"
        "最短波长在量程内有上万整周，解算只细化数十个分支。",
        "input": {
            "distance": {"min": "41230", "max": "41240"},
            "channels": [
                {"wavelength": "0.000633", "phase": "0.150078988941548", "epsilon": "0.000002"},
                {"wavelength": "0.000532", "phase": "0.571428571428571", "epsilon": "0.000002"},
                {"wavelength": "0.000502", "phase": "0.254980079681275", "epsilon": "0.000002"},
            ],
        },
    },
    {
        "id": "multi-long",
        "title": "长距离多解（0–50 km，四路重合，返回前两份见证）",
        "description": "误差略宽时全量程存在多个合成波长重合候选，按下端点排序展示前两份。",
        "input": {
            "distance": {"min": "0", "max": "50000"},
            "channels": [
                {"wavelength": "0.000633", "phase": "0.150078988941548", "epsilon": "0.000002"},
                {"wavelength": "0.000532", "phase": "0.571428571428571", "epsilon": "0.000002"},
                {"wavelength": "0.000502", "phase": "0.254980079681275", "epsilon": "0.000002"},
                {"wavelength": "0.000589", "phase": "0.516129032258065", "epsilon": "0.000002"},
            ],
        },
    },
]


@app.get("/api/examples")
def examples() -> list[dict]:
    return EXAMPLES
