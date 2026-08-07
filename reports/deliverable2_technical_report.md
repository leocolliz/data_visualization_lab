---
title: "Where You Refuel"
subtitle: "Dataset description, exploratory analysis and data quality assessment"
author: "Massimo Cherotti · Leonardo Collizzolli · Giovanni Divina"
date: "Data Visualization · Technical report"
geometry: margin=2.3cm
fontsize: 10pt
linestretch: 1.03
colorlinks: true
urlcolor: "blue"
header-includes:
  - \usepackage{needspace}
---

## 1. Scope and purpose

This report documents the data behind a single question - *how much does where
you refuel change what you pay?* - restricted to the 22 provinces of ISTAT
NUTS-1 **Nord-Est** (Trentino-Alto Adige, Veneto, Friuli-Venezia Giulia,
Emilia-Romagna) over **2024–2025**, sampled **one day per week (Monday)**.

The restriction is deliberate. The question is geographic, not dynamic, so daily
resolution buys nothing; and, as Section 5.3 shows, the 2024–2025 window is
internally consistent in a way the full 2015–2026 archive is not.

**Headline:** 105 weekly extracts yield **2,000,810 usable price observations**
(97.14% of the Nord-Est rows) across **5,329 registered stations**, with only
125 rows discarded for quality reasons. The dataset is in good condition; its
real difficulties are semantic (free-text fuel names, mixed units) rather than
structural.

Sections 2–5 describe the data and assess its quality. Section 6 reports what
exploration established about whether the data can carry the intended
visualization, and which of its properties constrain the design.

## 2. Sources and provenance

| Source | Content | Licence |
|---|---|---|
| MIMIT *Carburanti - archivio storico prezzi* | daily station prices, quarterly `.tar.gz`, 2015 Q1– | IODL 2.0 |
| MIMIT *Carburanti - anagrafica impianti attivi* | station registry with coordinates | IODL 2.0 |
| openpolis/geojson-italy | province boundaries (ISTAT-derived) | CC-BY |

Prices are reported to the Ministry by operators and each daily file is an extract of the prices valid at 08:00. Archive URLs follow
`opendatacarburanti.mise.gov.it/categorized/{dataset}/{year}/{year}_{q}_tr.tar.gz`.

## 3. Structure of the raw data

**Prices** (`prezzo_alle_8-YYYYMMDD.csv`) - line 1 is a free-text extraction
stamp, line 2 the header, delimiter `;`:

| Field | Type | Notes |
|---|---|---|
| `idImpianto` | int | joins to the registry |
| `descCarburante` | text | **free text**, see §5.4 |
| `prezzo` | float | EUR/litre, or EUR/kg for methane and LNG |
| `isSelf` | 0/1 | 1 = self-service, 0 = attended |
| `dtComu` | datetime | when the operator filed this price |

**Registry** (`anagrafica_impianti_attivi-YYYYMMDD.csv`) - same two-line
preamble, delimiter `;`, ten fields: `idImpianto`, `Gestore`, `Bandiera`,
`Tipo Impianto`, `Nome Impianto`, `Indirizzo`, `Comune`, `Provincia`,
`Latitudine`, `Longitudine`. `Tipo Impianto` takes two values, `Stradale` or
`Autostradale` - a controlled vocabulary the parser relies on (§5.5).

A national daily file holds ~93,000 price rows across ~24,000 stations. Even thought registry are published everyday with the prices file, since the number of stations is not often changing eight
registry snapshots were taken, one per quarter, growing from 22,821 to 24,462
national rows over the two years.

## 4. Construction of the analysis panel

The pipeline (`scripts/`, ~600 lines of Python) runs in five stages:

1. **`geo.load_registry`** - parse all eight snapshots, restrict to Nord-Est,
   derive region, motorway flag, harmonised brand, and a geocode validity flag;
   take the union across snapshots keeping the most recent record per station.
2. **`build_panel`** - read the 105 weekly price files, join the registry,
   harmonise fuel labels, apply the documented filters, and write the panel plus
   a machine-readable QC record (`data/processed/qc.json`).
3. **`analyse`** - compute the four geographic views.
4. **`figures`** - render the figures directly from the panel, so that no number
   in this report is transcribed by hand.

Two methodological rules are applied throughout, because both guard against
composition effects that would otherwise be mistaken for geography:

