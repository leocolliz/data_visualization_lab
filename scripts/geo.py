"""Station registry: parsing, geocode quality control, province boundaries."""

import json

import pandas as pd

import config

REG_COLS = ["idImpianto", "Gestore", "Bandiera", "TipoImpianto", "NomeImpianto",
            "Indirizzo", "Comune", "Provincia", "Latitudine", "Longitudine"]

# Brands with a national retail presence; everything else is collapsed so the
# legend stays readable. "Pompe bianche" (white pumps) are unbranded
# independents and are a category of real interest, not a residual.
_BRAND_MAP = {
    "eni": "Eni", "agip eni": "Eni", "agip": "Eni", "enimoov": "Eni",
    "ip": "IP", "api-ip": "IP", "api": "IP",
    "q8": "Q8", "kuwait": "Q8", "q8 easy": "Q8",
    "esso": "Esso", "tamoil": "Tamoil", "shell": "Shell",
    "pompe bianche": "Pompe bianche", "no logo": "Pompe bianche",
}


def _split_registry_line(line):
    """Split one registry row, tolerating separators inside free-text fields.

    The registry is semicolon-delimited, but ~0.1% of rows carry a stray ';'
    inside the station name or address. Those rows are recoverable rather than
    droppable: the id is always first and the coordinates always last, so the
    surplus can only have come from the two free-text fields in the middle.
    """
    f = line.rstrip("\n").split(";")
    if len(f) == len(REG_COLS):
        return f
    if len(f) > len(REG_COLS):
        # id, Gestore, Bandiera, Tipo | <free text absorbs the surplus> |
        # Comune, Provincia, Lat, Lon
        head, tail = f[:4], f[-4:]
        middle = f[4:-4]
        name, addr = middle[0], " ".join(middle[1:])
        return head + [name, addr] + tail
    return None


def load_registry():
    """Union of all registry snapshots, restricted to Nord-Est.

    Stations enter and leave the registry, and some are rebranded, so a single
    snapshot cannot resolve every id seen in the price files. We take the union
    across snapshots and keep the most recent record for each station.
    """
    frames, qc = [], []
    for path in config.registry_files():
        snap = path.stem.split("-")[-1]
        rows, unrecoverable, repaired = [], 0, 0
        with open(path, encoding="latin-1") as fh:
            fh.readline()  # "Estrazione del ..."
            fh.readline()  # header
            for line in fh:
                if not line.strip():
                    continue
                n_fields = line.count(";") + 1
                parsed = _split_registry_line(line)
                if parsed is None:
                    unrecoverable += 1
                else:
                    repaired += n_fields != len(REG_COLS)
                    rows.append(parsed)
        df = pd.DataFrame(rows, columns=REG_COLS)
        df["snapshot"] = pd.to_datetime(snap, format="%Y%m%d")
        qc.append({"snapshot": snap, "rows": len(df),
                   "repaired": repaired, "unrecoverable": unrecoverable})
        frames.append(df)

    reg = pd.concat(frames, ignore_index=True)
    reg["idImpianto"] = pd.to_numeric(reg["idImpianto"], errors="coerce")
    for c in ("Latitudine", "Longitudine"):
        reg[c] = pd.to_numeric(reg[c], errors="coerce")
    reg["Provincia"] = reg["Provincia"].str.strip().str.upper()

    reg = reg.dropna(subset=["idImpianto"])
    reg["idImpianto"] = reg["idImpianto"].astype("int64")

    ne = reg[reg["Provincia"].isin(config.NE_PROVINCES)].copy()
    ne["regione"] = ne["Provincia"].map(config.NE_PROVINCES)
    ne["motorway"] = ne["TipoImpianto"].str.strip().str.casefold().eq("autostradale")
    ne["brand"] = (
        ne["Bandiera"].fillna("").str.strip().str.casefold().map(_BRAND_MAP)
        .fillna("Altro")
    )

    # Geocode QC: flag coordinates that cannot be where the row claims to be.
    lon_min, lat_min, lon_max, lat_max = config.NE_BBOX
    ne["geo_ok"] = (
        ne["Latitudine"].between(lat_min, lat_max)
        & ne["Longitudine"].between(lon_min, lon_max)
        & ~(ne["Latitudine"].eq(0) | ne["Longitudine"].eq(0))
    )

    # Most recent snapshot wins; `n_snapshots` exposes station churn, and a
    # station whose brand changes across snapshots is a genuine rebranding.
    ne = ne.sort_values("snapshot")
    churn = ne.groupby("idImpianto").agg(
        n_snapshots=("snapshot", "nunique"),
        n_brands=("brand", "nunique"),
    )
    stations = ne.drop_duplicates("idImpianto", keep="last").set_index("idImpianto")
    stations = stations.join(churn)

    return stations.reset_index(), pd.DataFrame(qc)


def load_provinces():
    """Nord-Est province polygons, keyed by two-letter code.

    Returns {code: [ring, ...]} where each ring is a list of (lon, lat).
    Multipolygons are flattened to their constituent rings, which is all the
    matplotlib polygon renderer needs.
    """
    with open(config.RAW / "provinces.geojson", encoding="utf-8") as fh:
        gj = json.load(fh)

    out = {}
    for feat in gj["features"]:
        code = feat["properties"]["prov_acr"]
        if code not in config.NE_PROVINCES:
            continue
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        out[code] = [ring for poly in polys for ring in poly]
    return out
