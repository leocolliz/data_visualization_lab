"""Aggregates for the geographic question.

Four views, all built on the standard self-service grades so that ~5,300
stations remain comparable:

    province_deviation.csv   provincial mean vs the Nord-Est mean
    motorway_weekly.csv      motorway premium, week by week
    dispersion.csv           within-province spread between neighbouring pumps
    service_gap.csv          attended vs self-service, same station same week

Two rules are applied throughout, because both guard against composition
effects that would otherwise masquerade as geography:

1.  Statistics are computed *within a week* and then averaged across weeks.
    Averaging raw prices over two years would let a province that reports more
    often during expensive weeks look expensive.
2.  Paired comparisons (service gap) are made *within a station*, so the gap
    is a service premium rather than a difference in which stations offer what.
"""

import pandas as pd

import config
import fuels

CENTS = 100.0


def _concat(frames, columns):
    """Concatenate per-product results, tolerating a window that yields none.

    The app calls these functions on arbitrary date slices, where a product can
    legitimately have no comparable rows. An empty frame with the right columns
    keeps the caller's column access working.
    """
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)


def load_panel():
    panel = pd.read_parquet(config.INTERIM / "panel_ne.parquet")
    # Every view below is per-litre and geographic, so drop the handful of
    # stations whose coordinates cannot place them.
    return panel[panel["geo_ok"]]


def province_deviation(panel):
    """Provincial mean price, and its deviation from the Nord-Est mean.

    Weekly province means first, then averaged, so provinces are weighted
    equally across time rather than by how often they reported.
    """
    out = []
    for product in fuels.HEADLINE:
        d = panel[(panel["product"] == product) & panel["self"]]
        weekly = d.groupby(["date", "Provincia"], observed=True)["prezzo"].mean()
        ne_week = d.groupby("date", observed=True)["prezzo"].mean()
        dev = (weekly - ne_week).groupby("Provincia").mean() * CENTS
        mean = weekly.groupby("Provincia").mean()
        out.append(pd.DataFrame({
            "product": product,
            "mean_eur": mean,
            "dev_cents": dev,
            "n_stations": d.groupby("Provincia")["idImpianto"].nunique(),
        }).reset_index())
    return pd.concat(out, ignore_index=True)


def motorway_weekly(panel):
    """Median motorway price minus median ordinary-road price, per week.

    Medians, not means: 105 motorway stations against 5,200 ordinary ones is
    an unbalanced comparison, and the median is the more stable summary of the
    smaller group.
    """
    out = []
    for product in fuels.HEADLINE:
        d = panel[(panel["product"] == product) & panel["self"]]
        g = (d.groupby(["date", "motorway"], observed=True)["prezzo"]
             .median().unstack("motorway"))
        if True not in g.columns or False not in g.columns:
            continue
        out.append(pd.DataFrame({
            "date": g.index,
            "product": product,
            "motorway": g[True].to_numpy(),
            "ordinary": g[False].to_numpy(),
            "premium_cents": (g[True] - g[False]).to_numpy() * CENTS,
        }))
    return _concat(out, ["date", "product", "motorway", "ordinary", "premium_cents"])


def dispersion(panel):
    """How much the same litre varies *between pumps inside one province*.

    For each province-week, the spread of station prices; then averaged over
    weeks. p90-p10 is reported alongside the IQR because the tails are the
    part a driver can actually act on: the cheapest pump in reach.

    The two percentiles are kept, not just their difference. A band drawn as
    `median +/- (p90-p10)/2` has the right *length* but the wrong endpoints
    whenever the distribution is skewed around its median, which station prices
    are: it comes out shifted by up to 1.8 cents. Averaging is linear, so
    `mean(p90) - mean(p10)` equals `mean(p90 - p10)` exactly and keeping the
    endpoints costs nothing in the width every other view reports.
    """
    out = []
    for product in fuels.HEADLINE:
        d = panel[(panel["product"] == product) & panel["self"]]
        # One price per station-week first: a station quoting twice in a week
        # must not count twice in its province's spread.
        sw = (d.groupby(["date", "Provincia", "idImpianto"], observed=True)["prezzo"]
              .mean().reset_index())
        g = sw.groupby(["date", "Provincia"], observed=True)["prezzo"]
        p10, p90 = g.quantile(0.10), g.quantile(0.90)
        wk = pd.DataFrame({
            "iqr": g.quantile(0.75) - g.quantile(0.25),
            "p10": p10,
            "p90": p90,
            "p90_p10": p90 - p10,
            "median": g.median(),
            "n": g.size(),
        }).reset_index()
        agg = wk.groupby("Provincia").agg(
            iqr_cents=("iqr", lambda s: s.mean() * CENTS),
            p90_p10_cents=("p90_p10", lambda s: s.mean() * CENTS),
            p10_eur=("p10", "mean"),
            p90_eur=("p90", "mean"),
            median_eur=("median", "mean"),
            n_stations=("n", "mean"),
        ).reset_index()
        agg["product"] = product
        out.append(agg)
    return pd.concat(out, ignore_index=True)


