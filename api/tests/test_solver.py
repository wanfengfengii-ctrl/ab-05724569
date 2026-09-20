"""Unit tests for the exact rational solver.

The property tests cross-check both solver strategies (incremental and
periodic) against a naive brute-force oracle that scans every fringe order of
every channel over the range — the very approach the solver itself must
avoid.
"""

from __future__ import annotations

import random
from fractions import Fraction

import pytest

from app.solver import (
    Channel,
    Solution,
    TooManyClassesError,
    _solve_incremental,
    _solve_periodic,
    class_interval,
    solve,
)

F = Fraction


def ch(w, p, e) -> Channel:
    return Channel(F(w), F(p), F(e))


def brute_force(lo: Fraction, hi: Fraction, channels) -> list[tuple[tuple[int, ...], Fraction, Fraction]]:
    """Naive oracle: enumerate every tooth of every channel over the range."""
    per_channel = []
    for c in channels:
        teeth = []
        n = int(lo // c.wavelength) - 2
        while c.wavelength * (n + c.phase - c.epsilon) <= hi:
            if c.wavelength * (n + c.phase + c.epsilon) >= lo:
                teeth.append(n)
            n += 1
        per_channel.append(teeth)

    classes = []

    def rec(i, vec):
        if i == len(channels):
            a, b = class_interval(lo, hi, channels, vec)
            if a <= b:
                classes.append((tuple(vec), a, b))
            return
        for n in per_channel[i]:
            rec(i + 1, vec + [n])

    rec(0, [])
    classes.sort(key=lambda item: (item[1], item[0]))
    return classes


def assert_matches_oracle(lo, hi, channels, sol: Solution):
    oracle = brute_force(lo, hi, channels)
    assert sol.total == len(oracle), f"count mismatch: {sol.total} != {len(oracle)}"
    if not oracle:
        assert sol.status == "none"
        assert sol.witnesses == ()
        return
    assert sol.status == ("unique" if len(oracle) == 1 else "multiple")
    for witness, (vec, a, b) in zip(sol.witnesses, oracle[:2]):
        assert witness.integers == vec
        assert witness.lower == a
        assert witness.upper == b


# ---------------------------------------------------------------------------
# hand-computed cases
# ---------------------------------------------------------------------------

def test_unique_exact_fractions():
    # Teeth: ch1 n=0 -> [0.9, 1.1]; ch2 n=0 -> [0.75, 1.05].  Only overlap.
    channels = [ch("2", "0.5", "0.05"), ch("3", "0.3", "0.05")]
    sol = solve(F(0), F(4), channels)
    assert sol.status == "unique"
    assert sol.total == 1
    (w,) = sol.witnesses
    assert w.integers == (0, 0)
    assert w.lower == F(9, 10)
    assert w.upper == F(21, 20)


def test_multiple_two_witnesses_in_order():
    # Classes (0,0) -> [0.8, 1.05] and (3,2) -> [6.8, 7.05].
    channels = [ch("2", "0.5", "0.1"), ch("3", "0.25", "0.1")]
    sol = solve(F(0), F(10), channels)
    assert sol.status == "multiple"
    assert sol.total == 2
    first, second = sol.witnesses
    assert first.integers == (0, 0)
    assert (first.lower, first.upper) == (F(4, 5), F(21, 20))
    assert second.integers == (3, 2)
    assert (second.lower, second.upper) == (F(34, 5), F(141, 20))


def test_none_verdict():
    channels = [ch("2", "0.5", "0.05"), ch("3", "0.5", "0.05")]
    sol = solve(F(0), F(4), channels)
    assert sol.status == "none"
    assert sol.total == 0
    assert sol.witnesses == ()


def test_touching_closed_intervals_are_feasible():
    # ch1 tooth n=0: [0.9, 1.1]; ch2 tooth n=0: [1.1, 1.4] -> touch at d = 1.1.
    channels = [ch("2", "0.5", "0.05"), ch("4", "0.3125", "0.0375")]
    sol = solve(F(0), F(4), channels)
    assert sol.status == "unique"
    w = sol.witnesses[0]
    assert w.lower == w.upper == F(11, 10)


def test_negative_integers_and_range():
    # Single class (-5, -3) -> [-8.85, -8.6].
    channels = [ch("2", "0.5", "0.2"), ch("3", "0.25", "0.2")]
    sol = solve(F(-10), F(-6), channels)
    assert_matches_oracle(F(-10), F(-6), channels, sol)
    assert sol.status == "unique"
    w = sol.witnesses[0]
    assert w.integers == (-5, -3)
    assert (w.lower, w.upper) == (F(-177, 20), F(-43, 5))


def test_zero_epsilon():
    # d = 2n+1 and d = 3m+0.75 -> 2n-3m = -0.25 has no integer solution.
    channels = [ch("2", "0.5", "0"), ch("3", "0.25", "0")]
    sol = solve(F(0), F(100), channels)
    assert sol.status == "none"
    # d = 2n+1 = 3m+2 -> d = 5, 11, 17, ... (period 6).
    channels = [ch("2", "0.5", "0"), ch("3", F(2, 3), "0")]
    sol = solve(F(0), F(100), channels)
    assert sol.status == "multiple"
    assert sol.witnesses[0].integers == (2, 1)
    assert sol.witnesses[0].lower == sol.witnesses[0].upper == F(5)
    assert sol.witnesses[1].integers == (5, 3)
    assert sol.witnesses[1].lower == F(11)


def test_class_lowers_are_strictly_separated():
    # Teeth of one channel have positive gaps, so distinct classes have
    # strictly increasing lower endpoints (the lexicographic tie-break in the
    # ordering rule is a formality that can never trigger).
    channels = [ch("2", "0.5", "0.1"), ch("3", "0.25", "0.1")]
    sol = solve(F(0), F(10), channels)
    lowers = [w.lower for w in sol.witnesses]
    assert lowers == sorted(lowers)
    oracle = brute_force(F(0), F(10), channels)
    all_lowers = sorted(a for _, a, _ in oracle)
    assert len(all_lowers) == len(set(all_lowers))


def test_many_channels_crosscheck():
    channels = [
        ch("2", "0.5", "0.1"),
        ch("3", "0.25", "0.1"),
        ch("5", "0.4", "0.05"),
        ch("7", "0.1", "0.05"),
    ]
    sol = solve(F(0), F(60), channels)
    assert_matches_oracle(F(0), F(60), channels, sol)


def test_thirty_two_channels():
    # Intersection of all 32 teeth for order n: [n + 31/80 - 0.2, n + 0.2].
    channels = [ch("1", F(i, 80), "0.2") for i in range(32)]
    sol = solve(F(0), F(3), channels)
    assert sol.total == 3
    assert sol.witnesses[0].integers == (0,) * 32
    assert (sol.witnesses[0].lower, sol.witnesses[0].upper) == (F(3, 16), F(1, 5))
    assert sol.witnesses[1].integers == (1,) * 32
    assert (sol.witnesses[1].lower, sol.witnesses[1].upper) == (F(19, 16), F(6, 5))


# ---------------------------------------------------------------------------
# long-range behaviour: no naive enumeration of the shortest wavelength
# ---------------------------------------------------------------------------

def test_long_range_uses_periodic_mode_without_scanning():
    # Range spans ~1e6 teeth of the shortest wavelength; the solver must not
    # visit anywhere near that many candidates.
    channels = [ch("1000", "0", "0.01"), ch("1001", "0", "0.01")]
    sol = solve(F(0), F(10**9), channels)
    assert sol.mode == "periodic"
    assert sol.status == "multiple"
    assert sol.visited < 10_000  # naive scan would need ~1e6
    # Hand-derived: feasible iff |1000 n1 - 1001 n2| <= 20 (41 diophantine
    # offsets); k=0 and k=-1 contribute 1000 classes each over [0, 1e9],
    # the other 39 offsets 999 each -> 2*1000 + 39*999.
    assert sol.total == 40961
    first, second = sol.witnesses
    assert first.integers == (0, 0)
    assert (first.lower, first.upper) == (F(0), F(10))
    assert second.integers == (1, 1)
    assert (second.lower, second.upper) == (F(99099, 100), F(1010))


def test_long_range_total_matches_incremental_on_moderate_span():
    # Cross-check periodic vs incremental on a span both can handle.
    channels = [ch("1000", "0", "0.01"), ch("1001", "0", "0.01")]
    hi = F(5_000_000)
    inc = _solve_incremental(F(0), hi, channels)
    per = _solve_periodic(F(0), hi, channels)
    assert inc.total == per.total
    assert [w.integers for w in inc.witnesses] == [w.integers for w in per.witnesses]
    assert [(w.lower, w.upper) for w in inc.witnesses] == [
        (w.lower, w.upper) for w in per.witnesses
    ]


def test_huge_range_count_is_arithmetic():
    # 1e9 teeth of the shortest wavelength: counted arithmetically, not scanned.
    channels = [ch("1", "0.5", "0.1"), ch("2", "0.25", "0.1")]
    sol = solve(F(0), F(10**9), channels)
    assert sol.mode == "periodic"
    assert sol.visited < 100
    # Feasible iff n1 = 2 n2; class t -> [2t+0.4, 2t+0.6]; t in [0, 499999999].
    assert sol.total == 500_000_000
    assert sol.witnesses[0].integers == (0, 0)
    assert sol.witnesses[0].lower == F(2, 5)
    assert sol.witnesses[0].upper == F(3, 5)
    assert sol.witnesses[1].integers == (2, 1)


def test_too_many_classes_raises():
    # Per-period coincidence count explodes (~1e8 pieces) for three close
    # wavelengths with wide error bounds.
    channels = [ch("1", "0", "0.24"), ch("1.0001", "0", "0.24"), ch("1.0002", "0", "0.24")]
    with pytest.raises(TooManyClassesError):
        _solve_periodic(F(0), F(10**6), channels)


# ---------------------------------------------------------------------------
# randomized cross-validation against the brute-force oracle
# ---------------------------------------------------------------------------

def random_case(rng: random.Random):
    """Small case that keeps the exponential brute-force oracle feasible."""
    m = rng.randint(2, 3)
    channels = []
    for _ in range(m):
        w = F(rng.randint(2, 24), rng.choice([1, 2]))
        p = F(rng.randint(0, 19), 20)
        e = F(rng.randint(0, 24), 100)
        channels.append(Channel(w, p, e))
    lo = F(rng.randint(-20, 0))
    hi = lo + F(rng.randint(0, 24), rng.choice([1, 2]))
    return lo, hi, channels


@pytest.mark.parametrize("seed", range(60))
def test_incremental_matches_oracle(seed):
    rng = random.Random(seed)
    lo, hi, channels = random_case(rng)
    assert_matches_oracle(lo, hi, channels, _solve_incremental(lo, hi, channels))


@pytest.mark.parametrize("seed", range(60))
def test_periodic_matches_oracle(seed):
    rng = random.Random(10_000 + seed)
    lo, hi, channels = random_case(rng)
    assert_matches_oracle(lo, hi, channels, _solve_periodic(lo, hi, channels))


@pytest.mark.parametrize("seed", range(40))
def test_periodic_matches_incremental_on_long_ranges(seed):
    rng = random.Random(20_000 + seed)
    m = rng.randint(2, 3)
    channels = []
    for _ in range(m):
        w = F(rng.randint(50, 400), rng.choice([1, 2, 4]))
        p = F(rng.randint(0, 19), 20)
        e = F(rng.randint(0, 20), 100)
        channels.append(Channel(w, p, e))
    lo = F(0)
    hi = F(rng.randint(5_000, 40_000))
    inc = _solve_incremental(lo, hi, channels)
    per = _solve_periodic(lo, hi, channels)
    assert inc.total == per.total
    assert inc.status == per.status
    assert [(w.integers, w.lower, w.upper) for w in inc.witnesses] == [
        (w.integers, w.lower, w.upper) for w in per.witnesses
    ]
