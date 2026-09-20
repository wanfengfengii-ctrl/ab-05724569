"""Exact rational solver for multi-wavelength interferometry phase unwrapping.

Every input is a finite decimal number, hence every quantity derived here is
rational and is computed exactly with ``fractions.Fraction``.  No floating
point approximation ever enters the decision procedure.

Problem
-------
Given a closed distance interval ``[lo, hi]`` and ``m`` channels, each with
wavelength ``λ_i > 0``, wrapped phase ``p_i ∈ [0, 1)`` and error bound
``ε_i < 1/4`` (fraction of a cycle), find every integer vector
``n = (n_1, …, n_m)`` for which some distance ``d ∈ [lo, hi]`` satisfies

    |d / λ_i − n_i − p_i| ≤ ε_i        for every channel i.

For a fixed channel ``i`` and integer ``n_i`` the feasible distances form the
closed "tooth" interval

    T_i(n_i) = [λ_i (n_i + p_i − ε_i),  λ_i (n_i + p_i + ε_i)].

Because ``ε_i < 1/4`` the tooth width ``2 ε_i λ_i < λ_i / 2`` is smaller than
the tooth spacing ``λ_i``, so consecutive teeth of one channel never touch.
Consequently every connected component of the feasible distance set belongs
to exactly one integer vector — a *possibility class* — and its distance set
is the exact intersection  ``[lo, hi] ∩ ⋂_i T_i(n_i)``.

Why not naive enumeration
-------------------------
The textbook mistake is to sweep every fringe order of the *shortest*
wavelength across the whole measurement range, which costs
``O((hi − lo) / λ_min)`` iterations and explodes for long ranges.  This
module never does that.  Two exact strategies are used instead:

``incremental`` (used when the range spans only a modest number of teeth of
the *longest* wavelength):

1. The longest wavelength contributes its teeth over ``[lo, hi]`` — the
   fewest teeth any single channel can have.
2. Each refinement only visits teeth of the next channel that actually
   overlap a surviving interval; the overlapping indices are computed
   directly with exact rational floor/ceil, never by scanning.
   The shortest wavelength is therefore only ever resolved inside already
   narrowed intersection windows, never swept across the range.

``periodic`` (used for long ranges):

1. Each channel is a periodic comb with period ``λ_i``.  Combs are merged
   pairwise with exact rational CRT: for periods ``T1, T2`` the merged comb
   has period ``lcm(T1, T2)`` and every coincidence inside one period is
   found by solving ``k2·t2 − k1·t1 = m`` over a small window of integers
   ``m`` — again without scanning the range.
2. The resulting per-period residue pieces are then instantiated over
   ``[lo, hi]`` *arithmetically*: lifts are computed with floor/ceil and
   distinct integer vectors are counted by merging integer intervals, so the
   cost is independent of how many periods the range spans.

Both strategies return identical results (this is cross-checked by the test
suite against a brute-force oracle).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import ceil, floor, gcd
from typing import Sequence

# Safety valve: beyond this many live classes/pieces the input is considered
# pathological for an interactive workbench and rejected with a clear error
# instead of exhausting memory.
MAX_CLASSES = 200_000

# If the measurement range spans more than this many teeth of the *longest*
# wavelength, switch from the incremental strategy to the periodic (CRT)
# strategy whose cost is independent of the range length.
PERIODIC_THRESHOLD = 4096


class TooManyClassesError(RuntimeError):
    """Raised when the number of possibility classes exceeds the workbench limit."""


@dataclass(frozen=True)
class Channel:
    wavelength: Fraction  # λ > 0
    phase: Fraction       # p, 0 <= p < 1
    epsilon: Fraction     # ε, 0 <= ε < 1/4


@dataclass(frozen=True)
class Witness:
    """One possibility class: its integer vector and exact distance interval."""

    integers: tuple[int, ...]
    lower: Fraction
    upper: Fraction


@dataclass(frozen=True)
class Solution:
    status: str                  # "none" | "unique" | "multiple"
    total: int                   # exact number of possibility classes
    witnesses: tuple[Witness, ...]  # first two classes in canonical order
    mode: str                    # "incremental" | "periodic"
    visited: int                 # tooth candidates examined (algorithmic audit)


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

def class_interval(lo: Fraction, hi: Fraction, channels: Sequence[Channel],
                   vector: Sequence[int]) -> tuple[Fraction, Fraction]:
    """Exact distance intersection ``[lo, hi] ∩ ⋂_i T_i(n_i)``.

    Feasible iff ``lower <= upper`` (intervals are closed).
    """
    lower = lo
    upper = hi
    for ch, n in zip(channels, vector):
        a = ch.wavelength * (n + ch.phase - ch.epsilon)
        b = ch.wavelength * (n + ch.phase + ch.epsilon)
        if a > lower:
            lower = a
        if b < upper:
            upper = b
    return lower, upper


def _verdict(classes: list[tuple[Fraction, Fraction, tuple[int, ...]]],
             mode: str, visited: int) -> Solution:
    """Build the final solution from ``(lower, upper, vector)`` triples."""
    # Canonical order: intersection lower endpoint, then lexicographic vector.
    classes.sort(key=lambda item: (item[0], item[2]))
    total = len(classes)
    witnesses = tuple(
        Witness(integers=vec, lower=a, upper=b) for a, b, vec in classes[:2]
    )
    if total == 0:
        status = "none"
    elif total == 1:
        status = "unique"
    else:
        status = "multiple"
    return Solution(status=status, total=total, witnesses=witnesses,
                    mode=mode, visited=visited)


# ---------------------------------------------------------------------------
# strategy 1: incremental intersection (short ranges)
# ---------------------------------------------------------------------------

def _solve_incremental(lo: Fraction, hi: Fraction,
                       channels: Sequence[Channel]) -> Solution:
    m = len(channels)
    # Longest wavelength first: the initial frontier is as small as any
    # single-channel frontier can be, and later (shorter) wavelengths only
    # ever refine already narrow intervals.
    order = sorted(range(m), key=lambda i: (-channels[i].wavelength, i))
    visited = 0

    first = order[0]
    ch = channels[first]
    # Teeth of this channel overlapping [lo, hi]:
    #   λ(n+p−ε) <= hi  and  λ(n+p+ε) >= lo
    n_lo = ceil(lo / ch.wavelength - ch.phase - ch.epsilon)
    n_hi = floor(hi / ch.wavelength - ch.phase + ch.epsilon)
    # frontier entries: (lower, upper, partial vector indexed by original channel)
    frontier: list[tuple[Fraction, Fraction, list]] = []
    for n in range(n_lo, n_hi + 1):
        visited += 1
        a = ch.wavelength * (n + ch.phase - ch.epsilon)
        b = ch.wavelength * (n + ch.phase + ch.epsilon)
        if a < lo:
            a = lo
        if b > hi:
            b = hi
        if a <= b:
            vec: list = [None] * m
            vec[first] = n
            frontier.append((a, b, vec))

    for idx in order[1:]:
        if not frontier:
            break
        ch = channels[idx]
        refined: list[tuple[Fraction, Fraction, list]] = []
        for a, b, vec in frontier:
            # Only teeth of this channel that overlap the surviving window
            # [a, b] are visited; their indices are computed directly.
            n_lo = ceil(a / ch.wavelength - ch.phase - ch.epsilon)
            n_hi = floor(b / ch.wavelength - ch.phase + ch.epsilon)
            for n in range(n_lo, n_hi + 1):
                visited += 1
                t = ch.wavelength * (n + ch.phase - ch.epsilon)
                u = ch.wavelength * (n + ch.phase + ch.epsilon)
                a2 = a if a > t else t
                b2 = b if b < u else u
                if a2 <= b2:
                    v2 = list(vec)
                    v2[idx] = n
                    refined.append((a2, b2, v2))
                    if len(refined) > MAX_CLASSES:
                        raise TooManyClassesError(
                            f"possibility classes exceed the limit of {MAX_CLASSES}; "
                            "narrow the range or the error bounds"
                        )
        frontier = refined

    # Defensive dedup by integer vector (each class has a unique vector).
    seen: dict[tuple[int, ...], tuple[Fraction, Fraction]] = {}
    for a, b, vec in frontier:
        seen.setdefault(tuple(vec), (a, b))
    classes = [(a, b, vec) for vec, (a, b) in seen.items()]
    return _verdict(classes, "incremental", visited)


# ---------------------------------------------------------------------------
# strategy 2: periodic comb merging via exact CRT (long ranges)
# ---------------------------------------------------------------------------

def _rgcd(a: Fraction, b: Fraction) -> Fraction:
    """Greatest positive rational ``g`` such that ``a/g`` and ``b/g`` are integers."""
    return Fraction(
        gcd(a.numerator * b.denominator, b.numerator * a.denominator),
        a.denominator * b.denominator,
    )


def _single_channel_comb(idx: int, ch: Channel):
    """One channel as a periodic comb: ``(period, pieces)``.

    Each piece is ``(lo, hi, {idx: base_n})`` with ``0 <= lo <= hi <= period``,
    meaning: distances ``d = r + j·period`` with ``r ∈ [lo, hi]`` and integer
    lift ``j`` belong to tooth ``base_n + j`` of this channel.
    """
    period = ch.wavelength
    lo_r = ch.wavelength * (ch.phase - ch.epsilon)   # start of tooth 0
    hi_r = ch.wavelength * (ch.phase + ch.epsilon)   # end of tooth 0
    pieces = []
    # First tooth touching [0, period]: needs hi_r + n·period >= 0.
    n = ceil(-hi_r / period)
    # Teeth while their start is <= period (a tooth starting exactly at
    # `period` is redundant: its residue 0 is owned by the previous tooth).
    while lo_r + n * period <= period:
        a = lo_r + n * period
        b = hi_r + n * period
        lo_c = a if a > 0 else Fraction(0)
        hi_c = b if b < period else period
        if lo_c <= hi_c and lo_c < period:
            pieces.append((lo_c, hi_c, {idx: n}))
        n += 1
    return period, pieces


def _merge_combs(T1: Fraction, pieces1: list, idxs1: list[int],
                 T2: Fraction, pieces2: list, idxs2: list[int],
                 channels: Sequence[Channel], visited: list[int]):
    """Intersect two periodic combs exactly.

    Returns ``(T, pieces, idxs)`` for the merged comb with
    ``T = lcm(T1, T2)``.  For each pair of pieces the coincidences inside one
    merged period are the solutions of ``k2·t2 − k1·t1 = m`` (``t1 = T1/g``,
    ``t2 = T2/g``, ``g = gcd(T1, T2)``) for the few integers ``m`` inside the
    overlap window — never a scan of the measurement range.
    """
    g = _rgcd(T1, T2)
    T = T1 * T2 / g
    t1 = int(T1 / g)
    t2 = int(T2 / g)
    inv = pow(t2, -1, t1) if t1 > 1 else 0
    # Integer slopes: lifting by one own period advances tooth indices.
    s1 = {i: int(T1 / channels[i].wavelength) for i in idxs1}
    s2 = {i: int(T2 / channels[i].wavelength) for i in idxs2}

    out: list = []
    for a1, b1, v1 in pieces1:
        for a2, b2, v2 in pieces2:
            # Overlaps need  a1 − b2 <= k2·T2 − k1·T1 <= b1 − a2,
            # and k2·T2 − k1·T1 ranges over g·Z.
            m_lo = ceil((a1 - b2) / g)
            m_hi = floor((b1 - a2) / g)
            for mm in range(m_lo, m_hi + 1):
                visited[0] += 1
                # Solve k2·t2 − k1·t1 = mm with k2 in [0, t1).
                k2 = (mm * inv) % t1 if t1 > 1 else 0
                k1 = (k2 * t2 - mm) // t1
                lo_d = a1 + k1 * T1
                alt = a2 + k2 * T2
                if alt > lo_d:
                    lo_d = alt
                hi_d = b1 + k1 * T1
                alt = b2 + k2 * T2
                if alt < hi_d:
                    hi_d = alt
                if lo_d > hi_d:
                    continue  # cannot happen given the m-window; stay exact
                vec = {}
                for i in idxs1:
                    vec[i] = v1[i] + k1 * s1[i]
                for i in idxs2:
                    vec[i] = v2[i] + k2 * s2[i]
                out.append((lo_d, hi_d, vec))
                if len(out) > MAX_CLASSES:
                    raise TooManyClassesError(
                        f"possibility classes exceed the limit of {MAX_CLASSES}; "
                        "narrow the range or the error bounds"
                    )
    return T, out, idxs1 + idxs2


def _xgcd(a: int, b: int) -> tuple[int, int, int]:
    """Extended gcd: ``(x, y, g)`` with ``x·a + y·b == g == gcd(a, b) > 0``."""
    old_r, r = a, b
    old_s, s = 1, 0
    old_t, t = 0, 1
    while r:
        q = old_r // r
        old_r, r = r, old_r - q * r
        old_s, s = s, old_s - q * s
        old_t, t = t, old_t - q * t
    return old_s, old_t, old_r


def _bezout(values: Sequence[int]) -> list[int]:
    """Coefficients ``c`` with ``Σ c_i·values_i == gcd(values)``."""
    g = values[0]
    coeffs = [1]
    for v in values[1:]:
        a, b, g = _xgcd(g, v)
        coeffs = [a * c for c in coeffs] + [b]
    return coeffs


def _solve_periodic(lo: Fraction, hi: Fraction,
                    channels: Sequence[Channel]) -> Solution:
    m = len(channels)
    order = sorted(range(m), key=lambda i: (-channels[i].wavelength, i))
    visited = [0]

    idx = order[0]
    T, pieces = _single_channel_comb(idx, channels[idx])
    idxs = [idx]
    for idx in order[1:]:
        T2, pieces2 = _single_channel_comb(idx, channels[idx])
        T, pieces, idxs = _merge_combs(T, pieces, idxs, T2, pieces2, [idx],
                                       channels, visited)

    # Slope vector: lifting a residue by one full period T advances the tooth
    # index of channel i by exactly s_i = T / λ_i (a positive integer).
    slopes = {i: int(T / channels[i].wavelength) for i in idxs}
    s_vec = [slopes[i] for i in idxs]
    # gcd(s_1, …, s_m) == 1 because T is the *least* common multiple, so a
    # linear functional f with f(s) = 1 exists; it labels every integer
    # vector on a coset of Z·s with a single exact scalar.
    coeffs = _bezout(s_vec)

    cosets: dict[tuple[int, ...], list[tuple[int, int]]] = {}
    # Witness candidates: per piece only the first two lifts can belong to
    # the globally first two classes (per-piece class lower endpoints are
    # non-decreasing in the lift index).
    candidates: dict[tuple[int, ...], Fraction] = {}

    for a, b, v in pieces:
        j_lo = ceil((lo - b) / T)
        j_hi = floor((hi - a) / T)
        if j_lo > j_hi:
            continue
        f_v = sum(c * v[i] for c, i in zip(coeffs, idxs))
        key = tuple(v[i] - f_v * slopes[i] for i in idxs)
        cosets.setdefault(key, []).append((f_v + j_lo, f_v + j_hi))
        for j in (j_lo, j_lo + 1):
            if j > j_hi:
                continue
            # Integer vector in the ORIGINAL channel order.
            vec = tuple(v[i] + j * slopes[i] for i in range(m))
            if vec not in candidates:
                lower, _ = class_interval(lo, hi, channels, vec)
                candidates[vec] = lower

    # Exact class count: within one coset, vectors correspond bijectively to
    # scalars, so distinct vectors are counted by merging integer intervals.
    total = 0
    for intervals in cosets.values():
        intervals.sort()
        cur_lo, cur_hi = intervals[0]
        for x, y in intervals[1:]:
            if x > cur_hi + 1:
                total += cur_hi - cur_lo + 1
                cur_lo, cur_hi = x, y
            elif y > cur_hi:
                cur_hi = y
        total += cur_hi - cur_lo + 1

    ordered = sorted(candidates.items(), key=lambda kv: (kv[1], kv[0]))
    witnesses = []
    for vec, _ in ordered[:2]:
        lower, upper = class_interval(lo, hi, channels, vec)
        witnesses.append(Witness(integers=vec, lower=lower, upper=upper))

    if total == 0:
        status = "none"
    elif total == 1:
        status = "unique"
    else:
        status = "multiple"
    return Solution(status=status, total=total, witnesses=tuple(witnesses),
                    mode="periodic", visited=visited[0])


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def solve(lo: Fraction, hi: Fraction, channels: Sequence[Channel]) -> Solution:
    """Find every possibility class for the given measurement.

    Returns the exact count of classes and the first one/two of them in
    canonical order (intersection lower endpoint, then lexicographic integer
    vector).
    """
    if not channels:
        raise ValueError("at least one channel is required")
    lam_max = max(c.wavelength for c in channels)
    span_teeth = (hi - lo) / lam_max
    if span_teeth <= PERIODIC_THRESHOLD:
        return _solve_incremental(lo, hi, channels)
    return _solve_periodic(lo, hi, channels)
