"""Where You Refuel — the interactive companion to the report.

The report answers one question with eight fixed figures: how much does *where*
you refuel change what you pay? This app puts the same four comparisons behind
controls, so a reader can ask it for their own province, their own fuel, and
their own stretch of the two years.

Nothing here re-derives the analysis. The four views are the functions in
`scripts/analyse.py`, and the charts are the builders in `scripts/figures.py`,
called on a window the reader chooses instead of on the whole panel. If the app
and the report ever disagree, one of them is a bug.

How to run
----------
    pip install -r requirements.txt
    streamlit run app.py                 # needs data/ — see the README

or, without installing anything but Docker:

    docker compose up --build            # http://localhost:8501

Streamlit reruns this whole script top to bottom on every widget change, so the
expensive things are cached: the panel once per server process
(`st.cache_resource`, ~240 MB, never mutated) and each window's aggregates by
their date range (`st.cache_data`).
"""

from __future__ import annotations

import base64
import html
import io
import json
import struct
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # a container has no display; render straight to PNG

import altair as alt  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))  # the pipeline modules import each other flat

import analyse  # noqa: E402
import config  # noqa: E402
import figures  # noqa: E402
import fuels  # noqa: E402
import style  # noqa: E402

st.set_page_config(
    page_title="Where You Refuel",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# The full-screen figure overlay (see `zoomable`). Injected once per rerun,
# before anything that uses it. The overlay sits above Streamlit's own header,
# which is why the z-index is well clear of the 999990 the header uses.
ZOOM_CSS = """<style>
/* This block is delivered inside a markdown element, which would otherwise
   leave an empty element's worth of gap at the top of the page. A `<style>`
   still applies from inside a hidden parent. Matched by descendant rather than
   by an exact path: Streamlit's wrapper depth is not ours to depend on. */
.stMarkdown:has(style) { display: none; }
.zoomfig { width: 100%; }
.zoomfig-slot { position: relative; width: 100%; height: 100%; }
.zoomfig-slot img { display: block; width: 100%; height: 100%; object-fit: contain; }
.zoomfig-open { position: absolute; inset: 0; cursor: zoom-in; }
.zoomfig-open::after {
    content: "\\2921"; position: absolute; top: .45rem; right: .45rem;
    padding: .1rem .38rem; border-radius: 4px; line-height: 1.35;
    font-size: .95rem; color: #fcfcfb; background: rgba(32,35,42,.72);
    opacity: 0; transition: opacity .12s ease-in-out;
}
.zoomfig-slot:hover .zoomfig-open::after { opacity: 1; }
.zoomfig-shut { display: none; }

.zoomfig-slot:target {
    position: fixed; inset: 0; z-index: 1000001; padding: 2.2rem;
    background: rgba(18,20,24,.93);
    display: flex; align-items: center; justify-content: center;
}
.zoomfig-slot:target img {
    position: relative; z-index: 1; width: auto; height: auto;
    max-width: 100%; max-height: 100%; border-radius: 6px;
    box-shadow: 0 18px 60px rgba(0,0,0,.55);
}
.zoomfig-slot:target .zoomfig-open { display: none; }
/* Click anywhere off the figure to close; the glyph says so out loud. */
.zoomfig-slot:target .zoomfig-shut { display: block; position: fixed; inset: 0; cursor: zoom-out; }
.zoomfig-slot:target .zoomfig-shut::after {
    content: "\\2715"; position: fixed; top: .9rem; right: 1.4rem;
    font-size: 1.5rem; line-height: 1; color: #fcfcfb; opacity: .85;
}
@media (prefers-reduced-motion: reduce) {
    .zoomfig-open::after { transition: none; }
}
</style>"""

PAGES = [
    "The four gaps",
    "Between provinces",
    "Within one province",
    "Motorway vs ordinary road",
    "Attended vs self-service",
    "Data quality",
    "Method and downloads",
]

# Both hues are the report's, and the pair is the one validated in style.py:
# worst adjacent CVD ΔE 24.7 (protan) on this surface. The charts below never
# introduce a colour that has not been through the validator.
HOME_HUE = style.C2
REST_HUE = style.C1
BELOW_HUE = style.C1  # cheaper than the regional mean
ABOVE_HUE = "#e34948"  # dearer — the warm pole of style.DIVERGING

BAND_HUE = style.SEQ[2]  # the 10th–90th percentile band, as in figure 06
MEDIAN_HUE = style.SEQ[7]  # the provincial median, the dark step of one hue

SAMPLE_WEEKDAY_NAME = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                       "Saturday", "Sunday"][config.SAMPLE_WEEKDAY]


# -----------------------------------------------------------------------------
# Data availability
# -----------------------------------------------------------------------------

NEEDED = {
    config.INTERIM / "panel_ne.parquet": "the station-week price panel",
    config.PROCESSED / "qc.json": "the quality-control counts",
    config.PROCESSED / "qc_weekly.csv": "per-week coverage",
    config.RAW / "provinces.geojson": "province boundaries",
}


