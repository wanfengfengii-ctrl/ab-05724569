"""精确多波长整周求解器。

对通道 i，包裹相位 p_i、波长 λ_i、误差界 ε_i，真实距离 d 满足

    n_i + p_i - ε_i ≤ d/λ_i ≤ n_i + p_i + ε_i,   n_i ∈ ℤ

即距离区间（ε < 1/4 周 ⇒ 带宽严格小于 λ_i/2，不同整周数的带子互不相交）

    I_i(n) = [λ_i(n+p_i-ε_i), λ_i(n+p_i+ε_i)].

寻找全部可行整周向量时严格避免"按最短波长把量程内整周数逐个枚举一遍"：

1. 分支限界 + MRV：每个节点在当前共同距离带上只处理候选整数最少
   （最受限、通常即波长最长 / 已被大幅收窄）的通道；某通道候选为空
   立即剪枝，距离带随深度只缩不扩。
2. 配对模跳变：若所有单路候选数仍然很大，则取一对通道，在统一整数
   刻度 D = d·U 上用 gcd/贝祖等式直接解模数方程
   W_j n_j - W_i n_i ≡ WP_i - WP_j (mod g)，
   一步跳到下一个"两路重合簇"（步长为合成波长 W_i W_j/g，
   与最短波长本身无关），再在簇内对其余通道做 MRV。

所有输入为有限十进制数；选取公倍数刻度 U 后，分支循环内只有整数
运算，距离结果以 Fraction(n, U) 精确还原为有理数。
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd
from typing import Iterator

# 单次解算允许细化的分支（候选整数格 / 重合簇）上限。
DEFAULT_MAX_CELLS = 5_000_000


@dataclass(frozen=True)
class Channel:
    index: int
    wavelength: Fraction
    phase: Fraction
    epsilon: Fraction


@dataclass(frozen=True)
class Solution:
    """一个完整整周向量及其精确距离交集。"""

    orders: tuple[int, ...]
    lower: Fraction
    upper: Fraction


class SolveLimit(RuntimeError):
    """分支数超过穷尽上限时抛出（此时无法保证已找到全部类别）。"""


def floor_f(x: Fraction) -> int:
    return x.numerator // x.denominator


def ceil_f(x: Fraction) -> int:
    return -((-x.numerator) // x.denominator)


def _iceil(a: int, b: int) -> int:
    """ceil(a / b)，b > 0。"""
    return -((-a) // b)


def _ifloor(a: int, b: int) -> int:
    return a // b


def _lcm(a: int, b: int) -> int:
    return a // gcd(a, b) * b


def shortest_wavelength_integer_count(
    channels: list[Channel], lo: Fraction, hi: Fraction
) -> int:
    """朴素全枚举法在量程内需要枚举的整周数（仅用于对照展示）。"""
    ch = min(channels, key=lambda c: c.wavelength)
    a = ceil_f(lo / ch.wavelength)
    b = floor_f(hi / ch.wavelength)
    return max(0, b - a + 1)


def _extgcd(a: int, b: int) -> tuple[int, int, int]:
    """扩展欧几里得：返回 (g, x, y) 使 x*a + y*b = g = gcd(a, b)。"""
    x0, x1, y0, y1 = 1, 0, 0, 1
    while b:
        q = a // b
        a, b = b, a - q * b
        x0, x1 = x1, x0 - q * x1
        y0, y1 = y1, y0 - q * y1
    return a, x0, y0


@dataclass(frozen=True)
class _Scale:
    """统一整数刻度 D = d·U 下各通道的整数参数。"""

    U: int
    W: tuple[int, ...]    # 波长 ×U
    WP: tuple[int, ...]   # 波长 × 相位 ×U（带中心截距）
    WE: tuple[int, ...]   # 波长 × 误差界 ×U（带半宽）

    def candidates(self, i: int, lo: int, hi: int) -> range:
        """共同距离带 [lo, hi]（整数刻度）下通道 i 的候选整周数。"""
        a = _iceil(lo - self.WP[i] - self.WE[i], self.W[i])
        b = _ifloor(hi - self.WP[i] + self.WE[i], self.W[i])
        return range(a, b + 1) if a <= b else range(0, 0)


def _build_scale(
    channels: list[Channel], lo: Fraction, hi: Fraction
) -> tuple[_Scale, int, int]:
    """选取公倍数刻度 U，使全部波长、截距、半宽、端点化为整数。"""
    U = 1
    for ch in channels:
        U = _lcm(U, ch.wavelength.denominator * ch.phase.denominator)
        U = _lcm(U, ch.wavelength.denominator * ch.epsilon.denominator)
    U = _lcm(U, lo.denominator)
    U = _lcm(U, hi.denominator)

    W, WP, WE = [], [], []
    for ch in channels:
        w = ch.wavelength * U
        wp = w * ch.phase
        we = w * ch.epsilon
        assert w.denominator == wp.denominator == we.denominator == 1
        W.append(w.numerator)
        WP.append(wp.numerator)
        WE.append(we.numerator)
    assert (lo * U).denominator == (hi * U).denominator == 1
    return (
        _Scale(U, tuple(W), tuple(WP), tuple(WE)),
        (lo * U).numerator,
        (hi * U).numerator,
    )


def _pair_clusters(
    sc: _Scale, i: int, j: int, lo: int, hi: int
) -> Iterator[tuple[int, int, int, int]]:
    """整数刻度下生成两路 i,j 在 [lo, hi] 内的全部重合簇。

    yields (n_i, n_j, 簇交下界, 簇交上界)。簇按合成波长 W_i W_j/g
    大步跳跃，不枚举任何一路在整个量程内的整周数。
    """
    Wi, Wj = sc.W[i], sc.W[j]
    g, u, v = _extgcd(Wj, Wi)       # u·Wj + v·Wi = g
    si, sj = Wj // g, Wi // g       # n_i、n_j 随齐次参数 k 的步进
    ei, ej = sc.WE[i], sc.WE[j]
    delta = ei + ej
    t = sc.WP[i] - sc.WP[j]         # |Wj n_j - Wi n_i - t| ≤ δ

    for m in range(_iceil(t - delta, g), _ifloor(t + delta, g) + 1):
        ni0, nj0 = -v * m, u * m    # Wj·nj0 - Wi·ni0 = g·m
        # c_i = Wi·n_i + WP_i 的容差半宽带须与 [lo, hi] 相交：
        k_lo = _iceil(lo - ei - sc.WP[i] - Wi * ni0, Wi * si)
        k_hi = _ifloor(hi + ei - sc.WP[i] - Wi * ni0, Wi * si)
        for k in range(k_lo, k_hi + 1):
            ni = ni0 + si * k
            nj = nj0 + sj * k
            ci = Wi * ni + sc.WP[i]
            cj = Wj * nj + sc.WP[j]
            nlo = max(lo, ci - ei, cj - ej)
            nhi = min(hi, ci + ei, cj + ej)
            if nlo <= nhi:
                yield ni, nj, nlo, nhi


def _pair_estimate(sc: _Scale, i: int, j: int, lo: int, hi: int) -> int:
    """配对分支将产生的簇数上界估计（用于与单路 MRV 比较）。"""
    Wi, Wj = sc.W[i], sc.W[j]
    g = gcd(Wi, Wj)
    delta = sc.WE[i] + sc.WE[j]
    t = sc.WP[i] - sc.WP[j]
    m_count = _ifloor(t + delta, g) - _iceil(t - delta, g) + 1
    if m_count <= 0:
        return 0
    step = Wi * Wj // g  # 合成波长（整数刻度）
    return m_count * ((hi - lo) // step + 1) + m_count


def solve(
    channels: list[Channel],
    distance_lo: Fraction,
    distance_hi: Fraction,
    max_cells: int = DEFAULT_MAX_CELLS,
) -> tuple[list[Solution], int]:
    """寻找全部可行整周向量类别。

    返回 (按 (交集下端点, 整周向量字典序) 排好序的解列表, 实际细化分支数)。
    """
    n = len(channels)
    sc, lo, hi = _build_scale(channels, distance_lo, distance_hi)
    U = sc.U
    raw: list[tuple[int, tuple[int, ...], int, int]] = []
    state = {"cells": 0}

    def tick() -> None:
        state["cells"] += 1
        if state["cells"] > max_cells:
            raise SolveLimit(
                f"分支细化次数超过上限 {max_cells}，无法保证穷尽全部类别；"
                "请收窄距离区间或误差界后重试。"
            )

    def rec(pending: frozenset[int], lo: int, hi: int,
            orders: dict[int, int]) -> None:
        if not pending:
            raw.append((lo, tuple(orders[i] for i in range(n)), lo, hi))
            return

        # ---- 单路 MRV：候选整数最少的通道 ----
        best_idx = -1
        best_range: range | None = None
        best_count = 0
        for idx in pending:
            rng = sc.candidates(idx, lo, hi)
            count = rng.stop - rng.start
            if count == 0:
                return  # 该通道已无整数可落，立即剪枝
            if best_range is None or count < best_count:
                best_idx, best_range, best_count = idx, rng, count
                if count == 1:
                    break

        # ---- 配对模跳变：若某对通道的重合簇更少，则改走合成波长 ----
        best_pair: tuple[int, int] | None = None
        plist = list(pending)
        for a in range(len(plist)):
            for b in range(a + 1, len(plist)):
                est = _pair_estimate(sc, plist[a], plist[b], lo, hi)
                if est < best_count:
                    best_count, best_pair = est, (plist[a], plist[b])

        if best_pair is not None:
            i, j = best_pair
            rest = pending - {i, j}
            for ni, nj, nlo, nhi in _pair_clusters(sc, i, j, lo, hi):
                tick()
                orders[i], orders[j] = ni, nj
                rec(rest, nlo, nhi, orders)
                del orders[i], orders[j]
            return

        assert best_range is not None and best_idx >= 0
        rest = pending - {best_idx}
        wi, wpi, wei = sc.W[best_idx], sc.WP[best_idx], sc.WE[best_idx]
        for nval in best_range:
            tick()
            center = wi * nval + wpi
            nlo = max(lo, center - wei)
            nhi = min(hi, center + wei)
            orders[best_idx] = nval
            rec(rest, nlo, nhi, orders)
            del orders[best_idx]

    rec(frozenset(range(n)), lo, hi, {})
    raw.sort(key=lambda r: (r[0], r[1]))
    solutions = [
        Solution(orders, Fraction(lower, U), Fraction(upper, U))
        for _, orders, lower, upper in raw
    ]
    return solutions, state["cells"]
