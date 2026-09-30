"""FastAPI application exposing the leveling-network adjustment service."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import AdjustRequest, AdjustResponse, CorrectionOut
from .optimizer import Observation, adjust
from .validation import NetworkValidationError, validate_network

app = FastAPI(
    title="洞穴水准高程网配平 API",
    description="联合选择整数高程，按字典序目标配平往返水准观测。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/adjust", response_model=AdjustResponse)
def adjust_network(req: AdjustRequest) -> AdjustResponse:
    names = [s.name for s in req.stations]
    index = {name: i for i, name in enumerate(names)}
    benchmark = next(i for i, s in enumerate(req.stations) if s.benchmark)

    try:
        validate_network(names, benchmark, req.observations)
    except NetworkValidationError as exc:
        # Semantic network error (e.g. disconnected station): 422 with a
        # clear Chinese message the UI can show while keeping the draft.
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc)},
        )

    observations = [
        Observation(
            start=index[o.start],
            end=index[o.end],
            delta=o.delta,
            limit=o.limit,
        )
        for o in req.observations
    ]

    result = adjust(names, observations, benchmark, req.benchmark_height)

    if not result.feasible:
        return AdjustResponse(
            feasible=False,
            message=result.reason or "无可行配平：允许改正量不足。",
        )

    corrections = [
        CorrectionOut(
            start=req.observations[k].start,
            end=req.observations[k].end,
            delta=req.observations[k].delta,
            correction=result.corrections[k],
            back_delta=result.back_deltas[k],
            within_limit=abs(result.corrections[k]) <= req.observations[k].limit,
        )
        for k in range(len(req.observations))
    ]

    return AdjustResponse(
        feasible=True,
        elevations=[
            {"name": name, "elevation": h}
            for name, h in zip(names, result.elevations)
        ],
        corrections=corrections,
        max_abs_correction=result.max_abs_correction,
        total_abs_correction=result.total_abs_correction,
        message=(
            f"配平成功：最大绝对改正 {result.max_abs_correction} mm，"
            f"绝对改正总和 {result.total_abs_correction} mm，"
            "任意环路均按返回高程自然闭合。"
        ),
    )