def service_pairs(panel, product):
    """Station-week pairs where one station posted both prices for `product`.

    One row per station-week, carrying the attended-minus-self gap. Returns
    None if the window holds only one of the two service types. This is the
    station-level distribution behind the headline figure; `service_gap`
    aggregates it by province.
    """
    d = panel[panel["product"] == product]
    sw = (d.groupby(["date", "Provincia", "idImpianto", "self"], observed=True)
          ["prezzo"].mean().unstack("self"))
    if True not in sw.columns or False not in sw.columns:
        return None
    paired = sw.dropna()
    paired = paired.assign(gap_cents=(paired[False] - paired[True]) * CENTS)
    return (paired.reset_index()[["date", "Provincia", "idImpianto", "gap_cents"]]
            .assign(product=product))


def service_gap(panel):
    """Attended-service premium, measured within the same station and week.

    Only stations that posted both a self and a served price for the same
    product in the same week contribute, so the gap cannot be an artefact of
    which stations offer attended service.
    """
    out = []
    for product in fuels.HEADLINE:
        pr = service_pairs(panel, product)
        if pr is None:
            continue
        agg = pr.groupby("Provincia").agg(
            gap_cents=("gap_cents", "mean"),
            gap_median=("gap_cents", "median"),
            n_pairs=("gap_cents", "size"),
            n_stations=("idImpianto", "nunique"),
        ).reset_index()
        agg["product"] = product
        out.append(agg)
    return _concat(out, ["Provincia", "gap_cents", "gap_median", "n_pairs",
                         "n_stations", "product"])


def main():
    panel = load_panel()
    print(f"panel: {len(panel):,} rows, {panel['idImpianto'].nunique():,} stations")

    dev = province_deviation(panel)
    mw = motorway_weekly(panel)
    disp = dispersion(panel)
    svc = service_gap(panel)

    dev.to_csv(config.PROCESSED / "province_deviation.csv", index=False)
    mw.to_csv(config.PROCESSED / "motorway_weekly.csv", index=False)
    disp.to_csv(config.PROCESSED / "dispersion.csv", index=False)
    svc.to_csv(config.PROCESSED / "service_gap.csv", index=False)

    # The station-level pair distribution, kept for the headline figure.
    for product in fuels.HEADLINE:
        pr = service_pairs(panel, product)
        if pr is not None:
            pr.to_parquet(config.INTERIM / f"service_pairs_{product}.parquet",
                          index=False)

    for product in fuels.HEADLINE:
        p = dev[dev["product"] == product].sort_values("dev_cents")
        m = mw[mw["product"] == product]["premium_cents"]
        s = svc[svc["product"] == product]
        d = disp[disp["product"] == product]
        print(f"\n--- {fuels.DISPLAY[product]} (self-service) ---")
        print(f"  cheapest {p.iloc[0]['Provincia']} {p.iloc[0]['mean_eur']:.3f}  "
              f"dearest {p.iloc[-1]['Provincia']} {p.iloc[-1]['mean_eur']:.3f}  "
              f"spread {p.iloc[-1]['mean_eur'] - p.iloc[0]['mean_eur']:.3f} EUR")
        print(f"  motorway premium: mean {m.mean():.1f}c  "
              f"min {m.min():.1f}c  max {m.max():.1f}c")
        print(f"  within-province IQR: {d['iqr_cents'].mean():.1f}c  "
              f"(p90-p10 {d['p90_p10_cents'].mean():.1f}c)")
        print(f"  attended premium: {s['gap_cents'].mean():.1f}c  "
              f"on {int(s['n_pairs'].sum()):,} station-weeks")


if __name__ == "__main__":
    main()
