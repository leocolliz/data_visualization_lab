# Where You Refuel - the geography of pump prices in North-East Italy

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

## Getting the data

`data/` is gitignored, so a fresh clone has the code and none of the inputs.
One command puts them back:

```bash
.venv/bin/python scripts/fetch_data.py    # ~1.3 GB down, ~430 MB kept
```

It writes exactly the layout `scripts/config.py` reads:

| | what | where |
|---|---|---|
| Prices | 105 daily CSVs, one Monday per week | `data/raw/prices/` |
| Registry | 8 station snapshots, the first Monday of each quarter | `data/raw/registry/` |
| Boundaries | province polygons | `data/raw/provinces.geojson` |

MIMIT distributes both prices and registry as quarterly tarballs of ~91 daily
files, and offers no per-day download for past dates, so a whole quarter has to
come down for the 13 Mondays that are kept. That is the gap between 1.3 GB
fetched and 430 MB kept; `--keep-archives` retains the tarballs instead of
discarding them.

The scope lives in `config.py`, not in the script: change `START`, `END` or
`SAMPLE_WEEKDAY` and it fetches whatever the new window needs. Re-running is
cheap - files already on disk are left alone, and an interrupted download
resumes rather than restarting - so after a dropped connection just run it
again. `--force` re-fetches regardless.

## Reproducing

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/fetch_data.py    # raw MIMIT extracts -> data/raw/
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

## The interactive app
If you did not run the commands in the **Reproducing** section:
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
Otherwise the following is enough.
```bash
.venv/bin/streamlit run app.py            # http://localhost:8501
```

The same four comparisons, behind controls: which fuel, which weeks, and a
province of your own. It re-implements no statistic - the charts are the
report's own builders in `scripts/figures.py`, fed aggregates from
`scripts/analyse.py` recomputed over the window you pick. At the full range they
reproduce `figures/01`–`08` exactly. If the app and the report ever disagree,
one of them is a bug.

Report figures are rendered at print resolution and shown at column width, so
clicking one opens it full-screen; click anywhere outside it, or press Back, to
return. The figure keeps its place in the page while the overlay is open.

Light theme only, and deliberately: the figures are rendered for a printed
report and their palette is validated against that one surface, so a dark UI
would put light-surface PNGs on a dark page rather than restyle them.

## Docker

```bash
docker compose run --rm pipeline python scripts/fetch_data.py   # first time only
docker compose up --build                 # the app on http://localhost:8501
docker compose run --rm pipeline          # rebuild panel, aggregates, figures
docker compose down
```

Both services are the same image; the pipeline one is behind a profile so
`up` starts the app alone. `data/` is deliberately not baked in - ~430 MB of raw
extracts, gitignored besides - so it is bind-mounted instead: read-only for the
app, read-write for the pipeline. Fetch and build the panel once and every
container sees it. `up` on a machine with no data starts cleanly and then stops
with a message naming what is missing, rather than failing on a parquet read.

The image runs as uid 1000, which is the first ordinary user on a typical Linux
host, so files the pipeline writes back into `data/` and `figures/` are owned by
you rather than by root. If your uid differs (`id -u`), set `user:` on the
service. `pyarrow` is held at 24.x because streamlit 1.61 excludes 25; the
parquet files read identically either way.

## Layout

```
app.py       the interactive app (Streamlit)
Dockerfile, docker-compose.yml, .dockerignore, .streamlit/
             container image, the two services, and the app's theme
scripts/     config, data download, fuel harmonisation, registry/geo,
             pipeline, figures
data/raw/    prices/ (105 weekly CSVs), registry/ (8 snapshots),
             provinces.geojson, quarterly .tar.gz archives if --keep-archives
data/interim/    station table, price panel  (regenerated)
data/processed/  aggregates + qc.json        (regenerated)
figures/     01-08 (figures.py), 09 wireframe (wireframe.py),
             10-11 screenshots of the running app, taken by hand
reports/     deliverables 1 (proposal), 2 (technical report) and
             4 (final report), .md + .pdf
```

## Data

MIMIT *Osservaprezzi Carburanti* (IODL 2.0) - daily posted prices for every
Italian fuel station, plus the station registry, from
<https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-archivio-prezzi>
(quarterly archives served from `opendatacarburanti.mise.gov.it`). Province
boundaries from openpolis/geojson-italy (CC-BY). `scripts/fetch_data.py` pulls
all three - see **Getting the data**.

Prices are *posted* and self-reported, not transaction prices, and are not
weighted by volume sold. See §7 of the technical report for the full limitations.