def stop_if_data_missing() -> None:
    """The repo ships code, not data: ~430 MB of MIMIT extracts are gitignored."""
    missing = {p: what for p, what in NEEDED.items() if not p.exists()}
    if not missing:
        return

    st.title("⛽ Where You Refuel")
    st.error("The app cannot start: the data directory is empty or incomplete.")
    st.markdown("Missing:")
    st.markdown("\n".join(f"- `{p.relative_to(ROOT)}` — {what}"
                          for p, what in missing.items()))
    st.markdown(
        "The raw MIMIT extracts are not in the repository. Download them, then "
        "build the panel — the first step is safe to repeat, it keeps whatever "
        "is already on disk:"
    )
    st.code(
        "python scripts/fetch_data.py    # raw extracts -> data/raw/ (~1.3 GB down)\n"
        "python scripts/build_panel.py   # 105 weekly CSVs -> panel + qc.json (~95 s)\n"
        "python scripts/analyse.py       # the four geographic views\n"
        "python scripts/figures.py       # figures 01-08",
        language="bash",
    )
    st.caption(
        "In Docker the same thing is `docker compose run --rm pipeline`. The app "
        "reads `data/` through a bind mount, so the panel is built once on the "
        "host and every container sees it."
    )
    st.stop()


# -----------------------------------------------------------------------------
# Loading and caching
# -----------------------------------------------------------------------------

@st.cache_resource(show_spinner="Reading the price panel…")
def get_panel() -> pd.DataFrame:
    """The whole panel, read once per server process.

    `cache_resource`, not `cache_data`: this frame is ~240 MB in memory and is
    never mutated, and `cache_data` would hand every rerun its own copy of it.
    Treat the returned object as read-only — it is shared across sessions.
    """
    return pd.read_parquet(config.INTERIM / "panel_ne.parquet")


@st.cache_data
def get_qc() -> dict:
    with open(config.PROCESSED / "qc.json") as fh:
        return json.load(fh)


@st.cache_data
def get_qc_weekly() -> pd.DataFrame:
    return pd.read_csv(config.PROCESSED / "qc_weekly.csv", parse_dates=["date"])


@st.cache_data
def get_weeks() -> list[date]:
    """The sampled Mondays actually present in the panel."""
    return [d.date() for d in pd.DatetimeIndex(get_panel()["date"].unique()).sort_values()]


def window(panel: pd.DataFrame, first: date, last: date) -> pd.DataFrame:
    """Rows inside [first, last]. The full range is returned without copying."""
    weeks = get_weeks()
    if (first, last) == (weeks[0], weeks[-1]):
        return panel
    return panel[panel["date"].between(pd.Timestamp(first), pd.Timestamp(last))]


@st.cache_data(show_spinner="Recomputing the four views over this window…")
def compute_views(first: date, last: date) -> dict:
    """`analyse.py`'s four aggregates, over one window.

    Cached on the date range alone: only these small results are stored, while
    the panel they came from stays in `cache_resource`.

    The geo filter reproduces `analyse.load_panel()` — every view here is
    per-litre and geographic, so stations whose coordinates cannot place them
    are dropped first.
    """
    panel = window(get_panel(), first, last)
    geo = panel[panel["geo_ok"]]

    pairs = {}
    for product in fuels.HEADLINE:
        pr = analyse.service_pairs(geo, product)
        pairs[product] = pr if pr is not None else pd.DataFrame(
            columns=["date", "Provincia", "idImpianto", "gap_cents", "product"])

    return {
        "dev": analyse.province_deviation(geo),
        "mw": analyse.motorway_weekly(geo),
        "disp": analyse.dispersion(geo),
        "svc": analyse.service_gap(geo),
        "pairs": pairs,
        "n_stations": int(geo["idImpianto"].nunique()),
        "n_rows": int(len(geo)),
    }


@st.cache_data(show_spinner="Reading the stations in this province…")
def station_prices(first: date, last: date, product: str, province: str) -> pd.DataFrame:
    """One row per station in `province`: the mean price it posted.

    These are the rows a province's spread is computed *from* — deliverable 1's
    "aggregated to province and revealed only on selection". Station-weeks are
    averaged first, exactly as `analyse.dispersion` does, so a station that
    quoted twice in one week does not count twice.
    """
    panel = window(get_panel(), first, last)
    d = panel[(panel["Provincia"] == province) & (panel["product"] == product)
              & panel["self"] & panel["geo_ok"]]
    if d.empty:
        return pd.DataFrame(columns=["idImpianto", "prezzo", "weeks", "Comune"])

    sw = d.groupby(["date", "idImpianto"], observed=True)["prezzo"].mean().reset_index()
    out = (sw.groupby("idImpianto")
           .agg(prezzo=("prezzo", "mean"), weeks=("prezzo", "size"))
           .reset_index())
    towns = d.drop_duplicates("idImpianto").set_index("idImpianto")["Comune"]
    out["Comune"] = out["idImpianto"].map(towns).str.title()
    return out


SUMMARY_LABEL = "province median and spread"


