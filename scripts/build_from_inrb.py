"""Turn the INRB-UMIE national health-zone GeoJSON into the two lightweight files
the app ships with:

  data/processed/zones.geojson        real polygons for the Kivu zones (simplified)
  data/processed/zone_attributes.csv  real per-zone attributes (pop, health sites, CCVI)

Source (canonical health-zone boundaries + contextual data), ~9.7 MB:
  https://raw.githubusercontent.com/INRB-UMIE/BDBV2026-Data/main/build/drc_health_zones.geojson

Usage:
    pip install -r requirements-dev.txt          # needs shapely
    # download the source once:
    curl -L -o data/raw/drc_health_zones.geojson \\
      https://raw.githubusercontent.com/INRB-UMIE/BDBV2026-Data/main/build/drc_health_zones.geojson
    python scripts/build_from_inrb.py data/raw/drc_health_zones.geojson
    python scripts/seed_db.py                     # rebuild DB from the processed files

Change PROVINCES below to widen/narrow coverage (e.g. add "Ituri", where the
2026 case activity in this snapshot actually sits).
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_GEOJSON = ROOT / "data" / "processed" / "zones.geojson"
OUT_CSV = ROOT / "data" / "processed" / "zone_attributes.csv"

# Rwanda-bordering focus of the project: the two Kivu provinces.
PROVINCES = {"North-Kivu", "South-Kivu"}
SIMPLIFY_TOLERANCE = 0.008  # degrees; balances fidelity vs browser file size

# Curated set of Kivu health zones that border Rwanda (Lake Kivu / Ruzizi).
# A production build would intersect geometry with Rwanda's admin boundary;
# this hand-checked list is a defensible approximation for the watchlist.
BORDERS_RWANDA = {
    "Goma", "Karisimbi", "Nyiragongo", "Kirotshe", "Rutshuru", "Rwanguba",
    "Idjwi", "Kalehe", "Minova", "Katana", "Kabare", "Bagira", "Ibanda",
    "Kadutu", "Nyangezi", "Ruzizi",
}


def deep_num(d):
    """Pull the innermost scalar out of the nested {key:{key:value,_date:..}} shape.
    Returns None for missing / 'NA' / 'ND'."""
    if isinstance(d, dict):
        for k, v in d.items():
            if k == "_date":
                continue
            r = deep_num(v)
            if r is not None:
                return r
        return None
    if d in ("NA", "ND", "", None):
        return None
    try:
        return float(d)
    except (TypeError, ValueError):
        return None


def main(src_path: str):
    from shapely.geometry import shape, mapping

    gj = json.loads(Path(src_path).read_text(encoding="utf-8"))
    feats = [f for f in gj["features"] if f["properties"].get("province") in PROVINCES]
    print(f"Selected {len(feats)} zones in {sorted(PROVINCES)}")

    out_features = []
    rows = []
    for f in feats:
        p = f["properties"]
        nom = p["nom"]
        geom = shape(f["geometry"]).simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)

        out_features.append({
            "type": "Feature",
            "properties": {
                "zone": nom,
                "province": p["province"],
                "borders_rwanda": nom in BORDERS_RWANDA,
            },
            "geometry": mapping(geom),
        })

        rows.append({
            "zone": nom,
            "province": p["province"],
            "borders_rwanda": int(nom in BORDERS_RWANDA),
            "pop_count": deep_num(p.get("worldpop", {}).get("pop_count")) or 0,
            "pop_density": deep_num(p.get("worldpop", {}).get("pop_density")) or 0,
            "healthsites": int(deep_num(p.get("grid3_healthsites", {}).get("healthsite_count")) or 0),
            "ccvi_deprivation": deep_num(
                p.get("ccvi", {}).get("socioeconomic_deprivation")
            ),
        })

    OUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_GEOJSON.write_text(
        json.dumps({"type": "FeatureCollection", "features": out_features}),
        encoding="utf-8",
    )
    kb = OUT_GEOJSON.stat().st_size / 1024
    print(f"  wrote {OUT_GEOJSON}  ({len(out_features)} features, {kb:.0f} KB)")

    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {OUT_CSV}  ({len(rows)} rows)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/build_from_inrb.py <drc_health_zones.geojson>")
    main(sys.argv[1])
