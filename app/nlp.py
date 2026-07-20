"""Lightweight signal extraction from WHO Disease Outbreak News (DON) bulletins.

WHY RULE-BASED AND NOT A HUGGING FACE TRANSFORMER HERE:
Render's free web service has ~512 MB RAM. transformers + torch will not fit,
and would make cold starts painfully slow. So the *served* /briefing endpoint
uses a small, dependency-free extractor (regex + a zone gazetteer).

For the assessment's NLP requirement, run the heavy Hugging Face NER / zero-shot
pipeline in our notebook against the same DON text, and either (a) cache
its output to a JSON the API reads, or (b) deploy the model on a paid instance.
The interface below stays the same either way.
"""
from __future__ import annotations

import re
from pathlib import Path
from bs4 import BeautifulSoup

# DON_DIR = Path(__file__).resolve().parent.parent / "data" / "don"
DON_DIR = Path(__file__).resolve().parent.parent / "who_dons"  
SEVERITY_TERMS = [
    "public health emergency", "pheic", "cross-border", "no licensed vaccine",
    "no approved treatment", "healthcare worker", "nosocomial", "case fatality",
    "insecurity", "conflict", "displacement", "under-reporting",
]

BORDER_TERMS = ["rwanda", "uganda", "burundi", "goma", "rubavu", "gisenyi", "border"]


# def _latest_don() -> Path | None:
#     if not DON_DIR.exists():
#         return None
#     txts = sorted(DON_DIR.glob("*.txt"))
#     return txts[-1] if txts else None


def _latest_don() -> Path | None:
    if not DON_DIR.exists():
        return None

    htmls = sorted(DON_DIR.glob("*.html"))

    return htmls[-1] if htmls else None


def _first_int(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    return int(m.group(1).replace(",", "").replace(" ", ""))


def extract_briefing(known_zones: list[str]) -> dict:
    """Extract a structured briefing from the latest DON bulletin.

    `known_zones` is the health-zone gazetteer (pass in the zone names from the
    database) so we only report zones we can actually place on the map.
    """
    path = _latest_don()
    if path is None:
        return {
            "source": "none",
            "summary": "No DON bulletin found in data/don/. Add a .txt bulletin to enable the briefing.",
            "affected_zones": [],
            "severity_flags": [],
            "cross_border_mentions": [],
        }

    # text = path.read_text(encoding="utf-8", errors="ignore")
    html = path.read_text(encoding="utf-8", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")

    # Remove scripts and styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)

    low = text.lower()

    total_cases = _first_int(r"([\d,\s]+)\s+confirmed cases", text)
    total_deaths = _first_int(r"([\d,\s]+)\s+deaths", text)
    cfr = None

    if total_cases and total_deaths and total_cases > 0:
        cfr = round(100 * total_deaths / total_cases, 1)

    affected = sorted({z for z in known_zones if z.lower() in low})
    severity = sorted({t for t in SEVERITY_TERMS if t in low})
    borders = sorted({t for t in BORDER_TERMS if t in low})

    bits = []
    if total_cases is not None:
        bits.append(f"{total_cases:,} confirmed cases")
    if total_deaths is not None:
        bits.append(f"{total_deaths:,} deaths")
    if cfr is not None:
        bits.append(f"case-fatality ratio {cfr}%")
    head = "; ".join(bits) if bits else "counts not detected in text"
    zone_txt = (
        f" Zones named: {', '.join(affected[:8])}." if affected else ""
    )
    border_txt = (
        " Cross-border risk flagged." if borders else ""
    )
    summary = f"Latest bulletin ({path.stem}) reports {head}.{zone_txt}{border_txt}"

    return {
        "source": path.stem,
        "summary": summary,
        "total_cases": total_cases,
        "total_deaths": total_deaths,
        "case_fatality_ratio": cfr,
        "affected_zones": affected,
        "severity_flags": severity,
        "cross_border_mentions": borders,
    }
