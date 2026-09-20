"""FastAPI application for the multi-wavelength interferometry workbench."""

from __future__ import annotations

from fractions import Fraction
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .schemas import SolveInput
from .solver import Channel, Solution, TooManyClassesError, solve

app = FastAPI(
    title="Multi-wavelength Interferometry Workbench",
    version="1.0.0",
    description=(
        "Exact rational phase-unwrapping: finds every integer-fringe vector "
        "consistent with per-channel |d/λ − n − p| ≤ ε over a closed distance "
        "interval."
    ),
)

# The production frontend is served same-origin through nginx; CORS is only
# needed for local development (vite dev server on another port).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


def _exact(value: Fraction) -> str:
    """Canonical exact string: an integer, or ``numerator/denominator``."""
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _num(value: Fraction) -> dict:
    return {"exact": _exact(value), "approx": float(value)}


def _witness_payload(solution_channels: list[Channel], witness) -> dict:
    lower, upper = witness.lower, witness.upper
    per_channel = []
    for idx, (ch, n) in enumerate(zip(solution_channels, witness.integers)):
        band_lo = ch.wavelength * (n + ch.phase - ch.epsilon)
        band_hi = ch.wavelength * (n + ch.phase + ch.epsilon)
        # Residual r(d) = d/λ − n − p evaluated over the common band [lower, upper].
        res_lo = lower / ch.wavelength - n - ch.phase
        res_hi = upper / ch.wavelength - n - ch.phase
        per_channel.append(
            {
                "index": idx,
                "integer": n,
                "band": {"lo": _num(band_lo), "hi": _num(band_hi)},
                "residual": {"lo": _num(res_lo), "hi": _num(res_hi)},
            }
        )
    return {
        "integers": list(witness.integers),
        "interval": {"lo": _num(lower), "hi": _num(upper)},
        "channels": per_channel,
    }


@app.post("/api/solve")
def solve_endpoint(payload: SolveInput) -> dict:
    channels = [Channel(c.wavelength, c.phase, c.epsilon) for c in payload.channels]
    started = perf_counter()
    try:
        solution: Solution = solve(payload.range.lo, payload.range.hi, channels)
    except TooManyClassesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    elapsed_ms = (perf_counter() - started) * 1000.0

    return {
        "status": solution.status,
        "total_classes": solution.total,
        "mode": solution.mode,
        "candidates_examined": solution.visited,
        "elapsed_ms": round(elapsed_ms, 3),
        "range": {"lo": _num(payload.range.lo), "hi": _num(payload.range.hi)},
        "channels": [
            {
                "index": idx,
                "wavelength": _num(c.wavelength),
                "phase": _num(c.phase),
                "epsilon": _num(c.epsilon),
            }
            for idx, c in enumerate(payload.channels)
        ],
        "witnesses": [_witness_payload(channels, w) for w in solution.witnesses],
    }