def dispersion_strip(disp: pd.DataFrame, stations: pd.DataFrame, home: str) -> int:
    """Every province as a median and spread; the chosen one opened into its pumps.

    Built in Altair rather than `st.bar_chart` because this needs two mark types
    on one pair of axes — a summary band per province, and the individual
    stations behind the selected one — and tooltips that round.

    Returns the number of pumps priced outside the drawn range: a handful of
    stations sit far above the rest, and letting them set the axis would squeeze
    all 22 provinces into a third of its width. They are clipped rather than
    dropped, and the caller says how many.
    """
    band = disp.assign(
        lo=disp["median_eur"] - disp["p90_p10_cents"] / 200,
        hi=disp["median_eur"] + disp["p90_p10_cents"] / 200,
        kind=SUMMARY_LABEL,
    ).sort_values("median_eur")
    order = band["Provincia"].tolist()

    lo, hi = float(band["lo"].min()), float(band["hi"].max())
    n_off = 0
    if not stations.empty:
        p_lo, p_hi = stations["prezzo"].quantile([0.02, 0.98])
        lo, hi = min(lo, float(p_lo)), max(hi, float(p_hi))
        n_off = int(((stations["prezzo"] < lo) | (stations["prezzo"] > hi)).sum())
    pad = (hi - lo) * 0.04
    scale = alt.Scale(domain=[lo - pad, hi + pad], zero=False, nice=False)

    def price_x(field: str) -> alt.X:
        return alt.X(f"{field}:Q", title="EUR / litre", scale=scale)

    y = alt.Y("Provincia:N", sort=order, title=None)
    legend = alt.Color(
        "kind:N",
        scale=alt.Scale(domain=[SUMMARY_LABEL, f"individual pumps in {home}"],
                        range=[MEDIAN_HUE, HOME_HUE]),
        legend=alt.Legend(title=None, orient="bottom", columns=1, labelLimit=320),
    )
    band_tip = [
        alt.Tooltip("Provincia:N", title="Province"),
        alt.Tooltip("median_eur:Q", title="Median", format=".3f"),
        alt.Tooltip("p90_p10_cents:Q", title="p90 − p10 (cents)", format=".1f"),
        alt.Tooltip("n_stations:Q", title="Stations/week", format=".0f"),
    ]

    layers = [
        alt.Chart(band).mark_rule(
            color=BAND_HUE, size=6, opacity=0.65, strokeCap="round", clip=True,
        ).encode(y=y, x=price_x("lo"), x2="hi:Q", tooltip=band_tip),
        alt.Chart(band).mark_point(filled=True, size=75, clip=True).encode(
            y=y, x=price_x("median_eur"), color=legend, tooltip=band_tip),
    ]

    if not stations.empty:
        pumps = stations.assign(kind=f"individual pumps in {home}", Provincia=home)
        layers.append(
            alt.Chart(pumps).mark_circle(size=42, opacity=0.5, clip=True).encode(
                y=y, x=price_x("prezzo"), color=legend,
                tooltip=[
                    alt.Tooltip("Comune:N", title="Town"),
                    alt.Tooltip("prezzo:Q", title="Mean price", format=".3f"),
                    alt.Tooltip("weeks:Q", title="Weeks posting", format=".0f"),
                ],
            )
        )

    st.altair_chart(alt.layer(*layers).properties(height=700))
    return n_off


def figure_data(views: dict, first: date, last: date, *, whole_panel: bool = False) -> dict:
    """The dict `scripts/figures.py` draws from, filled live rather than from disk.

    `figures._load()` builds the same shape by reading the published CSVs; here
    the aggregates come from the chosen window instead, which is what makes the
    report's own figures respond to the controls.
    """
    D = dict(views)  # shallow copy: never mutate what the cache handed back
    panel = get_panel()
    D["panel"] = panel if whole_panel else window(panel, first, last)
    D["qc"] = get_qc()
    D["qcw"] = get_qc_weekly()
    return D


# -----------------------------------------------------------------------------
# Small rendering helpers
# -----------------------------------------------------------------------------

def tank(cents_per_litre: float) -> str:
    """A gap in cents/litre, restated as money on one refill.

    Deliverable 1 commits to labelling every headline gap twice. A reader with
    no feel for "nine cents a litre" has a very clear feel for "€4.57 a tank".
    """
    return f"€{cents_per_litre * config.TANK_LITRES / 100:.2f}"


