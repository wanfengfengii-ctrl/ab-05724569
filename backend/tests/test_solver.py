"""求解器测试：精确性、排序、非枚举性，并与朴素最短波长枚举对拍。"""
from __future__ import annotations

import random
from fractions import Fraction

import pytest

from app.solver import (
    Channel,
    SolveLimit,
    ceil_f,
    floor_f,
    shortest_wavelength_integer_count,
    solve,
)


def ch(i, w, p, e="0.1") -> Channel:
    return Channel(i, Fraction(w), Fraction(p), Fraction(e))


def brute_force(channels, lo, hi):
    """参照实现：严格按最短波长优先逐层枚举（即题目禁止的做法）。"""
    order = sorted(range(len(channels)), key=lambda i: channels[i].wavelength)
    sols = []

    def rec(k, l, h, ns):
        if l > h:
            return
        if k == len(order):
            sols.append((tuple(ns[i] for i in range(len(channels))), l, h))
            return
        i = order[k]
        c = channels[i]
        a = ceil_f(l / c.wavelength - c.phase - c.epsilon)
        b = floor_f(h / c.wavelength - c.phase + c.epsilon)
        for n in range(a, b + 1):
            ns[i] = n
            rec(
                k + 1,
                max(l, c.wavelength * (n + c.phase - c.epsilon)),
                min(h, c.wavelength * (n + c.phase + c.epsilon)),
                ns,
            )
            del ns[i]

    rec(0, lo, hi, {})
    sols.sort(key=lambda s: (s[1], s[0]))
    return sols


def test_floor_ceil_negatives():
    assert floor_f(Fraction(-1, 3)) == -1
    assert ceil_f(Fraction(-1, 3)) == 0
    assert floor_f(Fraction(5, 2)) == 2
    assert ceil_f(Fraction(5, 2)) == 3


def test_block_gauge_unique():
    cs = [ch(0, "1", "0.25"), ch(1, "1", "0.35")]
    sols, cells = solve(cs, Fraction(0), Fraction("1.2"))
    assert len(sols) == 1
    assert sols[0].orders == (0, 0)
    assert sols[0].lower == Fraction("0.25")
    assert sols[0].upper == Fraction("0.35")


def test_multiple_sorted_and_pairwise_disjoint():
    cs = [ch(0, "1", "0"), ch(1, "1", "0")]
    sols, _ = solve(cs, Fraction(0), Fraction(3))
    assert [s.orders for s in sols] == [(0, 0), (1, 1), (2, 2), (3, 3)]
    lowers = [s.lower for s in sols]
    assert lowers == sorted(lowers)
    for a, b in zip(sols, sols[1:]):
        assert a.upper <= b.lower  # ε<1/4 ⇒ 类别互不交叠


def test_infeasible_empty():
    cs = [ch(0, "1", "0.25"), ch(1, "1", "0.8")]
    sols, cells = solve(cs, Fraction(0), Fraction(3))
    assert sols == []


def test_heterogeneous_wavelengths_exact_band():
    cs = [ch(0, "2", "0.25", "0.05"), ch(1, "3", "0.5", "0.1")]
    sols, _ = solve(cs, Fraction(0), Fraction(20))
    for s in sols:
        for c, n in zip(cs, s.orders):
            assert s.lower / c.wavelength >= n + c.phase - c.epsilon
            assert s.upper / c.wavelength <= n + c.phase + c.epsilon


def test_random_cross_check_against_brute_force():
    rng = random.Random(20260920)
    decs = [1, 2, 3, 4, 5, 6, 8, 10, 12]

    def decfrac(n_ints=5, den_exp=3):
        return Fraction(rng.randint(1, n_ints * 10 ** den_exp), 10 ** den_exp)

    for trial in range(300):
        m = rng.randint(2, 5)
        channels = []
        for i in range(m):
            w = Fraction(rng.randint(2, 9), 10 ** rng.randint(0, 2))
            p = Fraction(rng.randint(0, 99), 100)
            e = Fraction(rng.randint(0, 24), 100)
            channels.append(Channel(i, w, p, e))
        lo = decfrac()
        hi = lo + Fraction(rng.randint(1, 60), 10)
        expected = brute_force(channels, lo, hi)
        sols, _ = solve(channels, lo, hi)
        got = [(s.orders, s.lower, s.upper) for s in sols]
        assert got == expected, f"trial {trial} mismatch"


def test_long_range_does_not_enumerate_shortest_wavelength():
    d = Fraction("41234.75")
    raw = [
        ("0.000633", "0.150078988941548"),
        ("0.000532", "0.571428571428571"),
        ("0.000502", "0.254980079681275"),
    ]
    cs = [
        Channel(i, Fraction(w), Fraction(p), Fraction("0.000002"))
        for i, (w, p) in enumerate(raw)
    ]
    lo, hi = Fraction("41230"), Fraction("41240")
    naive = shortest_wavelength_integer_count(cs, lo, hi)
    sols, cells = solve(cs, lo, hi)
    assert naive > 15_000            # 朴素做法需枚举上万整周
    assert cells < naive // 100      # 实际细化不足其百分之一
    assert len(sols) == 1
    s = sols[0]
    assert s.orders == (65141785, 77508928, 82140936)
    assert s.lower <= d <= s.upper
    assert s.upper - s.lower < Fraction("0.00001")


def test_long_range_full_scale_pair_jump_fast():
    raw = [
        ("0.000633", "0.150078988941548"),
        ("0.000532", "0.571428571428571"),
        ("0.000502", "0.254980079681275"),
        ("0.000589", "0.516129032258065"),
    ]
    cs = [
        Channel(i, Fraction(w), Fraction(p), Fraction("0.000002"))
        for i, (w, p) in enumerate(raw)
    ]
    lo, hi = Fraction(0), Fraction(50000)
    naive = shortest_wavelength_integer_count(cs, lo, hi)
    sols, cells = solve(cs, lo, hi)
    assert naive > 80_000_000
    assert cells < naive // 500
    assert len(sols) == 19
    assert sols[0].orders < sols[1].orders or sols[0].lower < sols[1].lower


def test_solve_limit_guards_pathological_input():
    # 宽误差 + 大量重复长波类别 → 触顶必须抛出而非静默截断。
    cs = [
        Channel(i, Fraction("0.000633"), Fraction("0.1"), Fraction("0.24"))
        for i in range(2)
    ]
    with pytest.raises(SolveLimit):
        solve(cs, Fraction(0), Fraction(50000), max_cells=10_000)
