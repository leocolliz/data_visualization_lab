# Where You Refuel — the geography of pump prices in North-East Italy

Data Visualization project. One question: **how much does *where* you refuel
change what you pay?** Scope: 22 Nord-Est provinces (ISTAT NUTS-1), 2024–2025,
one observation day per week (Monday).

## Result

Four gaps a driver faces, on the same scale (self-service petrol):

| Gap | cents/litre |
|---|---:|
| Attended vs self-service | 13.0 |
| Motorway vs ordinary road | 10.4 |
| Between pumps in the same province | 9.1 |
| Cheapest vs dearest province | 8.8 |

Geography matters least: which pump you pick inside your own province costs you
as much as living in the dearest province rather than the cheapest.

## Reproducing

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_panel.py   # 105 weekly CSVs -> panel + qc.json  (~95 s)
.venv/bin/python scripts/analyse.py       # the four geographic views
.venv/bin/python scripts/figures.py       # figures 01-08
.venv/bin/python scripts/wireframe.py     # figure 09
cd reports && pandoc deliverable1_proposal.md -o deliverable1_proposal.pdf \
    --pdf-engine=xelatex -V mainfont="DejaVu Serif" -V sansfont="DejaVu Sans" \
    -V monofont="DejaVu Sans Mono" -V fontsize=10pt   # same for deliverable2
```

Every threshold is a named constant in `scripts/config.py`; every excluded row
is counted into `data/processed/qc.json` rather than dropped silently.

## Layout

```
scripts/     config, fuel harmonisation, registry/geo, pipeline, figures
data/raw/    prices/ (105 weekly CSVs), registry/ (8 snapshots),
             provinces.geojson, quarterly .tar.gz archives (provenance)
data/interim/    station table, price panel  (regenerated)
data/processed/  aggregates + qc.json        (regenerated)
figures/     01-09  (regenerated)
reports/     deliverable 1 (proposal) and 2 (technical report), .md + .pdf
_archive_20260805/   earlier three-act version of this project, superseded
```

## Data

MIMIT *Osservaprezzi Carburanti* (IODL 2.0) — daily posted prices for every
Italian fuel station, plus the station registry, from
<https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-archivio-prezzi>.
Province boundaries from openpolis/geojson-italy (CC-BY).

Prices are *posted* and self-reported, not transaction prices, and are not
weighted by volume sold. See §7 of the technical report for the full limitations.