def png_bytes(fig: plt.Figure) -> bytes:
    """The figure as it would be written to figures/ — same surface, same dpi."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=style.SURFACE)
    return buf.getvalue()


def png_size(png: bytes) -> tuple[int, int]:
    """Pixel width and height, read from the PNG's IHDR chunk.

    Measuring the encoded file rather than trusting `fig.get_size_inches()`
    keeps the reserved slot correct even if a figure is ever saved with
    `bbox_inches="tight"`, which crops away part of the nominal canvas.
    """
    return struct.unpack(">II", png[16:24])


def zoomable(png: bytes, *, alt: str, slot: str) -> None:
    """A figure that opens full-screen when clicked.

    A chart drawn 700 px wide is a chart with unreadable tick labels, so every
    figure has to be openable at full size. This is the CSS `:target`
    idiom rather than a script: `st.markdown` strips `<script>`, and the usual
    way around that — a component iframe reaching into `window.parent` — breaks
    whenever Streamlit changes its DOM. Clicking the overlay link puts
    `#{slot}` in the address bar, `:target` matches, and the same `<img>` is
    restyled to fill the viewport. No second copy of the payload is sent, the
    browser Back button closes the overlay, and a rerun cannot desynchronise it
    because the state lives in the URL rather than in the session.

    The outer wrapper holds the figure's aspect ratio so that lifting the inner
    element out of flow (`position: fixed`) does not collapse the page behind
    the overlay and jump the scroll position.
    """
    w, h = png_size(png)
    src = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    alt = html.escape(alt, quote=True)
    st.markdown(
        f'<div class="zoomfig" style="aspect-ratio:{w}/{h}">'
        f'<div class="zoomfig-slot" id="{slot}">'
        f'<a class="zoomfig-shut" href="#zoomfig-closed" aria-label="Close"></a>'
        f'<img src="{src}" alt="{alt}">'
        f'<a class="zoomfig-open" href="#{slot}" aria-label="Enlarge: {alt}"></a>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def show(fig: plt.Figure, *, filename: str) -> None:
    """Draw a report figure and offer the PNG, then let it go.

    The PNG is encoded once and used twice, for the visible figure and for the
    download, which is why this renders the bytes itself instead of calling
    `st.pyplot` (that would draw the canvas a second time, and its own
    full-screen button only appears on hover).

    Closing matters: this process serves many reruns, and matplotlib keeps every
    unclosed figure alive.
    """
    png = png_bytes(fig)
    # The panels carry their own left-aligned titles, so the figure can describe
    # itself to a screen reader instead of repeating a caption in a second place.
    alt = " · ".join(t for ax in fig.axes if (t := ax.get_title(loc="left")))
    plt.close(fig)
    # The id has to survive a rerun unchanged or an open figure would snap shut,
    # and it has to be unique on the page or two figures would open together.
    # The filename is already both: it names one figure of one fuel.
    zoomable(png, alt=alt or filename,
             slot="zoomfig-" + filename.removesuffix(".png").replace("_", "-"))
    st.download_button("Download this figure (PNG)", png,
                       file_name=filename, mime="image/png", key=f"png::{filename}")


def table(df: pd.DataFrame, *, filename: str, column_config: dict | None = None) -> None:
    """A table view of whatever the chart above just showed, plus the CSV."""
    st.dataframe(df, hide_index=True, column_config=column_config)
    st.download_button("Download this table (CSV)",
                       df.to_csv(index=False).encode("utf-8"),
                       file_name=filename, mime="text/csv", key=f"csv::{filename}")


def split_home(df: pd.DataFrame, value_col: str, home: str) -> pd.DataFrame:
    """Split one value column in two so the reader's province gets its own hue.

    Streamlit's native charts colour by column, so a highlight is a second
    column rather than a per-bar colour — which keeps identity on the validated
    two-slot pair instead of inventing a hue per province.
    """
    is_home = df["Provincia"] == home
    return pd.DataFrame({
        "Provincia": df["Provincia"],
        "the rest of Nord-Est": df[value_col].where(~is_home),
        home: df[value_col].where(is_home),
    })


def ranked_bar(df: pd.DataFrame, value_col: str, home: str, *, value_label: str) -> None:
    """Provinces ranked by one measure, the reader's province picked out.

    `x_label`/`y_label` name the *data* channels, not the drawn axes, so under
    `horizontal=True` the measure is labelled with `y_label` even though it is
    the axis running across the page.
    """
    # Round before drawing: the native charts build their hover tooltip straight
    # from the frame, so an unrounded mean arrives as 15.219812646370023. One
    # decimal is the precision every other number in the app is shown at, and at
    # 0.1 c/L the bar length is unchanged to the pixel.
    ranked = df.sort_values(value_col)
    ranked = ranked.assign(**{value_col: ranked[value_col].round(1)})
    st.bar_chart(
        split_home(ranked, value_col, home),
        x="Provincia",
        y=["the rest of Nord-Est", home],
        color=[REST_HUE, HOME_HUE],
        horizontal=True,
        stack=False,
        sort=False,  # the frame is already in rank order
        x_label="",
        y_label=value_label,
        # Two y-columns split each province's row band in two, so the drawn bar
        # gets half of it. 700px over 22 provinces keeps the marks thin without
        # letting them thin out to hairlines.
        height=700,
    )


def for_product(views: dict, key: str, product: str) -> pd.DataFrame:
    return views[key][views[key]["product"] == product]


def four_gaps(views: dict, product: str) -> pd.DataFrame:
    """The report's headline table: four different comparisons, one scale."""
    dev = for_product(views, "dev", product)
    disp = for_product(views, "disp", product)
    mw = for_product(views, "mw", product)
    pairs = views["pairs"][product]
    rows = [
        ("Attended vs self-service", pairs["gap_cents"].mean()),
        ("Motorway vs ordinary road", mw["premium_cents"].mean()),
        ("Between pumps in the same province", disp["p90_p10_cents"].mean()),
        ("Cheapest vs dearest province",
         (dev["mean_eur"].max() - dev["mean_eur"].min()) * 100),
    ]
    out = (pd.DataFrame(rows, columns=["Gap", "cents/litre"])
           .sort_values("cents/litre", ascending=False, ignore_index=True))
    # Labelled twice, per deliverable 1: cents, and money on one refill.
    out["euros_per_tank"] = out["cents/litre"] * config.TANK_LITRES / 100
    return out


