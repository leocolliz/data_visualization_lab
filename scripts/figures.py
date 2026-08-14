"""Figures for the Nord-Est fuel price project.

Forms are chosen by the job the data does, and colour is assigned by that job
rather than by series index:

  04 choropleth   polarity (above/below the regional mean)  -> diverging
  05 motorway     identity (product) x road type            -> small multiples,
                                                                one hue, 2 shades
  06 dispersion   magnitude + spread, ranked                -> one hue
  07 service      before/after per province                 -> dumbbell, 1 hue 2 shades
  08 synthesis    magnitude, ranked                         -> one hue

01-03 are the exploratory/data-quality figures for the technical report.
"""

import json

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon

import config
import fuels
import geo
import style

style.apply()

PROD_COLOUR = {"benzina": style.C1, "gasolio": style.C2}
# Lighter step of each hue: hue carries the product, shade carries the road
# type, so no chart ever needs four categorical slots at once.
PROD_LIGHT = {"benzina": "#9ec5f4", "gasolio": "#f6bda6"}


def _load():
    """Everything the figures draw from, read once.

    Each `fig_*` below takes this dict and *returns* a figure; writing the PNG
    is `main`'s job. Keeping the two apart is what lets `app.py` hand the same
    functions a live recomputation over a user-chosen window and render the
    result to the screen instead of to disk.
    """
    return {
        "dev": pd.read_csv(config.PROCESSED / "province_deviation.csv"),
        "mw": pd.read_csv(config.PROCESSED / "motorway_weekly.csv",
                          parse_dates=["date"]),
        "disp": pd.read_csv(config.PROCESSED / "dispersion.csv"),
        "svc": pd.read_csv(config.PROCESSED / "service_gap.csv"),
        "qc": json.load(open(config.PROCESSED / "qc.json")),
        "qcw": pd.read_csv(config.PROCESSED / "qc_weekly.csv", parse_dates=["date"]),
        # The panel backs the two distribution figures; only these columns are
        # ever read, so the rest of it stays off the heap.
        "panel": pd.read_parquet(
            config.INTERIM / "panel_ne.parquet",
            columns=["product", "self", "motorway", "prezzo", "geo_ok", "age_days"]),
        "pairs": {p: pd.read_parquet(config.INTERIM / f"service_pairs_{p}.parquet")
                  for p in fuels.HEADLINE},
    }


def _date_axis(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))


# --------------------------------------------------------------------------
# Exploratory / data quality
# --------------------------------------------------------------------------

def fig_coverage(D):
    qcw = D["qcw"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    fig.subplots_adjust(wspace=0.28, top=0.80)

    ax = axes[0]
    ax.plot(qcw["date"], qcw["stations_reporting"], color=style.C1)
    ax.set_ylim(0, qcw["stations_reporting"].max() * 1.2)
    ax.set_ylabel("stations")
    _date_axis(ax)
    style.titles(ax, "Coverage is stable", "Stations posting at least one price")
    ax.annotate(f"{qcw['stations_reporting'].min():,}–"
                f"{qcw['stations_reporting'].max():,} of "
                f"{D['qc']['registry']['stations_ne']:,} registered",
                xy=(0.03, 0.10), xycoords="axes fraction",
                fontsize=9, color=style.INK_2)

    ax = axes[1]
    ax.plot(qcw["date"], qcw["median_age_days"], color=style.C1)
    ax.set_ylabel("days")
    ax.set_ylim(0, max(3, qcw["median_age_days"].max() * 1.35))
    _date_axis(ax)
    style.titles(ax, "Quotes stay fresh", "Median age of the posted price")

    style.source_note(fig)
    return fig


def fig_quality(D):
    panel = D["panel"]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 3.9))
    fig.subplots_adjust(wspace=0.30, top=0.78)

    ax = axes[0]
    d = panel.loc[panel["product"].isin(fuels.HEADLINE), "prezzo"]
    ax.hist(d, bins=140, range=(1.4, 2.4), color=style.C1, edgecolor="none")
    ax.set_xlim(1.4, 2.4)
    ax.set_xlabel("EUR / litre")
    ax.set_ylabel("posted prices")
    ex = D["qc"]["exclusions"]
    style.titles(ax, "Prices are plausible", "Standard petrol and diesel")
    ax.annotate(f"{ex['price_implausible']['n']} values outside "
                f"{config.PRICE_MIN}–{config.PRICE_MAX} EUR/L\nwere excluded "
                f"({ex['price_implausible']['pct_of_ne']:.3f}% of rows)",
                xy=(0.97, 0.94), xycoords="axes fraction", ha="right", va="top",
                fontsize=9, color=style.INK_2)

    ax = axes[1]
    ax.hist(panel["age_days"], bins=62, range=(0, 62), color=style.C1,
            edgecolor="none")
    ax.set_yscale("log")
    ax.set_xlim(0, 62)
    ax.set_xlabel("age of the quote, days")
    ax.set_ylabel("posted prices (log)")
    style.titles(ax, f"Nothing older than {D['qc']['panel']['age_max']} days",
                 f"Median {D['qc']['panel']['age_median']:.0f} d · "
                 f"99th pct 13 d · max {D['qc']['panel']['age_max']} d")
    ax.annotate("In 2024–2025 the archive holds no quote\n"
                "older than 61 days, and only 26 rows\n"
                "cross 60. The March 2022 extract reaches\n"
                "568 days and the live feed 4,823 — the\n"
                "retention behaviour changed over time.",
                xy=(0.97, 0.93), xycoords="axes fraction", ha="right", va="top",
                fontsize=8.5, color=style.INK_2)

    style.source_note(fig, "Operators must report price changes, not reconfirm "
                           "unchanged prices, so age alone is not staleness.")
    return fig