- Statistics are computed **within a week** and then averaged across weeks.
  Averaging raw prices over two years would let a province that happens to
  report more often during expensive weeks look expensive.
- Paired comparisons (the attended premium) are made **within a station**, so
  the gap cannot be an artefact of *which* stations offer attended service.

## 5. Data quality assessment

### 5.1 Coverage

All 105 expected Mondays are present; none is missing. Between 4,301 and 4,439
Nord-Est stations post at least one price in any given week, out of 5,329
registered. Over the whole period **5,018 stations report at least once**, so
**311 registered stations (5.8%) are never observed quoting a price** - they are
listed as active but silent. This is a real limitation: the "provincial mean" is
a mean over stations that report, not over stations that exist.

![Weekly coverage and the freshness of quotes.](../figures/01_coverage.png)

### 5.2 Price plausibility

Only **124 rows (0.006%)** fall outside a plausibility band of 0.5–4.0 EUR/litre
and are removed; one further row has an unparseable station id. Nothing is
missing: `prezzo` parses for every remaining row. The retained distribution is
well-behaved, with pronounced spikes at round numbers (1.700, 1.800, 1.900) that
are a genuine pricing behaviour rather than a defect.

For context, the *live* feed downloaded on 2026-08-06 carries nine such values,
among them 0.100 (four stations) and 8.888 (two) - placeholders rather than
prices. The band is set to catch exactly these without touching any real fuel
price.

![Price plausibility and the age of quotes.](../figures/02_quality.png)

### 5.3 Quote age - and a regime change in the archive

Operators are required to report price *changes*, not to reconfirm unchanged
prices, so an old `dtComu` is **not by itself evidence of a stale record**. We
therefore flag at 60 days and drop only beyond 365.

In the considered window the **drop** threshold never fires: no quote is anywhere near a year old, so not one row is removed for staleness. The **flag** does fire, but
barely - median quote age is **1 day**, the 99th percentile 13 days, and the
oldest quote in the panel is **61 days**, so **26 rows (0.001%)** cross the
60-day line. They are marked, not dropped.

That freshness is a property of *the considered window*, not of the dataset. The
same measurement on an extract from March 2022 gives a different picture; since
the two differ greatly in size, the last column gives the share as well as the
count:

\needspace{7\baselineskip}

| Extract | rows | median | 99th pct | max age | > 60 d |
|:---------------------|----------:|------:|--------:|-------:|-------------:|
| Archive, 2022-03-17 | 95,104 | 6 d | 453 d | 568 d | 6,201 (6.52%) |
| This panel, 2024–2025 | 2,000,810 | 1 d | 13 d | 61 d | 26 (0.001%) |

The first row is a single national day; the second is the whole panel, 105
Mondays of Nord-Est prices.

The two behave like different datasets. In 2022 a fifteenth of all quotes were
over two months old and the 99th percentile sat beyond a year, so staleness was
a genuine problem an analysis had to handle. By 2024 that tail has gone: the
same threshold catches 26 rows in two million. MIMIT's retention behaviour
changed somewhere between the two. **Any project spanning the full archive would
have to model that discontinuity;** scoping to 2024–2025 avoids it, and that is
part of why the window was chosen.

### 5.4 Fuel labels: the main semantic problem

`descCarburante` is free text. Across the study period it takes **59 distinct
values** (56 after case-folding) for what are really **nine products**. Diesel
alone appears under 20 commercial names - `Blue Diesel`, `Hi-Q Diesel`,
`Supreme Diesel`, `Excellium Diesel`, `Gasolio Oro Diesel`, and so on.

Harmonisation is an explicit lookup table (`fuels.py`), not a fuzzy rule, so an
unrecognised label surfaces as an error rather than being silently absorbed.
After harmonisation **zero rows are unmapped**.

Two decisions matter for the analysis:

- **Premium grades are kept separate from standard ones.** Pooling them would
  make a station that happens to sell Blue Diesel look expensive when it is
  simply selling a different product.
- **Winter-grade diesel** (`Gasolio artico`, `Gasolio Alpino`, …) is separated
  too: it is sold mainly in Alpine provinces and priced above standard diesel,
  so pooling it would bias precisely the provinces being compared.