# -----------------------------------------------------------------------------
# Sidebar: navigation and the controls every page shares
# -----------------------------------------------------------------------------

stop_if_data_missing()

st.markdown(ZOOM_CSS, unsafe_allow_html=True)

st.sidebar.title("⛽ Where you refuel")
st.sidebar.caption("The geography of pump prices in North-East Italy, 2024–2025.")

page = st.sidebar.radio("View", PAGES, key="page")

st.sidebar.divider()
st.sidebar.subheader("Controls")

# Every widget carries an explicit key, so its value survives reruns and page
# switches in st.session_state under a name we chose rather than a generated one.
product = st.sidebar.radio(
    "Fuel", fuels.HEADLINE,
    format_func=lambda p: fuels.DISPLAY[p], horizontal=True, key="product",
)

weeks = get_weeks()
# The label must be unique per option: Streamlit round-trips a select_slider's
# value through its formatted label, so a month-only format ("Jan 2024") would
# resolve every Monday in that month to the last one and silently move the
# window on the first interaction.
first, last = st.sidebar.select_slider(
    "Weeks observed", options=weeks, value=(weeks[0], weeks[-1]),
    format_func=lambda d: d.strftime("%d %b %Y"), key="window",
)

PROVINCES = sorted(config.NE_PROVINCES)
home = st.sidebar.selectbox(
    "Your province", PROVINCES, index=PROVINCES.index("BO"),
    format_func=lambda p: f"{p} · {config.NE_PROVINCES[p]}", key="home",
)

st.sidebar.caption(
    "The Nord-Est baseline always uses all 22 provinces: your province changes "
    "what is highlighted and summarised, never what the comparison is against."
)

views = compute_views(first, last)
n_weeks = sum(1 for w in weeks if first <= w <= last)
D = figure_data(views, first, last)

st.title("Where You Refuel")
st.caption(
    f"{fuels.DISPLAY[product]}, self-service · {n_weeks} of {len(weeks)} weeks "
    f"({first:%d %b %Y} – {last:%d %b %Y}) · {views['n_stations']:,} stations · "
    f"{views['n_rows']:,} posted prices"
)

if page != "Data quality" and for_product(views, "dev", product).empty:
    st.warning("No comparable prices for this fuel in this window. Widen the week range.")
    st.stop()


# -----------------------------------------------------------------------------
# 1. The four gaps
# -----------------------------------------------------------------------------

