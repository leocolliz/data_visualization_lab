"""Low-fidelity wireframe of the proposed solution.

Layout and linking only, deliberately not visual design: the point of a
wireframe at proposal stage is to commit to a structure and to what
cross-filters what, before any of it is styled.
"""

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

import style

style.apply()

# pad is in data units and expands the box *outside* the given rect, so keep it
# small — the layout below is spaced on the nominal rects.
BOX = dict(boxstyle="round,pad=0.004,rounding_size=0.012", linewidth=1.0)


def box(ax, x, y, w, h, title, body="", accent=False):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, facecolor="#ffffff" if not accent else "#f2f7fe",
        edgecolor=style.C1 if accent else style.AXIS, **BOX))
    ax.text(x + 0.014, y + h - 0.030, title, fontsize=9.5, fontweight="bold",
            color=style.INK, va="top")
    if body:
        ax.text(x + 0.014, y + h - 0.062, body, fontsize=8.0,
                color=style.INK_2, va="top", linespacing=1.5)


def act(ax, x, y, label):
    ax.text(x, y, label, fontsize=10, fontweight="bold", color=style.C1)


def main():
    fig, ax = plt.subplots(figsize=(9.0, 10.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.grid(False)

    box(ax, 0.02, 0.905, 0.96, 0.082,
        "What does a litre really cost here?",
        "Scrollytelling header — hero figure: the cents/litre you lose by "
        "picking the wrong pump", accent=True)

    act(ax, 0.02, 0.878, "ACT 1  ·  Where you are")
    box(ax, 0.02, 0.660, 0.56, 0.200,
        "Choropleth — 22 provinces",
        "Diverging blue↔red, cents above/below the Nord-Est mean.\n"
        "Polarity, not magnitude, so diverging is the right family.\n"
        "Hover: province detail. Click: cross-filters everything below.")
    box(ax, 0.60, 0.660, 0.38, 0.200,
        "Ranked bars",
        "The same 22 provinces ordered by price —\n"
        "ordering carries the comparison the map\n"
        "cannot make precise. Shares the map's scale.")

    act(ax, 0.02, 0.632, "ACT 2  ·  Which pump — the turn in the argument")
    box(ax, 0.02, 0.398, 0.96, 0.216,
        "Range plot — the spread inside each province",
        "Median and 10th–90th percentile of station prices, one row per "
        "province.\nThe reveal: the within-province spread is as wide as the "
        "whole between-province range,\nso the reader's mental model "
        "(\"my province is expensive\") is replaced by\n(\"my province "
        "contains both the cheapest and the dearest pump I could reach\").\n"
        "Selecting a province drops to a station-level dot strip.")

    act(ax, 0.02, 0.378, "ACT 3  ·  Two choices that cost more than geography")
    box(ax, 0.02, 0.215, 0.47, 0.148,
        "Motorway vs ordinary road",
        "Small multiples, one panel per fuel.\n"
        "Hue = fuel, shade = road type, so no\n"
        "panel needs four categorical slots.\n"
        "Premium over time beneath.")
    box(ax, 0.51, 0.215, 0.47, 0.148,
        "Attended vs self-service",
        "Dumbbell per province, paired within\n"
        "station and week. Annotated with the\n"
        "third of stations that charge nothing —\n"
        "the distribution is bimodal, not a mean.")

    box(ax, 0.02, 0.118, 0.96, 0.082,
        "Filter row (one row, above the views)",
        "Fuel: petrol | diesel        Service: self | attended        "
        "Road: all | motorway | ordinary        Date range")

    box(ax, 0.02, 0.006, 0.96, 0.100,
        "Accessibility & provenance layer",
        "Table view of every figure · palette validated for colour-blind "
        "separation, light and dark\n"
        "Source, licence and extraction date · download the cleaned panel (CSV)")

    # The map cross-filters every view below it; drawn on the right so the
    # marker never crosses an act heading.
    ax.annotate("", xy=(0.86, 0.618), xytext=(0.86, 0.656),
                arrowprops=dict(arrowstyle="->", color=style.C2, lw=1.4))
    ax.text(0.875, 0.637, "cross-filters Acts 2–3", fontsize=8, color=style.C2,
            va="center", ha="left")

    ax.text(0.02, -0.020, "Low-fidelity wireframe — layout and linking only, "
                          "not final visual design.",
            fontsize=8, color=style.MUTED)

    style.save(fig, "09_wireframe.png")


if __name__ == "__main__":
    main()
