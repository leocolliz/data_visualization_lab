"""Build the Nord-Est station-week price panel from the MIMIT weekly extracts.

Reads one price file per sampled week, joins the station registry, harmonises
fuel labels, applies documented quality filters, and writes:

    data/interim/stations_ne.parquet   one row per Nord-Est station
    data/interim/panel_ne.parquet      one row per station x week x fuel x service
    data/processed/qc.json             every exclusion, counted
    data/processed/qc_weekly.csv       per-week coverage

Every filter is counted rather than silently applied: the technical report
needs to state what was dropped and why.
"""

import json
from collections import Counter

import pandas as pd

import config
import fuels
import geo

PRICE_COLS = ["idImpianto", "descCarburante", "prezzo", "isSelf", "dtComu"]


def read_price_day(path, obs_date):
    """One daily extract, minimally typed. Malformed rows are counted."""
    raw = pd.read_csv(
        path,
        sep=";",
        skiprows=1,
        names=PRICE_COLS,
        header=0,
        encoding="latin-1",
        dtype=str,
        engine="python",
        on_bad_lines="skip",
    )
    df = pd.DataFrame({
        "idImpianto": pd.to_numeric(raw["idImpianto"], errors="coerce"),
        "label": raw["descCarburante"],
        "prezzo": pd.to_numeric(raw["prezzo"], errors="coerce"),
        "isSelf": pd.to_numeric(raw["isSelf"], errors="coerce"),
        "dtComu": pd.to_datetime(raw["dtComu"], format="%d/%m/%Y %H:%M:%S",
                                 errors="coerce"),
    })
    df["date"] = pd.Timestamp(obs_date)
    return df