def fig_harmonisation(D):
    counts = {p: len(v) for p, v in fuels._GROUPS.items()}
    prods = D["qc"]["panel"]["products"]
    order = sorted(counts, key=lambda p: -counts[p])

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.0))
    fig.subplots_adjust(wspace=0.62, top=0.80)

    ax = axes[0]
    y = np.arange(len(order))
    vals = [counts[p] for p in order]
    ax.barh(y, vals, color=style.C1, height=0.66)
    ax.set_yticks(y, [fuels.DISPLAY[p] for p in order])
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.18)
    ax.set_xlabel("distinct commercial labels")
    ax.grid(axis="y", visible=False)
    style.titles(ax, "59 free-text labels, 9 products",
                 "Operators type their own fuel name")
    for i, v in enumerate(vals):
        ax.text(v + 0.35, i, str(v), va="center", fontsize=9, color=style.INK_2)

    ax = axes[1]
    shown = [p for p in order if p in prods]
    vals = [prods[p] / 1e3 for p in shown]
    ax.barh(np.arange(len(shown)), vals, color=style.C1, height=0.66)
    ax.set_yticks(np.arange(len(shown)), [fuels.DISPLAY[p] for p in shown])
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.12)
    ax.set_xlabel("thousands of posted prices retained")
    ax.grid(axis="y", visible=False)
    style.titles(ax, "Two products carry the comparison",
                 "Standard grades are sold almost everywhere")

    style.source_note(fig, "Methane, LNG and L-GNC are priced per kilogram and "
                           "are excluded from every EUR/litre view.")
    return fig


# --------------------------------------------------------------------------
# The geographic question
# --------------------------------------------------------------------------

def _ring_centroid(rings):
    """Centroid of the largest ring, used to place the province label."""
    a = np.asarray(max(rings, key=len), dtype=float)
    return a[:, 0].mean(), a[:, 1].mean()


