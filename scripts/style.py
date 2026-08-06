"""Chart styling: one palette, one theme, applied everywhere.

Colours are the validated reference palette. Slots are assigned by the *job*
the colour does, never by series index:

  categorical  identity   two series max in these figures -> slots 1 and 2
  sequential   magnitude  one hue, light -> dark
  diverging    polarity   blue <-> red with a neutral gray midpoint

The two-slot categorical pair was checked with the skill's validator on the
light surface: worst adjacent CVD dE 24.7 (protan), normal-vision dE 33.6,
both clear of the gates.

Figures are rendered for a printed report, so light mode only; the interactive
solution will need its own dark steps rather than an automatic flip.
"""

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# --- surfaces and ink ----------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# --- categorical (identity) ----------------------------------------------
C1 = "#2a78d6"  # blue
C2 = "#eb6834"  # orange
NEUTRAL = "#c9c8c1"  # de-emphasised marks

# --- sequential (magnitude), blue ramp -----------------------------------
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#256abf",
       "#1c5cab", "#184f95", "#104281"]

# --- diverging (polarity): blue <-> gray <-> red -------------------------
DIVERGING = LinearSegmentedColormap.from_list(
    "ne_div",
    ["#184f95", "#2a78d6", "#9ec5f4", "#f0efec", "#f3a6a5", "#e34948", "#a52f2e"],
)
SEQUENTIAL = LinearSegmentedColormap.from_list("ne_seq", SEQ)


def apply():
    mpl.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": ["DejaVu Sans"],
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2,
        "xtick.major.size": 0,
        "ytick.major.size": 0,
        "legend.frameon": False,
        "legend.labelcolor": INK_2,
        "lines.linewidth": 1.6,
        "lines.markersize": 4.5,
        "figure.dpi": 130,
        "savefig.dpi": 130,
        "savefig.bbox": "tight",
    })


def titles(ax, title, subtitle=None):
    """Left-aligned title plus a quieter subtitle, in ink tokens only."""
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold",
                 color=INK, pad=18 if subtitle else 8)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=10,
                color=INK_2, va="bottom")


SOURCE = ("Source: MIMIT Osservaprezzi Carburanti (IODL 2.0), weekly extracts, "
          "Mondays 2024-2025. Nord-Est: 22 provinces, 5,329 stations. "
          "Boundaries: openpolis/geojson-italy (ISTAT).")


def source_note(fig, extra=None):
    fig.text(0.005, -0.01, SOURCE + (f"  {extra}" if extra else ""),
             fontsize=7.5, color=MUTED, va="top")


def save(fig, name):
    from config import FIGURES
    fig.savefig(FIGURES / name, facecolor=SURFACE)
    plt.close(fig)
    print(f"  wrote figures/{name}")
