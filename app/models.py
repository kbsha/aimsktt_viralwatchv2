"""Pydantic models. These give you request/response validation and power the
auto-generated Swagger docs at /docs."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ZoneWarning(BaseModel):
    zone: str = Field(..., description="Health zone name")
    province: str
    borders_rwanda: bool = Field(..., description="Zone shares a border with Rwanda")
    warning_score: float = Field(..., ge=0, le=1, description="Anomaly / early-warning score, 0-1")
    cumulative_cases: int
    new_cases_last7: int
    updated: str = Field(..., description="Date of the latest situation report used")


class EarlyWarningResponse(BaseModel):
    generated_at: str
    n_zones: int
    watchlist: list[ZoneWarning]


class PredictResponse(BaseModel):
    zone: str
    province: str
    borders_rwanda: bool
    next7d_case_probability: float = Field(..., ge=0, le=1)
    cumulative_cases: int
    days_since_first_case: int
    travel_time_min: float = Field(..., description="Road travel time to nearest treatment centre (min)")
    population_density: float
    note: str


class BriefingResponse(BaseModel):
    source: str = Field(..., description="Bulletin the summary was extracted from")
    summary: str
    total_cases: int | None = None
    total_deaths: int | None = None
    case_fatality_ratio: float | None = None
    affected_zones: list[str] = []
    severity_flags: list[str] = []
    cross_border_mentions: list[str] = []