def fig_choropleth(D, product="benzina"):
    dev = D["dev"][D["dev"]["product"] == product].set_index("Provincia")
    polys = geo.load_provinces()
    gap_c = (dev["mean_eur"].max() - dev["mean_eur"].min()) * 100

    fig = plt.figure(figsize=(11.5, 5.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1], wspace=0.05)
    axm, axb = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

    vmax = float(np.abs(dev["dev_cents"]).max())
    norm = plt.Normalize(-vmax, vmax)

    patches, colours = [], []
    for code, rings in polys.items():
        if code not in dev.index:
            continue
        c = style.DIVERGING(norm(dev.loc[code, "dev_cents"]))
        for ring in rings:
            patches.append(Polygon(np.asarray(ring, dtype=float), closed=True))
            colours.append(c)
    axm.add_collection(PatchCollection(
        patches, facecolor=colours, edgecolor=style.SURFACE, linewidth=0.9))

    for code, rings in polys.items():
        if code not in dev.index:
            continue
        x, y = _ring_centroid(rings)
        v = dev.loc[code, "dev_cents"]
        axm.text(x, y, code, ha="center", va="center", fontsize=7.5,
                 fontweight="bold",
                 color="#ffffff" if abs(v) > vmax * 0.55 else style.INK)

    axm.autoscale_view()
    axm.set_aspect(1 / np.cos(np.radians(45.5)))
    axm.axis("off")
    style.titles(axm, f"A {gap_c:.0f}-cent gap across Nord-Est",
                 f"Mean self-service {fuels.DISPLAY[product].lower()}, 2024-2025")

    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=style.DIVERGING),
                      ax=axm, orientation="horizontal", fraction=0.042, pad=0.02)
    cb.set_label("cents/litre vs the Nord-Est mean", color=style.INK_2, fontsize=9)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=style.MUTED, labelcolor=style.INK_2)

    s = dev.sort_values("mean_eur")
    y = np.arange(len(s))
    axb.barh(y, s["mean_eur"], height=0.66,
             color=[style.DIVERGING(norm(v)) for v in s["dev_cents"]])
    axb.set_yticks(y, s.index)
    axb.set_xlim(s["mean_eur"].min() - 0.05, s["mean_eur"].max() + 0.014)
    axb.set_xlabel("EUR / litre")
    axb.grid(axis="y", visible=False)
    style.titles(axb, "Ranked, cheapest first", "Provincial mean")
    for i, (_, row) in enumerate(s.iterrows()):
        if i in (0, len(s) - 1):
            axb.text(row["mean_eur"] + 0.0018, i, f"{row['mean_eur']:.3f}",
                     va="center", fontsize=9, color=style.INK_2)

    style.source_note(fig, "Friuli-Venezia Giulia operates a regional discount "
                           "for residents that posted prices do not reflect.")
    return fig


