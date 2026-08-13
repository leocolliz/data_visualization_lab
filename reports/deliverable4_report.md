---
title: "Where You Refuel"
subtitle: "Final report: the solution, and the process that produced it"
author: "Massimo Cherotti · Leonardo Collizzolli · Giovanni Divina"
date: "Data Visualization · Final report"
geometry: margin=2.3cm
fontsize: 10pt
linestretch: 1.03
colorlinks: true
urlcolor: "blue"
header-includes:
  - \usepackage{needspace}
  - \usepackage{float}
  - \floatplacement{figure}{H}
---

## 1. The finished solution

The project asks one question - **how much does *where* you refuel change what
you pay?** - of the MIMIT *Osservaprezzi Carburanti* archive, restricted to the
22 provinces of ISTAT NUTS-1 Nord-Est over 2024–2025, sampled one day per week.
The panel behind every number is 105 weekly extracts, **2,000,810 usable price
observations** across **5,329 registered stations**.

The answer is a single ranked comparison. "Where" turns out to operate at four
scales, and putting all four on one axis is the finding:

| Gap a driver faces | cents/litre | on a 50-litre tank |
|:---|---:|---:|
| Attended vs self-service | 13.0 | €6.50 |
| Motorway vs ordinary road | 10.4 | €5.22 |
| Between pumps in the same province | 9.1 | €4.57 |
| Cheapest vs dearest province | 8.8 | €4.39 |

**Geography matters least.** Which pump you pick inside your own province costs
about as much as living in the dearest province rather than the cheapest, and
the two choices a driver actually controls - motorway or not, attended or
self-service - each cost more than the entire geographic range.

The solution is delivered as two artefacts that share one codebase:

- **Eight static figures** (`figures/01`–`08`), rendered for print and used in
  the technical report;
- **an interactive application** (Streamlit) with six views, in which the same
  figures are recomputed live over a window, a fuel and a province chosen by the
  reader (Figure 1).

Underneath both sits the four-stage pipeline described in Deliverable 2:
registry parsing and geocode QC (`geo.py`), panel construction with a
machine-readable quality-control ledger (`build_panel.py`), the four geographic
views (`analyse.py`), and the figure builders (`figures.py`).

![The delivered application, opening view. The four gaps are stated before any
of them is explained.](../figures/10_app_overview.png){width=100%}

### 1.1 How the application is navigated

The layout is a fixed sidebar and a single content pane (Figure 1). Nothing is
hidden behind a menu: everything the reader can change is visible at all times
on the left, and everything the application can show is one click away.

**The sidebar has two parts.** *View* is a radio list of the six sections, which
is the only navigation in the piece - there is no scrolling between sections and
no drill-down. *Controls* holds the three inputs that apply everywhere:

- **Fuel** - petrol or diesel, the only two grades stocked at nearly every
  station and therefore the only two comparable across 5,000 pumps;
- **Weeks observed** - a double-ended slider over the 105 sampled Mondays, so
  any sub-period of the two years can be selected;
- **Your province** - one of the 22, which changes what is *highlighted and
  summarised* but never what the comparison is measured against.

On the *Data quality* section the three controls are disabled rather than
hidden, because that section describes the published dataset as a whole and
honouring a fuel or a week range there would be a fiction. A caption in the
sidebar says so, and the reader's selections are preserved for the other views.

Immediately under the title, every section prints the same status line - fuel,
weeks in the window, stations, posted prices - so whatever is on screen is
always labelled with the selection that produced it.

**Four of the six sections are built on the same three tabs**, which is the main
organising idea of the application: one comparison, three levels of commitment.

| Tab | What it holds |
|:-----------------|:----------------------------------------------------------------------------|
| **Report figure** | The exact figure from the technical report, recomputed over the chosen window. Click it to open full-screen; a button below exports the PNG. |
| **Explore** | A live, hoverable chart of the same quantity, plus two or three summary tiles. |
| **Table** | The numbers behind the figure, with a CSV export. |

The reader who wants the argument stops at the first tab; the reader who wants
to interrogate it moves right. The *Table* tab exists for a second reason: it is
the accessibility fallback for every figure, so no statement in the piece is
reachable only through colour.

The six sections themselves. The four middle ones - one per comparison - carry
the three tabs; the opening and closing sections are single pages, because
neither presents a comparison to interrogate:

