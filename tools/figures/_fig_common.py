"""Shared matplotlib setup and palette for manuscript figures (IEEE two-column).

Not a general-purpose plotting library -- just the handful of constants and
helpers every make_fig_*.py in this directory needs, kept in one place so the
five scripts stay literally identical on fonts/sizes/palette.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# IEEE column widths
COL_WIDTH_IN = 3.4
PAGE_WIDTH_IN = 7.16

FONT_SIZE = 8
TICK_SIZE = 7

plt.rcParams.update({
    "font.family": "serif",
    "font.size": FONT_SIZE,
    "axes.titlesize": FONT_SIZE,
    "axes.labelsize": FONT_SIZE,
    "xtick.labelsize": TICK_SIZE,
    "ytick.labelsize": TICK_SIZE,
    "legend.fontsize": TICK_SIZE,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "axes.grid": True,
    "grid.linewidth": 0.4,
    "grid.alpha": 0.5,
    "axes.axisbelow": True,
    "axes.linewidth": 0.6,
})

# dataviz skill categorical palette, slots 1-8, light-mode hex (print figures
# are a fixed light surface, so only the light column is used).
PALETTE = {
    1: "#2a78d6",  # blue
    2: "#eb6834",  # orange
    3: "#1baf7a",  # aqua
    4: "#eda100",  # yellow
    5: "#e87ba4",  # magenta
    6: "#008300",  # green
    7: "#4a3aa7",  # violet
    8: "#e34948",  # red
}

# Policy -> (palette slot, hatch, marker) so identity survives greyscale
# printing and CVD simulation without relying on hue alone.
POLICY_STYLE = {
    "p0": dict(color="#898781", hatch=None, marker="o", label="p0 (baseline)"),
    "p1": dict(color=PALETTE[1], hatch="//", marker="s", label="p1 (adjacent)"),
    "p2": dict(color=PALETTE[2], hatch="\\\\", marker="^", label="p2 (stride)"),
    "p3": dict(color=PALETTE[7], hatch="xx", marker="D", label="p3 (Markov)"),
    "p4": dict(color=PALETTE[8], hatch="..", marker="*", label="p4 (oracle)"),
}

CONFIG_STYLE = {
    "C0": dict(color="#898781", hatch=None, marker="o", label="C0 (prefetch ON)"),
    "C1": dict(color=PALETTE[1], hatch="//", marker="s", label="C1 (prefetch OFF)"),
    "C2": dict(color=PALETTE[2], hatch="\\\\", marker="^", label="C2 (stride, d=1)"),
    "C3": dict(color=PALETTE[8], hatch="..", marker="*", label="C3 (oracle, d=1)"),
}

INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"


def savefig(fig, outstem):
    fig.savefig(f"{outstem}.pdf", bbox_inches="tight")
    fig.savefig(f"{outstem}.png", bbox_inches="tight", dpi=250)
    plt.close(fig)


def pct_formatter():
    return mticker.FuncFormatter(lambda x, _: f"{x:g}%")