def fig_motorway(D):
    mw = D["mw"]
    panel = D["panel"]
    panel = panel[panel["geo_ok"] & panel["self"]]

    fig = plt.figure(figsize=(12.4, 4.2))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.5, 1, 1], wspace=0.30)
    axl = fig.add_subplot(gs[0])
    axp, axd = fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
    fig.subplots_adjust(top=0.78)

    for product in fuels.HEADLINE:
        d = mw[mw["product"] == product]
        axl.plot(d["date"], d["premium_cents"], color=PROD_COLOUR[product],
                 label=fuels.DISPLAY[product])
    axl.set_ylim(0, mw["premium_cents"].max() * 1.16)
    axl.set_ylabel("cents / litre")
    _date_axis(axl)
    axl.legend(loc="lower center", ncols=2)
    style.titles(axl, "The motorway premium never closes",
                 "Median motorway minus median ordinary-road price")
    for product in fuels.HEADLINE:
        d = mw[mw["product"] == product]
        axl.annotate(f"{fuels.DISPLAY[product]}  mean {d['premium_cents'].mean():.1f}c",
                     xy=(d["date"].iloc[len(d) // 2],
                         d["premium_cents"].iloc[len(d) // 2]),
                     xytext=(0, 26 if product == "gasolio" else -30),
                     textcoords="offset points", ha="center",
                     fontsize=9, color=style.INK_2)

    # Small multiples: one panel per product, so no panel ever carries more
    # than two series and hue never has to mean two things at once.
    bins = np.linspace(1.45, 2.30, 110)
    for ax, product in ((axp, "benzina"), (axd, "gasolio")):
        for is_mw, colour, lab in ((False, PROD_LIGHT[product], "ordinary road"),
                                   (True, PROD_COLOUR[product], "motorway")):
            v = panel.loc[(panel["product"] == product)
                          & (panel["motorway"] == is_mw), "prezzo"]
            ax.hist(v, bins=bins, density=True, histtype="step", lw=1.7,
                    color=colour, label=lab)
        ax.set_xlabel("EUR / litre")
        ax.set_yticks([])
        ax.set_xlim(1.45, 2.30)
        ax.legend(loc="upper right", fontsize=8.5)
        style.titles(ax, fuels.DISPLAY[product], "two separate populations")
    axp.set_ylabel("density")

    style.source_note(
        fig, f"{D['qc']['registry']['motorway']} motorway stations of "
             f"{D['qc']['registry']['stations_ne']:,}. "
             f"Spikes are round-number pricing.")
    return fig


def fig_dispersion(D, product="benzina"):
    disp = D["disp"][D["disp"]["product"] == product].set_index("Provincia")
    dev = D["dev"][D["dev"]["product"] == product].set_index("Provincia")
    disp = disp.join(dev["mean_eur"]).sort_values("median_eur")

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.2),
                             gridspec_kw={"width_ratios": [1.35, 1],
                                          "wspace": 0.24})
    fig.subplots_adjust(top=0.80)

    ax = axes[0]
    y = np.arange(len(disp))
    # The drawn percentiles, not median +/- half the spread: the two have the
    # same length, but the second is shifted wherever the distribution is
    # skewed around its median, and this panel is read off the axis.
    lo, hi = disp["p10_eur"], disp["p90_eur"]
    ax.hlines(y, lo, hi, color=style.SEQ[2], lw=5, alpha=0.6)
    ax.plot(disp["median_eur"], y, "o", color=style.SEQ[7], ms=6, zorder=3)
    ax.set_yticks(y, disp.index)
    ax.set_xlim(lo.min() - 0.012, hi.max() + 0.008)
    # Headroom above the top row so the comparison sits in clear space rather
    # than over the bands.
    ax.set_ylim(-0.7, len(disp) + 1.6)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("EUR / litre")
    style.titles(ax, "Inside one province, the same litre spans nine cents",
                 "Median and the 10th–90th percentile of station prices")

    # Compared on the same basis as every other figure: provincial means.
    between = (dev["mean_eur"].max() - dev["mean_eur"].min()) * 100
    within = disp["p90_p10_cents"].mean()
    ax.annotate(f"cheapest vs dearest province   {between:.1f}c        "
                f"typical spread within a province   {within:.1f}c",
                xy=(0.0, len(disp) + 1.0), xycoords=("axes fraction", "data"),
                va="center", fontsize=9.5, color=style.INK_2)

    ax = axes[1]
    order = disp.sort_values("p90_p10_cents")
    y = np.arange(len(order))
    ax.barh(y, order["p90_p10_cents"], height=0.66, color=style.SEQ[4])
    ax.set_yticks(y, order.index)
    ax.set_xlim(0, order["p90_p10_cents"].max() * 1.14)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("cents / litre")
    style.titles(ax, "Where the pumps disagree most",
                 "Mean weekly 10th–90th percentile spread")
    for i, v in enumerate(order["p90_p10_cents"]):
        if i in (0, len(order) - 1):
            ax.text(v + 0.15, i, f"{v:.1f}", va="center", fontsize=9,
                    color=style.INK_2)

    style.source_note(fig, "Spread computed within each week, then averaged, so "
                           "it is not inflated by prices moving over time.")
    return fig


def fig_service(D, product="benzina"):
    svc = D["svc"][D["svc"]["product"] == product].set_index("Provincia")
    dev = D["dev"][D["dev"]["product"] == product].set_index("Provincia")
    pairs = D["pairs"][product]
    gap = pairs["gap_cents"]
    zero_pct = float((gap.abs() < 0.5).mean() * 100)
    diff = gap[gap > 0.5]

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.2),
                             gridspec_kw={"width_ratios": [1.25, 1],
                                          "wspace": 0.26})
    fig.subplots_adjust(top=0.80)

    d = pd.DataFrame({"self": dev["mean_eur"], "gap": svc["gap_cents"] / 100})
    d["served"] = d["self"] + d["gap"]
    d = d.sort_values("gap")

    ax = axes[0]
    y = np.arange(len(d))
    ax.hlines(y, d["self"], d["served"], color=style.SEQ[2], lw=2.6, zorder=1)
    ax.plot(d["self"], y, "o", color=style.SEQ[3], ms=6.5, zorder=3)
    ax.plot(d["served"], y, "o", color=style.SEQ[7], ms=6.5, zorder=3)
    ax.set_yticks(y, d.index)
    ax.set_ylim(-2.2, len(d) - 0.4)
    ax.set_xlabel("EUR / litre")
    ax.grid(axis="y", visible=False)
    style.titles(ax, "Attended service costs more than geography",
                 "Self-service and attended price, same station, same week")
    ax.legend(handles=[
        plt.Line2D([], [], color=style.SEQ[3], marker="o", ls="", ms=6.5,
                   label="self-service"),
        plt.Line2D([], [], color=style.SEQ[7], marker="o", ls="", ms=6.5,
                   label="attended"),
    ], loc="lower right", ncols=2)

    ax = axes[1]
    counts, edges, _ = ax.hist(gap.clip(-2, 45), bins=95, color=style.SEQ[4],
                               edgecolor="none")
    ax.set_yscale("log")
    ax.set_xlabel("attended minus self-service, cents / litre")
    ax.set_ylabel("station-weeks (log)")
    style.titles(ax, "A third of stations charge nothing extra",
                 f"Mean {gap.mean():.1f}c over all pairs · "
                 f"{diff.mean():.1f}c where a differential exists")
    # Anchored to the measured height of the zero bin rather than a literal, so
    # the leader line still lands on the bar when the window is recomputed.
    zero_bin = max(int(np.searchsorted(edges, 0.0, side="right")) - 1, 0)
    peak = max(counts[zero_bin], 1.0)
    ax.annotate(f"{zero_pct:.0f}% of paired\nstation-weeks\nsit at zero",
                xy=((edges[zero_bin] + edges[zero_bin + 1]) / 2, peak),
                xytext=(9, peak * 0.53),
                fontsize=9, color=style.INK_2,
                arrowprops=dict(arrowstyle="-", color=style.MUTED, lw=0.9))

    style.source_note(
        fig, f"{len(pairs):,} paired station-weeks at "
             f"{pairs['idImpianto'].nunique():,} stations. Only stations posting "
             f"both prices for the same product in the same week contribute.")
    return fig