def main():
    stations, reg_qc = geo.load_registry()
    ne_ids = set(stations["idImpianto"])
    print(f"registry: {len(stations)} Nord-Est stations "
          f"({stations['motorway'].sum()} motorway), "
          f"{reg_qc['repaired'].sum()} rows repaired, {reg_qc['unrecoverable'].sum()} unrecoverable")

    dates = list(config.sample_dates())
    missing = [d for d in dates if not config.price_file(d).exists()]
    present = [d for d in dates if config.price_file(d).exists()]
    print(f"weeks: {len(present)} present, {len(missing)} missing")

    ex = Counter()
    weekly, frames = [], []

    for d in present:
        raw = read_price_day(config.price_file(d), d)
        n_raw = len(raw)

        df = raw.dropna(subset=["idImpianto"])
        ex["bad_station_id"] += n_raw - len(df)
        df = df.copy()
        df["idImpianto"] = df["idImpianto"].astype("int64")

        n_nat = len(df)
        df = df[df["idImpianto"].isin(ne_ids)]
        n_ne = len(df)

        # --- documented exclusions, in order -----------------------------
        m = df["prezzo"].isna()
        ex["price_missing"] += int(m.sum())
        df = df[~m]

        m = ~df["prezzo"].between(config.PRICE_MIN, config.PRICE_MAX)
        ex["price_implausible"] += int(m.sum())
        df = df[~m]

        df = df.copy()
        df["product"] = df["label"].map(fuels.to_product)
        m = df["product"].isna()
        ex["fuel_unmapped"] += int(m.sum())
        if m.any():
            ex.update({f"unmapped::{v}": c
                       for v, c in df.loc[m, "label"].value_counts().items()})
        df = df[~m]

        m = df["product"].isin(fuels.PER_KG)
        ex["priced_per_kg"] += int(m.sum())
        df = df[~m]

        m = df["isSelf"].isna() | ~df["isSelf"].isin([0, 1])
        ex["service_unknown"] += int(m.sum())
        df = df[~m]

        # Age of the quote, in whole days. Compared date-to-date, not
        # timestamp-to-timestamp: the extract is taken at 08:00 and carries
        # quotes filed up to 08:15 that same morning, so a timestamp
        # comparison against midnight would score same-day quotes as -1.
        # Operators report changes, not reconfirmations, so age is a soft
        # signal: flagged at 60 days, dropped only past a year.
        df = df.copy()
        df["age_days"] = (df["date"].dt.normalize()
                          - df["dtComu"].dt.normalize()).dt.days
        m = df["age_days"] > config.STALE_DROP_DAYS
        ex["stale_over_1y"] += int(m.sum())
        df = df[~m]

        m = df["age_days"] < 0
        ex["quote_in_future"] += int(m.sum())
        df = df[~m]

        df["self"] = df["isSelf"].astype("int8").eq(1)
        keep = ["idImpianto", "date", "product", "self", "prezzo", "age_days"]
        frames.append(df[keep])

        weekly.append({
            "date": d,
            "rows_national": n_nat,
            "rows_ne": n_ne,
            "rows_kept": len(df),
            "stations_reporting": df["idImpianto"].nunique(),
            "median_age_days": float(df["age_days"].median()),
            "pct_flagged_stale": float(
                (df["age_days"] > config.STALE_FLAG_DAYS).mean() * 100),
        })

    panel = pd.concat(frames, ignore_index=True)
    panel = panel.merge(
        stations[["idImpianto", "Provincia", "regione", "motorway", "brand",
                  "geo_ok", "Comune"]],
        on="idImpianto", how="left",
    )

    weekly_df = pd.DataFrame(weekly)
    total_ne = int(weekly_df["rows_ne"].sum())
    qc = {
        "scope": {
            "regions": {r: len(p) for r, p in config.NE_REGIONS.items()},
            "n_provinces": len(config.NE_PROVINCES),
            "weeks_expected": len(dates),
            "weeks_present": len(present),
            "weeks_missing": [str(d) for d in missing],
            "week_first": str(present[0]),
            "week_last": str(present[-1]),
            "sample_weekday": "Monday",
        },
        "registry": {
            "snapshots": len(reg_qc),
            "rows_per_snapshot": reg_qc.to_dict("records"),
            "stations_ne": int(len(stations)),
            "motorway": int(stations["motorway"].sum()),
            "ordinary": int((~stations["motorway"]).sum()),
            "geo_unusable": int((~stations["geo_ok"]).sum()),
            "rebranded": int((stations["n_brands"] > 1).sum()),
            "by_region": stations["regione"].value_counts().to_dict(),
            "by_brand": stations["brand"].value_counts().to_dict(),
        },
        "panel": {
            "rows_ne_raw": total_ne,
            "rows_kept": int(len(panel)),
            "pct_kept": round(100 * len(panel) / total_ne, 3),
            "products": panel["product"].value_counts().to_dict(),
            "age_median": float(panel["age_days"].median()),
            "age_p95": float(panel["age_days"].quantile(0.95)),
            "age_max": int(panel["age_days"].max()),
            "pct_flagged_stale": round(
                float((panel["age_days"] > config.STALE_FLAG_DAYS).mean() * 100), 3),
        },
        "exclusions": {
            k: {"n": v, "pct_of_ne": round(100 * v / total_ne, 4)}
            for k, v in sorted(ex.items()) if not k.startswith("unmapped::")
        },
        "unmapped_labels": {k.split("::", 1)[1]: v
                            for k, v in ex.items() if k.startswith("unmapped::")},
        "fuel_labels_seen": len(fuels.LABEL_TO_PRODUCT),
    }

    stations.to_parquet(config.INTERIM / "stations_ne.parquet", index=False)
    panel.to_parquet(config.INTERIM / "panel_ne.parquet", index=False)
    weekly_df.to_csv(config.PROCESSED / "qc_weekly.csv", index=False)
    with open(config.PROCESSED / "qc.json", "w") as fh:
        json.dump(qc, fh, indent=2, default=str)

    print(f"panel: {len(panel):,} rows kept of {total_ne:,} Nord-Est rows "
          f"({qc['panel']['pct_kept']}%)")
    print("exclusions:", {k: v["n"] for k, v in qc["exclusions"].items() if v["n"]})
    if qc["unmapped_labels"]:
        print("UNMAPPED LABELS:", qc["unmapped_labels"])


if __name__ == "__main__":
    main()