**Mixed units.** Methane, LNG and L-GNC are priced **per kilogram**, not per
litre. These **58,784 rows (2.854%)** are excluded from every EUR/litre view.
This is the single largest exclusion in the pipeline, and it is a unit
incompatibility rather than a quality failure.

![Label harmonisation and the products that carry the comparison.](../figures/03_harmonisation.png)

### 5.5 Registry quality

- **Embedded separators.** 34 rows across the eight snapshots carry a stray `;`
  inside a free-text field, so they split into 11 or 12 pieces instead of 10.
  They are *recoverable* rather than droppable, because three positions in the
  row can be trusted: `idImpianto` is always first, the coordinates are always
  last, and `Tipo Impianto` is a two-value controlled vocabulary. We repair them
  rather than drop them; **zero rows are unrecoverable.** The surplus pieces are
  rejoined with `;`, the exact inverse of the split, so the repaired field is
  the ministry's original text rather than an approximation of it.
- **Geocoding.** Only **10 stations (0.19%)** have coordinates that fall outside
  a Nord-Est bounding box or sit at (0,0). They are excluded from spatial views.
- **Churn.** 4,267 of 5,329 stations appear in all eight snapshots; 225 appear in
  only one. Because a single snapshot cannot resolve every id, the registry is
  built as a union across snapshots - using only the latest snapshot would have
  silently dropped historical stations.

### 5.6 Exclusion ledger

| Filter | Rows | % of Nord-Est rows |
|---|---:|---:|
| Unparseable station id | 1 | 0.000 |
| Price missing | 0 | 0.000 |
| Price outside 0.5–4.0 EUR/L | 124 | 0.006 |
| Fuel label unmapped | 0 | 0.000 |
| Priced per kilogram (methane, LNG) | 58,784 | 2.854 |
| Service flag unknown | 0 | 0.000 |
| Quote older than 365 days | 0 | 0.000 |
| **Retained** | **2,000,810** | **97.14** |

### 5.7 Why the window stops at 2024–2025

The archive reaches back to 2015. Restricting to two years is partly a matter of
proportion - the question is geographic, so daily resolution over a decade adds
volume rather than evidence - but the decisive reasons are properties of the
older data, each checked against a 2022 file and archive held for comparison.

- **The retention regime changes (§5.3).** Maximum quote age is 61 days in
  2024–2025, 568 days in the March 2022 extract. Pooling the two would mix
  populations whose staleness differs by an order of magnitude.
- **The archive layout changes.** 2022 quarterly archives store the daily CSVs
  at the root; 2024–2025 archives nest them inside a `{year}_{q}_tr/` directory.
  A loader written against one silently extracts nothing from the other.
- **The fuel vocabulary is not stable.** The March 2022 file uses `SSP98`, a
  label that never appears in 2024–2025. Because harmonisation is a strict
  lookup that raises on anything unrecognised (§5.4), every extra year of
  history costs another pass of manual label triage - and an unnoticed one
  would silently drop a product from a station's price list.
- **Daily completeness is better.** 2022 Q1 is missing two consecutive days
  (15–16 March) out of 90. Across all of 2024–2025 exactly one day is absent
  from the archive, Saturday 2025-01-11 - and being a Saturday it does not touch
  the Monday sample, which is why all 105 expected weeks are present (§5.1).

None of this makes the earlier data unusable. It means a longer window is a
different project, with a discontinuity to model rather than a panel to
describe, and the two years chosen are the ones that behave consistently.

## 6. Exploratory analysis

Exploration had one job: establish whether this panel can carry the intended
visualization, and identify the properties that constrain how it must be built.
All results below use **standard self-service grades** unless stated otherwise.

### 6.1 Panel composition: how much data sits in each cell

Of 5,329 registered stations, **5,018 report at least once** and 5,008 of those
also carry usable coordinates. They divide unevenly:

| Region | Reporting stations | | Product | Rows retained |
|---|---:|---|---|---:|
| Veneto | 2,109 | | Petrol | 689,555 |
| Emilia-Romagna | 1,930 | | Diesel | 683,971 |
| Friuli-Venezia Giulia | 555 | | Diesel (premium) | 313,321 |
| Trentino-Alto Adige | 424 | | LPG | 121,196 |
| | | | Petrol (premium) | 102,031 |
| *of which motorway* | *101* | | HVO | 71,491 |
| | | | Diesel (winter grade) | 19,245 |

