"""ViralWatch API + dashboard.

Endpoints (auto-documented at /docs):
  GET /earlywarning     -> Kivu zones ranked by early-warning score (watchlist)
  GET /predict/{zone}   -> next-7-day case probability + real context for a zone
  GET /briefing         -> NLP-extracted summary of the latest DON bulletin
  GET /geojson          -> real health-zone boundaries with the score joined on
  GET /health           -> liveness probe (for Render / uptime pingers)
  GET /                 -> the dashboard (static HTML/JS/CSS)

Backend is SQLite by default, or Postgres if DATABASE_URL is set (see app/database.py).
Boundaries + population/health-site/CCVI values are REAL (INRB-UMIE build). The
warning_score / next7d probability are a transparent placeholder for your model.
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
    version="0.2.0",
    description=(
        "Early-warning API for the 2026 Bundibugyo virus outbreak. Cross-border "
        "watchlist for North Kivu and South Kivu health zones bordering Rwanda. "
        "Boundaries + population/health-site data are real (INRB-UMIE); the "
        "warning score is a placeholder for your trained model."
    ),
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"]
)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok", "backend": "postgres" if db.IS_POSTGRES else "sqlite"}


@app.get("/earlywarning", response_model=EarlyWarningResponse, tags=["signals"])
def early_warning():
    """All Kivu health zones ranked by early-warning score, highest first."""
    rows = db.query(
        """
        SELECT zone, province, borders_rwanda, warning_score,
               pop_density, healthsites, updated
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
            pop_density=r["pop_density"],
            healthsites=r["healthsites"],
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

    The probability is precomputed in the DB. Swap in your trained
    scikit-learn / Keras model at the marked line to score live.
    """
    r = db.query_one(
        """
        SELECT zone, province, borders_rwanda, next7d_prob,
               pop_count, pop_density, healthsites, ccvi_deprivation
        FROM zones
        WHERE lower(zone) = lower(?)
        """,
        (zone,),
    )
    if r is None:
        raise HTTPException(status_code=404, detail=f"Unknown health zone: {zone!r}")

    # --- plug in your real model here -------------------------------------
    # from joblib import load
    # model = load(ROOT / "models" / "classifier.joblib")
    # prob = float(model.predict_proba([[...features...]])[0, 1])
    prob = float(r["next7d_prob"])
    # ----------------------------------------------------------------------

    return PredictResponse(
        zone=r["zone"],
        province=r["province"],
        borders_rwanda=bool(r["borders_rwanda"]),
        next7d_case_probability=prob,
        pop_count=r["pop_count"],
        pop_density=r["pop_density"],
        healthsites=r["healthsites"],
        ccvi_deprivation=r["ccvi_deprivation"],
        note="Probability is a placeholder from real vulnerability inputs. Replace with model.predict_proba() — see main.py.",
    )


@app.get("/briefing", response_model=BriefingResponse, tags=["signals"])
def briefing():
    """NLP-extracted situation summary from the latest DON bulletin."""
    zones = [r["zone"] for r in db.query("SELECT zone FROM zones")]
    return BriefingResponse(**extract_briefing(zones))


@app.get("/geojson", tags=["map"])
def geojson():
    """Real health-zone polygons with the current warning score joined onto each
    feature, ready for the Leaflet choropleth."""
    if not GEOJSON_PATH.exists():
        raise HTTPException(status_code=500, detail="zones.geojson not found. Run scripts/build_from_inrb.py + seed_db.py.")
    gj = json.loads(GEOJSON_PATH.read_text(encoding="utf-8"))
    scores = {
        r["zone"]: r
        for r in db.query(
            "SELECT zone, warning_score, next7d_prob, borders_rwanda, pop_density FROM zones"
        )
    }
    for feat in gj.get("features", []):
        s = scores.get(feat["properties"].get("zone"))
        if s:
            feat["properties"]["warning_score"] = s["warning_score"]
            feat["properties"]["next7d_prob"] = s["next7d_prob"]
            feat["properties"]["borders_rwanda"] = bool(s["borders_rwanda"])
            feat["properties"]["pop_density"] = s["pop_density"]
    return JSONResponse(gj)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(DASHBOARD / "index.html")


app.mount("/static", StaticFiles(directory=DASHBOARD), name="static")
