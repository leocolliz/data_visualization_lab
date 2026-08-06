"""Shared configuration for the Nord-Est fuel price project.

Scope: the geography of pump prices in North-East Italy. One observation day
per week (Monday), 2024-2025, every station in the 22 NUTS-1 "Nord-Est"
provinces.
"""

from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PRICES = RAW / "prices"
REGISTRY = RAW / "registry"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"

for _d in (INTERIM, PROCESSED, FIGURES):
    _d.mkdir(parents=True, exist_ok=True)

# --- Temporal scope -------------------------------------------------------
# MIMIT publishes one file per day; we sample one weekday per week. Monday is
# arbitrary but fixed: the map question needs breadth of stations, not daily
# resolution, so weekly sampling costs nothing here.
START = date(2024, 1, 1)
END = date(2025, 12, 31)
SAMPLE_WEEKDAY = 0  # Monday

# --- Spatial scope --------------------------------------------------------
# ISTAT NUTS-1 "Nord-Est".
NE_REGIONS = {
    "Trentino-Alto Adige": ("BZ", "TN"),
    "Veneto": ("VR", "VI", "BL", "TV", "VE", "PD", "RO"),
    "Friuli-Venezia Giulia": ("UD", "GO", "TS", "PN"),
    "Emilia-Romagna": ("PC", "PR", "RE", "MO", "BO", "FE", "RA", "FC", "RN"),
}
NE_PROVINCES = {p: r for r, ps in NE_REGIONS.items() for p in ps}

# Bounding box for Nord-Est, used only to flag implausible geocodes.
NE_BBOX = (9.0, 43.6, 14.0, 47.2)  # lon_min, lat_min, lon_max, lat_max

# --- Data quality thresholds ---------------------------------------------
# Posted prices below/above these are treated as data entry errors, not prices.
# The live feed contains values like 0.100 and 8.888 that are plainly not
# per-litre prices for any fuel sold in Italy.
PRICE_MIN, PRICE_MAX = 0.5, 4.0

# Operators are required to report price *changes*, not to reconfirm unchanged
# prices, so an old timestamp is not by itself evidence of a stale record.
# We flag at 60 days and drop only at 365.
STALE_FLAG_DAYS = 60
STALE_DROP_DAYS = 365


def sample_dates(start=START, end=END, weekday=SAMPLE_WEEKDAY):
    """Every `weekday` between start and end inclusive."""
    d = start + timedelta(days=(weekday - start.weekday()) % 7)
    while d <= end:
        yield d
        d += timedelta(days=7)


def price_file(d):
    return PRICES / f"prezzo_alle_8-{d:%Y%m%d}.csv"


def registry_files():
    """Registry snapshots on disk, oldest first."""
    return sorted(REGISTRY.glob("anagrafica_impianti_attivi-*.csv"))