def fig_synthesis(D, product="benzina"):
    dev = D["dev"][D["dev"]["product"] == product]
    disp = D["disp"][D["disp"]["product"] == product]
    mw = D["mw"][D["mw"]["product"] == product]
    pairs = D["pairs"][product]

    items = [
        ("Cheapest vs dearest\nprovince",
         (dev["mean_eur"].max() - dev["mean_eur"].min()) * 100),
        ("Between pumps in the\nsame province",
         disp["p90_p10_cents"].mean()),
        ("Motorway vs\nordinary road", mw["premium_cents"].mean()),
        ("Attended vs\nself-service", pairs["gap_cents"].mean()),
    ]
    items.sort(key=lambda t: t[1])
    labels, vals = zip(*items)

    fig, ax = plt.subplots(figsize=(9.4, 4.1))
    fig.subplots_adjust(top=0.78, left=0.26)
    y = np.arange(len(vals))
    shades = [style.SEQ[2 + i * 2] for i in range(len(vals))]
    ax.barh(y, vals, height=0.6, color=shades)
    ax.set_yticks(y, labels)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("cents / litre")
    ax.set_xlim(0, max(vals) * 1.36)
    # Labelled twice, in cents and in money: the gap a reader can feel is the
    # one on the tank they actually buy, not the one per litre.
    for i, v in enumerate(vals):
        ax.text(v + 0.22, i, f"{v:.1f}c", va="center", fontsize=10,
                color=style.INK_2)
        ax.text(v + 2.15, i, f"€{v * config.TANK_LITRES / 100:.2f} a tank",
                va="center", fontsize=9.5, color=style.MUTED)
    style.titles(ax, "Which pump you choose matters more than which province "
                     "you are in",
                 f"Self-service {fuels.DISPLAY[product].lower()}, Nord-Est, "
                 f"2024-2025")

    style.source_note(fig, "Each bar is a different comparison on the same "
                           "scale: a range across provinces, a within-province "
                           "spread, and two paired premiums. Euro figures are "
                           f"the same gap on a {config.TANK_LITRES}-litre refill.")
    return fig


# Filename -> builder. The report renders each one at its default product;
# `app.py` walks the same table to offer diesel as well as petrol.
SHEET = [
    ("01_coverage.png", fig_coverage),
    ("02_quality.png", fig_quality),
    ("03_harmonisation.png", fig_harmonisation),
    ("04_choropleth.png", fig_choropleth),
    ("05_motorway.png", fig_motorway),
    ("06_dispersion.png", fig_dispersion),
    ("07_service.png", fig_service),
    ("08_synthesis.png", fig_synthesis),
]


def main():
    D = _load()
    for name, build in SHEET:
        style.save(build(D), name)


if __name__ == "__main__":
    main()
