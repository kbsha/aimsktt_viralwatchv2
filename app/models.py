"""Pydantic models — request/response validation + the /docs Swagger schema."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ZoneWarning(BaseModel):
    zone: str = Field(..., description="Health zone name (INRB canonical 'nom')")
    province: str
    borders_rwanda: bool = Field(..., description="Zone borders Rwanda (Lake Kivu / Ruzizi)")
    warning_score: float = Field(..., ge=0, le=1, description="Early-warning score, 0-1 (placeholder for model output)")
    pop_density: float = Field(..., description="WorldPop population density (people/km²)")
    healthsites: int = Field(..., description="GRID3 health-facility count in the zone")
    updated: str = Field(..., description="INSP sitrep snapshot date")


class EarlyWarningResponse(BaseModel):
    generated_at: str
    n_zones: int
    watchlist: list[ZoneWarning]


class PredictResponse(BaseModel):
    zone: str
    province: str
    borders_rwanda: bool
    next7d_case_probability: float = Field(..., ge=0, le=1)
    pop_count: float = Field(..., description="WorldPop population estimate")
    pop_density: float
    healthsites: int
    ccvi_deprivation: float | None = Field(None, description="CCVI socioeconomic deprivation, 0-1")
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
