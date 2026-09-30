"""Request/response models for the leveling adjustment API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

MIN_STATIONS = 5
MAX_STATIONS = 10
MIN_OBSERVATIONS = 7
MAX_OBSERVATIONS = 18
NAME_MAX_LEN = 20


class ObservationIn(BaseModel):
    start: str = Field(..., description="起点测站名称")
    end: str = Field(..., description="终点测站名称")
    delta: int = Field(..., description="实测高差，整数毫米（沿 start -> end 方向）")
    limit: int = Field(..., ge=0, description="该观测最大允许改正量，非负整数毫米")

    @field_validator("start", "end")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("测站名称不能为空")
        if len(v) > NAME_MAX_LEN:
            raise ValueError(f"测站名称不能超过 {NAME_MAX_LEN} 个字符")
        return v


class StationIn(BaseModel):
    name: str
    benchmark: bool = False

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("测站名称不能为空")
        if len(v) > NAME_MAX_LEN:
            raise ValueError(f"测站名称不能超过 {NAME_MAX_LEN} 个字符")
        return v


class AdjustRequest(BaseModel):
    stations: list[StationIn] = Field(
        ...,
        min_length=MIN_STATIONS,
        max_length=MAX_STATIONS,
        description="按录入顺序排列的 5-10 个唯一测站",
    )
    benchmark_height: int = Field(..., description="基准点已知高程，整数毫米")
    observations: list[ObservationIn] = Field(
        ...,
        min_length=MIN_OBSERVATIONS,
        max_length=MAX_OBSERVATIONS,
        description="7-18 条带方向的高差观测",
    )

    @model_validator(mode="after")
    def _validate_network(self) -> "AdjustRequest":
        names = [s.name for s in self.stations]
        if len(set(names)) != len(names):
            raise ValueError("测站名称必须唯一，不能重复")
        benchmarks = [s.name for s in self.stations if s.benchmark]
        if len(benchmarks) != 1:
            raise ValueError("必须且只能指定一个基准测站")
        known = set(names)
        for o in self.observations:
            if o.start not in known:
                raise ValueError(f"观测起点 {o.start!r} 不在测站列表中")
            if o.end not in known:
                raise ValueError(f"观测终点 {o.end!r} 不在测站列表中")
            if o.start == o.end:
                raise ValueError("观测起点与终点不能相同")
        return self


class CorrectionOut(BaseModel):
    start: str
    end: str
    delta: int = Field(..., description="实测高差，mm")
    correction: int = Field(..., description="改正值 c = H_end - H_start - delta，mm")
    back_delta: int = Field(..., description="回算高差 H_end - H_start，mm")
    within_limit: bool


class AdjustResponse(BaseModel):
    feasible: bool
    elevations: list[dict] = Field(
        default_factory=list,
        description="按录入顺序排列的 {name, elevation}，mm",
    )
    corrections: list[CorrectionOut] = Field(default_factory=list)
    max_abs_correction: int = 0
    total_abs_correction: int = 0
    message: str