| Section | Content |
|:------------------------|:-----------------------------------------------------------------------|
| **The four gaps** | Opening view, no tabs. Four tiles giving each gap in cents and in euros per 50-litre tank, the synthesis figure, then *"What this means in \<your province\>"* - mean price against the regional mean, spread between local pumps, local attended premium, stations reporting - and the gap table. |
| **Between provinces** | Choropleth of deviation from the Nord-Est mean paired with ranked bars; *Explore* gives horizontal bars coloured by sign, above or below the mean. |
| **Within one province** | The range plot of median and 10th–90th percentile per province; *Explore* opens the selected province's row into one dot per station (Figure 2), with tiles for pump count, typical spread and cheapest-to-dearest range. |
| **Motorway vs ordinary road** | Small multiples plus the weekly premium; *Explore* is a line chart of the premium over the 105 weeks for both fuels, with mean, narrowest and widest week. |
| **Attended vs self-service** | Dumbbell per province; *Explore* ranks provinces by premium with your own highlighted, and reports the share of station-weeks at zero - the bimodality discussed in §2.3. |
| **Data quality** | No tabs. Coverage, plausibility and label-harmonisation figures from Deliverable 2, four headline QC tiles, the exclusion ledger as a table, and the raw `qc.json` in an expander. |

Two conventions hold throughout. Every figure is clickable to full screen, since
a chart shown at column width is a chart with unreadable tick labels. Every
table and every figure can be exported, as CSV and PNG respectively, so a reader
can leave with the evidence rather than a screenshot of it.

### 1.2 The rule that holds the two artefacts together

The application does not re-implement a single statistic. Its charts *are* the
report's builders in `figures.py`, fed aggregates from `analyse.py` recomputed
over the chosen window instead of over the whole panel. At full range the app
reproduces `figures/01`–`08` exactly.

This was a deliberate constraint rather than a convenience. The most likely way
for a project like this to become quietly wrong is for an interactive layer to
grow its own copy of the analysis and drift from the written report. Making the
app call the report's own code means the two cannot disagree; if they ever do,
one of them is a bug rather than a matter of interpretation.

## 2. Is the final solution different from the proposal?

Yes - substantially in **form**, very little in **content**. The analytical
programme set out in Deliverable 1 survived contact with the data almost intact.
The way it is presented did not.

### 2.1 What survived unchanged

Every one of the four comparisons proposed in Deliverable 1 is in the final
solution, with the encodings proposed for them:

- the **diverging choropleth** of provincial deviation from the Nord-Est mean,
  paired with **ranked bars**;
- the **range plot** of within-province median and 10th–90th percentile;
- **small multiples** for the motorway premium, hue carrying the fuel and shade
  the road type, so that no panel ever needs four categorical slots;
- the **dumbbell** per province for attended versus self-service.

The two methodological rules also survived, and are enforced in code: statistics
are computed **within a week** and then averaged, and paired comparisons are made
**within a station**. Both guard against composition effects that would otherwise
be mistaken for geography. The ideas we explicitly rejected in the proposal - a
dual-axis chart, and a dot map of all 5,300 stations - stayed rejected.

Two commitments from §3.3 of the proposal that were kept: **ordering as encoding** (provinces are ranked by value,
never alphabetically) and **cents into money the reader spends** (every headline
gap is labelled twice, in cents and as the difference on a 50-litre refill, with
`TANK_LITRES` a named constant rather than a number typed into a caption).

### 2.2 What changed, and why

| Proposed (D1) | Delivered | Reason |
|:---|:---|:---|
| Scrollytelling piece on the web | Paged application, six views | Reading order could not be enforced; see below |
| Narrative building to the reversal | Answer stated first, then evidence | Consequence of the medium change |
| Click a province to cross-filter everything below | Province selection highlights only; baseline fixed at all 22 provinces | Cross-filtering silently changes the comparison |
| Filter row: fuel, service, road, date | Fuel and date only | Service and road *are* two of the four comparisons |
| — | Data quality promoted to a user-facing view | Quality assessment was too substantial to bury |
| — | Docker packaging and a data-fetch script | Reproducibility on a machine that is not ours |

**From scrollytelling to an application.** This is the largest departure. The
proposal argued for a scrolled narrative because the argument is sequential: the
reader has to believe the provincial map before it can be undercut. That
reasoning is still correct, and it is the change we are least comfortable with.

What defeated it was the combination of an argument that needs a fixed order and
a question that is personal. A scrollytelling piece controls order but resists
exploration; the moment a reader can choose their own province, their own fuel
and their own weeks, the author no longer controls what is on screen when. 

This choice implies a cost: **the reversal no longer lands as a
reversal.** In the proposal, "the spread inside your province is as wide as the
range across all of them" was a turn in an argument. In the application it is
the third row of a table on the opening screen. We recovered part of the effect
by making that opening screen state the conclusion in words - *"Geography
matters least"* - and by giving the within-province view its own page with the
station-level detail the proposal promised (Figure 2). But a reader who arrives
with the belief "my province is expensive" is now corrected rather than
persuaded, and those are not the same thing.

![The within-province view. Selecting a province opens its row into one dot per
station - the "station-level dot strip" the proposal
promised.](../figures/11_app_explore.png){width=100%}