if page == "The four gaps":
    st.markdown(
        "**How much does *where* you refuel change what you pay?** Four gaps a "
        "driver faces, all on the same scale. Geography matters least: which "
        "pump you pick inside your own province costs you about as much as "
        "living in the dearest province rather than the cheapest."
    )

    gaps = four_gaps(views, product)
    for col, (_, row) in zip(st.columns(4), gaps.iterrows()):
        col.metric(row["Gap"], f"{row['cents/litre']:.1f} c/L", border=True)
        col.caption(f"{tank(row['cents/litre'])} on a {config.TANK_LITRES}-litre tank")

    show(figures.fig_synthesis(D, product), filename=f"08_synthesis_{product}.png")

    st.divider()
    st.subheader(f"What this means in {home} · {config.NE_PROVINCES[home]}")

    dev = for_product(views, "dev", product).set_index("Provincia")
    disp = for_product(views, "disp", product).set_index("Provincia")
    svc = for_product(views, "svc", product).set_index("Provincia")

    if home not in dev.index:
        st.info(f"No {fuels.DISPLAY[product].lower()} prices in {home} in this window.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        # delta_color="inverse" throughout: on a price, below the average is the
        # good direction, and the default green-is-up would say the opposite.
        c1.metric(
            "Mean price", f"€{dev.loc[home, 'mean_eur']:.3f}/L",
            delta=f"{dev.loc[home, 'dev_cents']:+.1f} c vs Nord-Est",
            delta_color="inverse", border=True,
        )
        spread = disp.loc[home, "p90_p10_cents"]
        c2.metric(
            "Spread between pumps here", f"{spread:.1f} c/L",
            delta=f"{spread - disp['p90_p10_cents'].mean():+.1f} c vs average province",
            delta_color="inverse", border=True,
            help="Mean weekly 10th–90th percentile spread of station prices.",
        )
        gap = svc.loc[home, "gap_cents"]
        c3.metric(
            "Attended premium here", f"{gap:.1f} c/L",
            delta=f"{gap - svc['gap_cents'].mean():+.1f} c vs average province",
            delta_color="inverse", border=True,
        )
        c4.metric("Stations reporting", f"{int(dev.loc[home, 'n_stations']):,}",
                  border=True)

        move = (dev.loc[home, "mean_eur"] - dev["mean_eur"].min()) * 100
        st.caption(
            f"Choosing well inside {home} is worth about {spread:.1f} c/L — "
            f"{tank(spread)} on a {config.TANK_LITRES}-litre tank; moving to the "
            f"cheapest province in Nord-Est would be worth {move:.1f} c/L "
            f"({tank(move)})."
        )

    st.divider()
    table(
        gaps, filename=f"four_gaps_{product}.csv",
        column_config={
            "cents/litre": st.column_config.NumberColumn("cents/litre", format="%.1f c"),
            "euros_per_tank": st.column_config.NumberColumn(
                f"on a {config.TANK_LITRES}-litre tank", format="€ %.2f"),
        },
    )


# -----------------------------------------------------------------------------
# 2. Between provinces
# -----------------------------------------------------------------------------

elif page == "Between provinces":
    st.markdown(
        "The provincial mean, and how far it sits from the Nord-Est mean. Weekly "
        "province means are computed first and then averaged, so a province that "
        "reports more often during expensive weeks cannot look expensive."
    )

    tab_fig, tab_explore, tab_data = st.tabs(["Report figure", "Explore", "Table"])
    dev = for_product(views, "dev", product)

    with tab_fig:
        show(figures.fig_choropleth(D, product), filename=f"04_choropleth_{product}.png")

    with tab_explore:
        e = dev.sort_values("dev_cents")
        rounded = e["dev_cents"].round(1)  # tooltip precision — see ranked_bar
        st.bar_chart(
            pd.DataFrame({
                "Provincia": e["Provincia"],
                "below the Nord-Est mean": rounded.where(e["dev_cents"] <= 0),
                "above the Nord-Est mean": rounded.where(e["dev_cents"] > 0),
            }),
            x="Provincia",
            y=["below the Nord-Est mean", "above the Nord-Est mean"],
            color=[BELOW_HUE, ABOVE_HUE],
            horizontal=True, stack=False, sort=False,
            x_label="", y_label="cents/litre vs the Nord-Est mean", height=700,
        )
        st.caption(
            "Friuli-Venezia Giulia (GO, PN, TS, UD) operates a regional discount "
            "for residents that posted prices do not reflect."
        )

    with tab_data:
        table(
            dev.sort_values("mean_eur")[["Provincia", "mean_eur", "dev_cents", "n_stations"]],
            filename=f"province_deviation_{product}.csv",
            column_config={
                "mean_eur": st.column_config.NumberColumn("Mean price", format="€ %.3f"),
                "dev_cents": st.column_config.NumberColumn("vs Nord-Est", format="%+.1f c"),
                "n_stations": st.column_config.NumberColumn("Stations", format="%d"),
            },
        )


# -----------------------------------------------------------------------------
# 3. Within one province
# -----------------------------------------------------------------------------

elif page == "Within one province":
    st.markdown(
        "How much the same litre varies **between pumps inside one province**. "
        "The spread is computed within each week and then averaged, so it is not "
        "inflated by prices moving over the two years."
    )

    tab_fig, tab_explore, tab_data = st.tabs(["Report figure", "Explore", "Table"])
    disp = for_product(views, "disp", product)

    with tab_fig:
        show(figures.fig_dispersion(D, product), filename=f"06_dispersion_{product}.png")

    with tab_explore:
        pumps = station_prices(first, last, product, home)
        n_off = dispersion_strip(disp, pumps, home)

        if pumps.empty:
            st.info(f"No {fuels.DISPLAY[product].lower()} prices in {home} in this window.")
        else:
            home_row = disp[disp["Provincia"] == home]
            spread_home = float(home_row["p90_p10_cents"].iloc[0]) if not home_row.empty else float("nan")
            full = float((pumps["prezzo"].max() - pumps["prezzo"].min()) * 100)
            a, b, c = st.columns(3)
            a.metric(f"Pumps in {home}", f"{len(pumps):,}", border=True)
            b.metric("Typical spread here", f"{spread_home:.1f} c/L", border=True,
                     help="Mean weekly 10th–90th percentile — the measure the bands "
                          "draw and the one the headline gap uses.")
            b.caption(f"{tank(spread_home)} on a {config.TANK_LITRES}-litre tank")
            c.metric("Cheapest to dearest pump", f"{full:.1f} c/L", border=True,
                     help="The full range of station mean prices over this window, "
                          "tails included.")
            c.caption(f"{tank(full)} on a {config.TANK_LITRES}-litre tank")

        st.caption(
            "Each province is its median and the 10th–90th percentile of station "
            f"prices; {home} is opened up into the individual pumps behind that "
            "band. The tails, not the quartiles, are what a driver can act on: "
            "the cheapest pump within reach is a tail, not a median."
            + (f" {n_off} pump{'s' if n_off != 1 else ''} in {home} price outside "
               "the range drawn and are not shown; the range beside it counts them."
               if n_off else "")
        )

    with tab_data:
        table(
            disp.sort_values("p90_p10_cents")[
                ["Provincia", "median_eur", "iqr_cents", "p90_p10_cents", "n_stations"]],
            filename=f"dispersion_{product}.csv",
            column_config={
                "median_eur": st.column_config.NumberColumn("Median price", format="€ %.3f"),
                "iqr_cents": st.column_config.NumberColumn("IQR", format="%.1f c"),
                "p90_p10_cents": st.column_config.NumberColumn("p90 − p10", format="%.1f c"),
                "n_stations": st.column_config.NumberColumn("Stations/week", format="%.0f"),
            },
        )


# -----------------------------------------------------------------------------
# 4. Motorway vs ordinary road
# -----------------------------------------------------------------------------

elif page == "Motorway vs ordinary road":
    st.markdown(
        "Median motorway price minus median ordinary-road price, week by week. "
        "Medians rather than means: 105 motorway stations against 5,200 ordinary "
        "ones is an unbalanced comparison, and the median is the more stable "
        "summary of the smaller group."
    )

    tab_fig, tab_explore, tab_data = st.tabs(["Report figure", "Explore", "Table"])
    mw = views["mw"]

    with tab_fig:
        show(figures.fig_motorway(D), filename="05_motorway.png")
        st.caption("This figure shows both fuels, so the fuel control does not apply to it.")

    with tab_explore:
        wide = (mw.pivot(index="date", columns="product", values="premium_cents")
                .round(1)  # tooltip precision — see ranked_bar
                .rename(columns=fuels.DISPLAY))
        series = [fuels.DISPLAY[p] for p in fuels.HEADLINE if fuels.DISPLAY[p] in wide.columns]
        st.line_chart(
            wide, y=series,
            color=[figures.PROD_COLOUR[p] for p in fuels.HEADLINE
                   if fuels.DISPLAY[p] in wide.columns],
            x_label="", y_label="premium, cents/litre", height=420,
        )
        prem = for_product(views, "mw", product)["premium_cents"]
        if not prem.empty:
            a, b, c = st.columns(3)
            a.metric(f"{fuels.DISPLAY[product]}: mean premium", f"{prem.mean():.1f} c/L",
                     border=True)
            b.metric("Narrowest week", f"{prem.min():.1f} c/L", border=True)
            c.metric("Widest week", f"{prem.max():.1f} c/L", border=True)
        st.caption("The premium never closes: it has no week at zero in either fuel.")

    with tab_data:
        table(
            mw.sort_values(["product", "date"]),
            filename="motorway_weekly.csv",
            column_config={
                "date": st.column_config.DateColumn("Week"),
                "motorway": st.column_config.NumberColumn("Motorway", format="€ %.3f"),
                "ordinary": st.column_config.NumberColumn("Ordinary road", format="€ %.3f"),
                "premium_cents": st.column_config.NumberColumn("Premium", format="%.1f c"),
            },
        )


# -----------------------------------------------------------------------------
# 5. Attended vs self-service
# -----------------------------------------------------------------------------

elif page == "Attended vs self-service":
    st.markdown(
        "The attended-service premium, measured **within the same station and "
        "week**. Only stations that posted both a self and a served price for the "
        "same product in the same week contribute, so the gap is a service "
        "premium and not a difference in which stations offer what."
    )

    tab_fig, tab_explore, tab_data = st.tabs(["Report figure", "Explore", "Table"])
    svc = for_product(views, "svc", product)
    pairs = views["pairs"][product]

    with tab_fig:
        show(figures.fig_service(D, product), filename=f"07_service_{product}.png")

    with tab_explore:
        ranked_bar(svc, "gap_cents", home, value_label="attended premium, cents/litre")
        if not pairs.empty:
            a, b, c = st.columns(3)
            a.metric("Mean over all pairs", f"{pairs['gap_cents'].mean():.1f} c/L",
                     border=True)
            at_zero = float((pairs["gap_cents"].abs() < 0.5).mean() * 100)
            b.metric("Station-weeks at zero", f"{at_zero:.0f}%", border=True,
                     help="Stations posting the same price for both services.")
            c.metric("Paired station-weeks", f"{len(pairs):,}", border=True)

    with tab_data:
        table(
            svc.sort_values("gap_cents")[
                ["Provincia", "gap_cents", "gap_median", "n_pairs", "n_stations"]],
            filename=f"service_gap_{product}.csv",
            column_config={
                "gap_cents": st.column_config.NumberColumn("Mean gap", format="%.1f c"),
                "gap_median": st.column_config.NumberColumn("Median gap", format="%.1f c"),
                "n_pairs": st.column_config.NumberColumn("Station-weeks", format="%d"),
                "n_stations": st.column_config.NumberColumn("Stations", format="%d"),
            },
        )


# -----------------------------------------------------------------------------
# 6. Data quality
# -----------------------------------------------------------------------------

elif page == "Data quality":
    st.markdown(
        "Every filter is counted rather than silently applied. These are the "
        "published checks, over **all 105 weeks** — they describe the dataset "
        "itself, so the week control does not apply to them."
    )

    qc = get_qc()
    DQ = figure_data(views, weeks[0], weeks[-1], whole_panel=True)

    a, b, c, d = st.columns(4)
    a.metric("Stations in Nord-Est", f"{qc['registry']['stations_ne']:,}", border=True)
    b.metric("Posted prices kept", f"{qc['panel']['rows_kept']:,}",
             delta=f"{qc['panel']['pct_kept']}% of Nord-Est rows", delta_color="off",
             border=True)
    c.metric("Weeks present", f"{qc['scope']['weeks_present']} / {qc['scope']['weeks_expected']}",
             border=True)
    d.metric("Free-text fuel labels", f"{qc['fuel_labels_seen']}",
             delta=f"mapped onto {len(fuels.DISPLAY)} products", delta_color="off",
             border=True)

    show(figures.fig_coverage(DQ), filename="01_coverage.png")
    show(figures.fig_quality(DQ), filename="02_quality.png")
    show(figures.fig_harmonisation(DQ), filename="03_harmonisation.png")

    st.subheader("Exclusions, counted")
    ex = pd.DataFrame(
        [{"Rule": k, "Rows": v["n"], "% of Nord-Est rows": v["pct_of_ne"]}
         for k, v in qc["exclusions"].items()]
    ).sort_values("Rows", ascending=False)
    table(ex, filename="exclusions.csv")

    with st.expander("The full quality-control record (qc.json)"):
        st.json(qc)


# -----------------------------------------------------------------------------
# 7. Method and downloads
# -----------------------------------------------------------------------------

elif page == "Method and downloads":
    st.subheader("What this app computes")
    st.markdown(
        f"""
        Scope: the {len(config.NE_PROVINCES)} provinces of ISTAT NUTS-1 *Nord-Est*,
        {config.START:%d %b %Y} to {config.END:%d %b %Y}, one observation day per
        week ({SAMPLE_WEEKDAY_NAME}). The map question needs breadth of stations,
        not daily resolution, so weekly sampling costs nothing here.

        Two rules hold in every view, because both guard against composition
        effects that would otherwise masquerade as geography:

        1. Statistics are computed **within a week** and then averaged across
           weeks, so a province that reports more often during expensive weeks
           does not look expensive.
        2. Paired comparisons are made **within a station**, so the attended gap
           is a service premium rather than a difference in which stations offer
           what.

        Quality thresholds, all named constants in `scripts/config.py`: posted
        prices outside €{config.PRICE_MIN}–{config.PRICE_MAX}/litre are treated as
        data-entry errors; quotes are flagged at {config.STALE_FLAG_DAYS} days and
        dropped only past {config.STALE_DROP_DAYS}, because operators must report
        price *changes*, not reconfirm unchanged prices.

        Prices are *posted* and self-reported, not transaction prices, and are not
        weighted by volume sold. Methane, LNG and L-GNC are priced per kilogram and
        appear in no EUR/litre view. See §7 of the technical report for the full
        limitations.
        """
    )

    st.subheader("How the app relates to the report")
    st.markdown(
        "The figures here are the report's own builders in `scripts/figures.py`, "
        "fed the aggregates of `scripts/analyse.py` recomputed over the window you "
        "chose. At the full range they reproduce `figures/01`–`08` exactly. The "
        "app never re-implements a statistic."
    )

    st.subheader("Downloads for this window")
    st.caption(f"{first:%d %b %Y} – {last:%d %b %Y}, {n_weeks} weeks.")
    for label, key, name in [
        ("Provincial means and deviations", "dev", "province_deviation"),
        ("Within-province dispersion", "disp", "dispersion"),
        ("Motorway premium, weekly", "mw", "motorway_weekly"),
        ("Attended-service gap", "svc", "service_gap"),
    ]:
        st.download_button(
            f"{label} (CSV)",
            views[key].to_csv(index=False).encode("utf-8"),
            file_name=f"{name}_{first:%Y%m%d}_{last:%Y%m%d}.csv",
            mime="text/csv", key=f"dl::{key}",
        )

    st.subheader("Source")
    st.markdown(
        "MIMIT *Osservaprezzi Carburanti* (IODL 2.0) — daily posted prices for "
        "every Italian fuel station, plus the station registry, from "
        "<https://www.mimit.gov.it/it/open-data/elenco-dataset/carburanti-archivio-prezzi>. "
        "Province boundaries from openpolis/geojson-italy (CC-BY)."
    )


st.divider()
st.caption(
    "Where You Refuel · MIMIT Osservaprezzi Carburanti (IODL 2.0), Mondays "
    "2024–2025 · figures and app share one palette, validated on this surface."
)