Per province the station count runs from **40 (Trieste)** and 53 (Gorizia) to
**392 (Verona)**, median 195. Standard petrol and diesel are the only two
products stocked at nearly every station, and therefore the only two comparable
across 5,000 pumps; the remainder are too unevenly distributed to map.

Three consequences for the design follow directly:

1. **A province × motorway breakdown is not supportable.** 101 motorway stations
   across 22 provinces is under five per province, and several provinces have
   none. Motorway can only be a Nord-Est-level comparison.
2. **Per-province views must expose their sample size.** A price distribution
   for Trieste rests on 40 pumps against Verona's 392; drawn identically, the
   two would imply equal confidence.
3. **Unbalanced comparisons need medians.** With 101 stations against ~4,900, a
   handful of outlying motorway sites would otherwise drive the result.

### 6.2 The intended comparisons are separable in this data

| Comparison | Gap | Measured over |
|:---------------------------|--------:|:------------------------------------------|
| Attended vs self-service | 13.0 c/L | 240,347 paired station-weeks, 2,785 stations |
| Motorway vs ordinary road | 10.4 c/L | 101 vs ~4,900 stations, weekly medians |
| Spread within a province-week | 9.1 c/L | p10–p90, 22 provinces × 105 weeks |
| Cheapest vs dearest province | 8.8 c/L | RO €1.745 to BZ €1.833 |

Each is large relative to week-to-week movement and stable across the two years
- the motorway premium, for instance, never falls below 7.8 cents in any of the
105 weeks, and the provincial ordering is coherent rather than noisy (Alpine and
border provinces dear, the Po plain cheap). Diesel behaves like petrol
throughout: an 11.6-cent motorway premium and a 9.8-cent provincial range. The
question is answerable with this data, and the answer does not depend on which
of the two headline fuels is chosen.

### 6.3 Two distributional properties the visualization must respect

Stations fall into two camps on attended service, so **the average describes almost none of them**. At **32% of paired station-weeks the two prices are identical** - those stations charge nothing extra for attended service. The rest charge **19.0 cents** more on average. The overall figure of 13.0 cents sits in the gap between the two groups and describes neither, so this comparison needs to be drawn as **a distribution rather than a single bar**.

**Within-province spread is as wide as the between-province range.** Inside a
single province in a single week, the 10th–90th percentile of station prices
spans **9.1 cents** on average, against **8.8 cents** between the cheapest and
dearest province. Bologna is the most dispersed (11.8c), Bolzano the least
(6.0c) - Bolzano is uniformly expensive, whereas Bologna contains both cheap and
dear pumps.

This is the most consequential thing the exploration turned up. A choropleth on
its own would leave a reader with "my province is expensive", when the data
supports "my province contains both the cheapest and the dearest pump I could
reach". **A map alone cannot carry this dataset**; a within-province view has to
sit beside it.

## 7. Limitations

1. **Posted, not transacted, and unweighted.** Prices are what operators
   advertise, not what drivers pay, and every station counts equally regardless
   of throughput. Provincial means are means over pumps, not over litres.
2. **Silent stations.** 311 registered stations never report; if silence
   correlates with price, provincial means are biased.
3. **Friuli-Venezia Giulia** operates a regional discount for residents that
   posted prices do not reflect, so UD, GO, TS and PN overstate what a resident
   actually pays.
4. **Weekly Monday sampling** is appropriate for a geographic question but
   would be inadequate for a dynamic one.
6. **The clean age profile does not generalise** beyond 2024–2025 (§5.3).

## 8. Reproducibility

```
scripts/config.py       scope, paths, thresholds
scripts/fuels.py        59 labels -> 9 products; per-kg products flagged
scripts/geo.py          registry parsing, repair, geocode QC, boundaries
scripts/build_panel.py  105 weekly files -> panel + qc.json
scripts/analyse.py      the four geographic views
scripts/figures.py      the figures in this report
```

Running `build_panel.py`, `analyse.py` and `figures.py` in that order
regenerates every number and figure in this report from the raw CSVs.
Every threshold is a named constant in `config.py`; every exclusion is counted
into `data/processed/qc.json` rather than applied silently. Environment: Python
3.12, pandas 3.0.5, matplotlib 3.11.1, numpy 2.5.1, pyarrow 25.0.0.