**Cross-filtering, dropped on purpose.** The wireframe had clicking a province
on the map cross-filter every view beneath it. Building it revealed the flaw:
if selecting Bologna also restricts the comparison to Bologna, then the
deviation-from-the-mean encoding is measuring deviation from a mean of one
province, and the reader is shown a chart that answers a different question from
the one its legend claims. The final application separates the two roles - the
selected province changes what is *highlighted and summarised*, never what the
comparison is *against* - and says so in the sidebar. This is a case where
implementing the proposal faithfully would have produced a misleading product.

**Two filters removed.** The proposed filter row offered service and road type
as filters. But the attended premium and the motorway premium are two of the
four gaps being measured; a control that filters to self-service only would
delete one of the project's own findings. They are fixed comparisons in the
final solution, not user-adjustable dimensions.

**Data quality became a view.** Deliverable 2 produced a quality-control ledger
detailed enough that hiding it felt like a loss - 59 free-text fuel labels
mapped onto 9 products, 34 repaired registry rows, an exclusion table where
every filter is counted rather than silently applied. It is now a page of the
application, with the same figures the technical report uses and the raw
`qc.json` available underneath. Nothing about this was in the proposal; it exists
because the exploration turned out to be interesting in its own right.

### 2.3 What we did not deliver

Three items from the proposal are not in the final solution, and we would rather
name them than let them pass:

1. **The weekday robustness check.** Deliverable 1 promised to "check that the
   main patterns hold across different weekdays rather than assuming the sampled
   day is representative". We scoped, downloaded and sampled Mondays, but this
   check is not reported in Deliverable 2 and is not in the final solution. The
   design of the pipeline makes it cheap to run - `SAMPLE_WEEKDAY` is a single
   constant in `config.py` - which makes its absence a matter of sequencing
   rather than difficulty.
2. **Brand.** The registry's `Bandiera` field is parsed, harmonised onto a small
   set of national retail brands plus unbranded *pompe bianche*, and counted into
   the QC record - but it appears in no figure. It was carried as a possible fifth angle and
   never earned a view, because none of the four comparisons needed it.
3. **The cleaned panel as a download.** The wireframe promised a provenance
   layer offering the cleaned panel as CSV. Each view exports its own aggregate
   table, but the full panel is not downloadable from the application; source
   and licence appear in the footer, without an extraction date.

## 3. Difficulties encountered

### 3.1 Making a claim about two dispersions legible

Deliverable 1 predicted this would be the central design problem, and it was.
"The spread inside a province is as wide as the range across provinces" is a
comparison of two dispersions, aimed at a reader who is not assumed to know what
a percentile is. A box plot would encode it correctly and communicate nothing to
that reader.

Our solution was to stop asking the reader to compare two statistics, and let
them compare two *lengths* instead. No single chart does this; it takes three
steps across two figures.

1. **Turn the spread into a length.** In the range plot, each province is drawn
   as a bar running from its 10th to its 90th percentile. The length of that bar
   *is* the spread inside that province. A quantity that was a number in a table
   becomes a distance the eye can measure without being told how.
2. **Put both numbers on the chart in words.** The same figure is annotated with
   the two quantities being compared - the typical spread within a province
   (9.1 c/L) and the gap between the cheapest and dearest province (8.8 c/L) -
   so the reader never has to hold one value in memory while hunting for the
   other, or do the subtraction themselves.
3. **Draw them on one shared axis.** The synthesis figure (`figures/08`) places
   those two quantities side by side as two of its four bars, on a single scale.
   Here the comparison needs no statistical vocabulary at all: one bar is
   slightly longer than the other, and the reader can simply see which.

That synthesis figure is the one that ends up carrying the argument, and it was
not in the proposal. It only became possible once all four gaps had been
measured in the same unit and could share an axis - which is also why the
finished piece leads with it.

### 3.2 Unbalanced samples

101 motorway stations report against roughly 4,900 ordinary ones. Three
consequences had to be designed around rather than analysed away: a province ×
motorway breakdown is not supportable (under five stations per province, several
with none), so motorway is a Nord-Est-level comparison only; unbalanced
comparisons use medians, so that a handful of outlying sites cannot drive the
result; and per-province views expose their sample size, because a distribution
for Trieste rests on 40 pumps against Verona's 392 and drawing them identically
would imply equal confidence.

## 4. Conclusion

The project answers the question it set out to answer, with a result that is
mildly counter-intuitive and entirely supported by the data: of the four ways
"where you refuel" can change what you pay, the geographic one is the smallest.
The analysis survived from proposal to delivery essentially unchanged, which we
take as evidence that the feasibility work behind Deliverable 1 was honest. The
presentation changed a great deal, for one reason worth stating: an argument
that needs to be read in order and a question the reader wants to ask about
themselves pull in opposite directions, and we did not find a form that fully
serves both.
