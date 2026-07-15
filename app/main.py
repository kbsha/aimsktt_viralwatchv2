"""ViralWatch API + dashboard.

Endpoints (auto-documented at /docs):
  GET /earlywarning     -> all zones ranked by anomaly score (the watchlist)
  GET /predict/{zone}   -> next-7-day case probability for one zone
  GET /briefing         -> NLP-extracted summary of the latest DON bulletin
  GET /geojson          -> health-zone boundaries for the map (joined by name)
  GET /health           -> liveness probe (handy for Render / uptime pingers)
  GET /                 -> the dashboard (static HTML/JS/CSS)

The single service serves both the JSON API and the static dashboard, so the
frontend calls the API on the same origin — no CORS setup needed locally.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import database as db
from app.models import (
    BriefingResponse,
    EarlyWarningResponse,
    PredictResponse,
    ZoneWarning,
)
from app.nlp import extract_briefing

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "dashboard"
GEOJSON_PATH = ROOT / "data" / "processed" / "zones.geojson"

app = FastAPI(
    title="ViralWatch API",
    version="0.1.0",
    description=(
        "Early-warning API for the 2026 Bundibugyo virus outbreak. "
        "Cross-border watchlist focused on North Kivu and South Kivu zones "
        "bordering Rwanda. Data in this skeleton is synthetic — see README."
    ),
)

# Permissive CORS so the frontend still works if you later split it onto its
# own static site / different origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


@app.get("/earlywarning", response_model=EarlyWarningResponse, tags=["signals"])
def early_warning():
    """All health zones ranked by early-warning (anomaly) score, highest first."""
    rows = db.query(
        """
        SELECT zone, province, borders_rwanda, warning_score,
               cumulative_cases, new_cases_last7, updated
        FROM zones
        ORDER BY warning_score DESC
        """
    )
    watchlist = [
        ZoneWarning(
            zone=r["zone"],
            province=r["province"],
            borders_rwanda=bool(r["borders_rwanda"]),
            warning_score=r["warning_score"],
            cumulative_cases=r["cumulative_cases"],
            new_cases_last7=r["new_cases_last7"],
            updated=r["updated"],
        )
        for r in rows
    ]
    generated = rows[0]["updated"] if rows else ""
    return EarlyWarningResponse(
        generated_at=generated, n_zones=len(watchlist), watchlist=watchlist
    )


@app.get("/predict/{zone}", response_model=PredictResponse, tags=["signals"])
def predict(zone: str):
    """Probability that `zone` reports new cases in the next 7 days.

    In this skeleton the probability is precomputed and stored in the DB. Swap in
    your trained scikit-learn / Keras model at the marked line to score live.
    """
    r = db.query_one(
        """
        SELECT zone, province, borders_rwanda, next7d_prob, cumulative_cases,
               days_since_first_case, travel_time_min, population_density
        FROM zones
        WHERE lower(zone) = lower(?)
        """,
        (zone,),
    )
    if r is None:
        raise HTTPException(status_code=404, detail=f"Unknown health zone: {zone!r}")

    # --- plug in our  real model here -------------------------------------








    # from joblib import load
    # model = load(ROOT / "models" / "classifier.joblib")   FROM ROOT FOLDER AIMSKTT_VIRALWATCHV2/MODELS/...
    # prob = float(model.predict_proba([[...features...]])[0, 1])
    prob = float(r["next7d_prob"])
    # ----------------------------------------------------------------------

    return PredictResponse(
        zone=r["zone"],
        province=r["province"],
        borders_rwanda=bool(r["borders_rwanda"]),
        next7d_case_probability=prob,
        cumulative_cases=r["cumulative_cases"],
        days_since_first_case=r["days_since_first_case"],
        travel_time_min=r["travel_time_min"],
        population_density=r["population_density"],
        note="Skeleton value from DB. Replace with live model.predict_proba() — see main.py.",
    )


@app.get("/briefing", response_model=BriefingResponse, tags=["signals"])
def briefing():
    """NLP-extracted situation summary from the latest DON bulletin."""
    zones = [r["zone"] for r in db.query("SELECT zone FROM zones")]
    return BriefingResponse(**extract_briefing(zones))


@app.get("/geojson", tags=["map"])
def geojson():
    """Health-zone polygons with the current warning score joined onto each
    feature's properties, ready for the Leaflet choropleth."""
    if not GEOJSON_PATH.exists():
        raise HTTPException(status_code=500, detail="zones.geojson not found. Run scripts/seed_db.py.")
    gj = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    scores = {
        r["zone"]: r
        for r in db.query(
            "SELECT zone, warning_score, next7d_prob, borders_rwanda, new_cases_last7 FROM zones"
        )
    }
    for feat in gj.get("features", []):
        name = feat["properties"].get("zone")
        s = scores.get(name)
        if s:
            feat["properties"]["warning_score"] = s["warning_score"]
            feat["properties"]["next7d_prob"] = s["next7d_prob"]
            feat["properties"]["borders_rwanda"] = bool(s["borders_rwanda"])
            feat["properties"]["new_cases_last7"] = s["new_cases_last7"]
    return JSONResponse(gj)


# --- static dashboard --------------------------------------------------------
# Serve index.html at "/" and the css/js next to it under /static.
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(DASHBOARD / "index.html")


app.mount("/static", StaticFiles(directory=DASHBOARD), name="static")
