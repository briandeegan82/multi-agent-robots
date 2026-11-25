"""T-ASE figures 2, 3, 4 and 8 at print size (all text >= 8 pt at the width used in the manuscript).

    PYTHONPATH=. python paper_tase_rev/figures/make_figures_tase.py   # from amr_negotiation/, writes paper_tase_rev/Images/
Fig. 4 is computed from studies/results_raw/{S1_baseline,reservation}.csv.gz and Fig. 8 from
studies/report_r2/gazebo_tase_runs.csv.gz; Figs. 2-3 are schematics drawn from the scenario files, with the Gazebo
renders of studies/gazebo/hires as panels 3(e,f).
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Polygon, Rectangle  # noqa: E402

from amr_negotiation import load_scenario  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "paper_tase_rev" / "Images"
RAW = ROOT / "studies" / "results_raw"
TEXTW, COLW = 7.16, 3.5  # IEEE two-column text and column widths [in]
FS = 8
plt.rcParams.update({"font.size": FS, "axes.titlesize": FS, "axes.labelsize": FS, "xtick.labelsize": FS,
                     "ytick.labelsize": FS, "legend.fontsize": FS, "font.family": "DejaVu Sans", "pdf.fonttype": 42,
                     "axes.spines.top": False, "axes.spines.right": False})
C = {"A": "#1f6fb4", "B": "#e0711b", "C": "#1a9a73", "S": "#d4609a"}
LIGHT = {"A": "#cfe3f5", "B": "#fbdcc6"}
NAVY = "#1d3557"


def save(fig, name):
    fig.savefig(IMG / f"{name}.pdf")  # no tight bbox: the PDF is exactly the printed width, so 8 pt stays 8 pt
    fig.savefig(Path("/tmp") / f"{name}.png", dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 2
def fig_formulation():
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(TEXTW, 2.4), layout="constrained",
                                   gridspec_kw={"width_ratios": [1, 1.5]})
    hw, bw, bd, ypark = 0.325, 0.80, 0.60, 0.625
    out = [(-0.95, -hw), (0.95, -hw), (0.95, hw), (bw / 2, hw), (bw / 2, hw + bd), (-bw / 2, hw + bd), (-bw / 2, hw),
           (-0.95, hw)]
    ax.add_patch(Polygon(out, closed=True, fc="#f1f3f8", ec="0.15", lw=1.4))
    for y in (-0.30, 0.30):
        ax.plot([-0.95, 0.95], [y, y], ":", color=C["B"], lw=1)
    for x, lab in ((-0.8, r"$x_{\mathrm{hold}}$"), (0.0, r"$x_r$"), (0.8, r"$x_{\mathrm{pass}}$")):
        ax.plot([x, x], [-hw, hw], "--", color="0.45", lw=0.8)
        ax.text(x, -hw - 0.04, lab, ha="center", va="top")
    ax.add_patch(Rectangle((-0.1405, ypark - 0.153), 0.281, 0.306, fc=C["A"], ec="0.2"))
    ax.text(0, ypark, "Y", ha="center", va="center", color="w", weight="bold", fontsize=10)
    ax.text(0.43, ypark + 0.12, r"$y_{\mathrm{park}}$" + "\n= +0.625 m", ha="left", va="center", color=NAVY,
            linespacing=1.0)
    ax.add_patch(Rectangle((-0.1405, -0.153), 0.281, 0.306, fc=C["B"], ec="0.2"))
    ax.add_patch(plt.Circle((0, 0), 0.25, fill=False, ls="--", ec="0.3", lw=0.8))
    ax.text(0, 0, "P", ha="center", va="center", color="w", weight="bold", fontsize=10)
    ax.text(0.27, 0.07, "0.281×0.306 m", ha="left", va="center")
    ax.text(0.27, -0.09, r"$R_{\mathrm{sw}}$ = 0.25 m", ha="left", va="center")
    ax.annotate("", (bw / 2, hw + bd + 0.07), (-bw / 2, hw + bd + 0.07), arrowprops={"arrowstyle": "<->", "lw": 0.9})
    ax.text(0, hw + bd + 0.10, r"bay $w_r$ = 0.80 m × $d_b$ = 0.60 m", ha="center", va="bottom")
    ax.annotate("", (-1.04, hw), (-1.04, -hw), arrowprops={"arrowstyle": "<->", "lw": 0.9})
    ax.text(-1.08, 0, r"$W$ = 0.65 m", rotation=90, ha="right", va="center")
    ax.text(-0.05, -0.56, r"$2(w_{\mathrm{rob}}+c_{\mathrm{clear}})$ = 0.712 m > $W$" + "\n(no side-by-side passing)",
            ha="center", va="top", color="#c0262d", linespacing=1.1)
    ax.set(xlim=(-1.3, 1.1), ylim=(-0.80, 1.12), xticks=[-0.5, 0, 0.5], yticks=[-0.3, 0, 0.3, 0.6, 0.9],
           xlabel=r"Longitudinal offset $x-x_r$ [m]", ylabel="Lateral $y$ [m]")
    ax.set_aspect("equal")
    ax.set_title("(a) Clearance and refuge geometry", loc="left")

    bx.set_axis_off()
    bx.set(xlim=(-0.05, 6.05), ylim=(-0.5, 1.32))
    bx.set_title("(b) Synchronized yield-maneuver timeline", loc="left")
    yr, pr, h = 0.72, 0.0, 0.36
    ysegs = [(0, 1.4, "Approach /\nreverse", LIGHT["A"]), (1.4, 2.3, "Turn,\npark", "#9cc6e8"),
             (2.3, 3.6, r"Wait in $r$", "#e8edf3"), (3.6, 4.5, "Exit,\nturn", "#9cc6e8"),
             (4.5, 6.0, "Cruise\nto goal", LIGHT["A"])]
    psegs = [(0, 1.4, "Approach\n" + r"$x_{\mathrm{hold}}(r,P)$", LIGHT["B"]), (1.4, 2.3, "Hold", "#fdeee3"),
             (2.3, 3.6, "Pass refuge\n" + r"to $x_{\mathrm{pass}}$", "#f4a582"),
             (3.6, 6.0, "Cruise to goal", LIGHT["B"])]
    for y0, segs, ec in ((yr, ysegs, C["A"]), (pr, psegs, C["B"])):
        for a, b, lab, fc in segs:
            bx.add_patch(Rectangle((a, y0), b - a, h, fc=fc, ec=ec, lw=0.9))
            bx.text((a + b) / 2, y0 + h / 2, lab, ha="center", va="center", linespacing=1.0)
    bx.text(0, yr + h + 0.04, "Yielder $Y$", ha="left", va="bottom", color=C["A"], weight="bold")
    bx.text(0, pr + h + 0.04, "Proceeder $P$", ha="left", va="bottom", color=C["B"], weight="bold")
    for t, lab, ha in ((0, r"$t_0$: conflict detected", "left"),
                       (2.3, r"$t_{\mathrm{go}}=\max(t_{\mathrm{park}},t_{\mathrm{hold}})$", "center"),
                       (3.62, r"$t_{\mathrm{pass}}$: lane clear", "left")):
        bx.plot([t, t], [-0.06, yr + h + 0.02], "--", color="0.35", lw=0.8)
    bx.text(0, -0.08, r"$t_0$: conflict" + "\ndetected", ha="left", va="top", linespacing=1.0)
    bx.text(2.3, -0.08, r"$t_{\mathrm{go}}$ =" + "\n" + r"$\max(t_{\mathrm{park}},t_{\mathrm{hold}})$", ha="center",
            va="top", linespacing=1.0)
    bx.text(3.65, -0.08, r"$t_{\mathrm{pass}}$:" + "\nlane clear", ha="left", va="top", linespacing=1.0)
    bx.annotate("", (2.3, yr - 0.01), (2.3, pr + h + 0.01), arrowprops={"arrowstyle": "->", "color": C["C"], "lw": 1.2})
    bx.text(2.36, (yr + pr + h) / 2 - 0.01, "Y parked off-lane releases P", ha="left", va="center", color=C["C"])
    save(fig, "problem_formulation")


# ---------------------------------------------------------------- Fig. 3
def draw_layout(ax, sc, title):
    for r in sc.free_rects():
        ax.add_patch(Rectangle((r.x0, r.y0), r.x1 - r.x0, r.y1 - r.y0, fc="#f1f3f8", ec="none"))
    for (x0, y0), (x1, y1) in sc.wall_segments():
        ax.plot([x0, x1], [y0, y1], "-", color="0.1", lw=1.3)
    rr = sc.room_length
    for r in sc.refuges():
        ax.plot(r.x, r.park_y, "x", color="0.2", ms=6, mew=1.6)
        if r.kind == "bay":
            if r.park_y < -1.2:
                ax.text(r.x + 0.45, r.park_y + 0.25, r.id, ha="left", va="center", color=NAVY, weight="bold")
            elif r.park_y > 0:
                ax.text(r.x, r.park_y + 0.35, r.id, ha="center", va="bottom", color=NAVY, weight="bold")
            else:
                ax.text(r.x, r.park_y - 0.35, r.id, ha="center", va="top", color=NAVY, weight="bold")
    ax.text(-rr / 2, -0.97, "room_lo", ha="center", va="center", color="0.35")
    ax.text(sc.length + rr / 2, -0.97, "room_hi", ha="center", va="center", color="0.35")
    for a in sc.agents:
        x, y, _ = sc.start_pose(a)
        col = C.get(a.id, "0.5")
        ax.plot(x, y, "o", ms=11, mfc=col, mec="0.15", mew=0.6, zorder=4)
        ax.text(x, y, a.id, ha="center", va="center", color="w", weight="bold", zorder=5)
        if a.start_refuge:
            ax.annotate("", (x, y + 0.95), (x, y + 0.4), arrowprops={"arrowstyle": "-|>", "color": col, "lw": 1.2})
        else:
            d = a.direction
            ax.annotate("", (x + 1.0 * d, y), (x + 0.42 * d, y), arrowprops={"arrowstyle": "-|>", "color": col, "lw": 1.2})
    ax.set_aspect("equal")
    ax.set_ylabel("y [m]")
    ax.set_title(title, loc="left", pad=2)


def fig_scenarios():
    S = ROOT / "scenarios"
    rows = [("corridor_single_bay", "(a) Single-bay corridor ($L$ = 8.0 m, $W$ = 0.65 m)"),
            ("corridor_two_bays", "(b) Two-bay corridor ($L$ = 10.0 m, $W$ = 0.65 m)"),
            ("corridor_convoy", "(c) Convoy encounter (2 vs. 1, $L$ = 10.0 m)"),
            ("corridor_tjunction_goal", "(d) T-junction branch (3 robots, 2.0 m stem)")]
    scs = [load_scenario(S / f"{n}.yaml") for n, _ in rows]
    fig = plt.figure(figsize=(TEXTW, 4.1), layout="constrained")
    og = fig.add_gridspec(1, 2, width_ratios=[1.08, 1])
    lg = og[0].subgridspec(4, 1, height_ratios=[1, 1, 1, 1.32])
    rg = og[1].subgridspec(3, 1, height_ratios=[1, 1.2, 0.36])
    xl = (-0.2 - max(s.room_length for s in scs), max(s.length + s.room_length for s in scs) + 0.2)
    for i, ((n, title), sc) in enumerate(zip(rows, scs)):
        ax = fig.add_subplot(lg[i])
        draw_layout(ax, sc, title)
        ax.set_xlim(*xl)
        ax.set_ylim(*((-1.45, 1.6) if i < 3 else (-2.45, 1.6)))
        if i < 3:
            ax.tick_params(labelbottom=False)
        else:
            ax.set_xlabel("x [m]")
    for j, (p, title, labs) in enumerate((
            ("e", "(e) Gazebo: 2-robot corridor pass",
             [((0.34, 0.67), (0.12, 0.90), "Waffle A\n(in bay0)", C["A"]),
              ((0.69, 0.55), (0.80, 0.18), "Waffle B\n(proceeding)", C["B"])]),
            ("f", "(f) Gazebo: 3-robot T-junction staging",
             [((0.17, 0.83), (0.15, 0.55), "A staged in bay0", C["A"]),
              ((0.31, 0.74), (0.40, 0.40), "B passing", C["B"]),
              ((0.74, 0.70), (0.56, 0.17), "S in branch", C["S"])]))):
        ax = fig.add_subplot(rg[j])
        im = plt.imread(IMG / f"gazebo_panel_{p}.png")
        hh = im.shape[0] / im.shape[1]
        ax.imshow(im, extent=(0, 1, 0, hh), interpolation="none")  # embed native pixels, not 100 dpi resample
        for (xa, ya), (xt, yt), txt, col in labs:
            ax.annotate(txt, (xa, ya * hh), (xt, yt * hh), ha="center", va="center", color=col, weight="bold",
                        linespacing=1.0, bbox={"boxstyle": "round,pad=0.25", "fc": "w", "ec": col, "lw": 1},
                        arrowprops={"arrowstyle": "-|>", "color": col, "lw": 1})
        ax.set_axis_off()
        ax.set_title(title, loc="left", pad=2)
    lax = fig.add_subplot(rg[2])
    lax.set_axis_off()
    handles = [Line2D([], [], marker="o", ls="", mfc=C[k], mec="0.15", ms=8, label=lab) for k, lab in
               (("A", "A: eastbound leader"), ("B", "B: westbound peer"), ("C", "C: convoy follower"),
                ("S", "S: branch stem robot"))] + [Line2D([], [], marker="x", ls="", color="0.2", mew=1.6, ms=7,
                                                          label="refuge parking pose")]
    lax.legend(handles=handles, loc="center", ncol=2, frameon=True, columnspacing=0.8, handletextpad=0.3,
               borderpad=0.4, labelspacing=0.3)
    save(fig, "scenarios")


# ---------------------------------------------------------------- Fig. 4
def excess_by_x(df, ref_fn, labels, xcol):
    out = {}
    v = df.total_delay.where(df.success, 2 * 180.0)
    w = df.assign(v=v).pivot_table(index=[xcol, "seed"], columns="label", values="v", aggfunc="first")
    ref = ref_fn(w)
    for lab in labels:
        d = (w[lab] - ref).groupby(level=0)
        out[lab] = pd.DataFrame({"m": d.mean(), "h": 1.96 * d.std(ddof=1) / np.sqrt(d.count())})
    return out


def fig_bay_geometry():
    s1 = pd.read_csv(RAW / "S1_baseline.csv.gz")
    s1 = s1.assign(sd=s1["agents.1.start_delay"])
    s1 = s1.assign(seed=s1.seed.astype(str) + "_" + s1.sd.round(6).astype(str))
    a = excess_by_x(s1, lambda w: w["oracle"], ["fixed_priority", "rules_proximity", "cost_bid"], "bays.0.x")
    rs = pd.read_csv(RAW / "reservation.csv.gz")
    b = excess_by_x(rs, lambda w: w[["forced_A", "forced_B"]].min(axis=1), ["reservation"], "x")
    fig, ax = plt.subplots(figsize=(COLW, 2.35), layout="constrained")
    sty = [(b["reservation"], "reservation (FCFS)", "#c96fa3", "D", "--"),
           (a["fixed_priority"], "fixed priority / default rule", "#d95f0e", "s", "-"),
           (a["rules_proximity"], "closest-refuge rulebook", "#56b4e9", "^", "-"),
           (a["cost_bid"], "cost_bid", "#0b66a8", "o", "-")]
    for t, lab, col, mk, ls in sty:
        ax.errorbar(t.index, t.m, yerr=t.h, label=lab, color=col, marker=mk, ms=4, ls=ls, lw=1.4, capsize=2)
    ax.set(xlabel="Bay position $x$ [m] ($A$ enters at 0, $B$ at 8)", ylabel=r"Excess delay $\Delta_\pi$ [s]",
           ylim=(-1.5, 41), xticks=range(1, 8))
    ax.grid(alpha=0.3)
    ax.legend(ncol=2, loc="upper left", frameon=False, handlelength=1.6, columnspacing=0.6, borderaxespad=0.1,
              handletextpad=0.3, labelspacing=0.25)
    save(fig, "fig5_bay_geometry")
    return a, b


# ---------------------------------------------------------------- Fig. 8
def fig_gazebo_scatter():
    g = pd.read_csv(ROOT / "studies" / "report_r2" / "gazebo_tase_runs.csv.gz").dropna(subset=["gz_wdelay", "d2_wdelay"])
    stoch, expl = g.group.isin(["S7", "S8b", "S8c_all_off"]), g.group == "explore_det_3.5"
    tj, rea = g.group.isin(["tj", "tjgoal"]), (g.policy == "reactive") & ~g.group.isin(["tj", "tjgoal"])
    shared = ~(stoch | expl | tj | rea)
    fig, ax = plt.subplots(figsize=(COLW, 2.5), layout="constrained")
    ax.plot([0, 170], [0, 170], "k--", lw=1, label="$y=x$")
    for m, lab, kw in ((shared, f"Shared draws ({shared.sum()})", {"c": "#2a7ab9", "marker": "o", "s": 12}),
                       (stoch, f"Noise / 90% loss ({stoch.sum()})",
                        {"c": "#e3b23c", "marker": "^", "s": 18}),
                       (expl, f"share_on_detect, 3.5 m ({expl.sum()})",
                        {"c": "#1a9a73", "marker": "D", "s": 16}),
                       (tj, f"T-junction ({tj.sum()})", {"c": "#d2691e", "marker": "s", "s": 14}),
                       (rea, f"Reactive ({rea.sum()})", {"c": "0.45", "marker": "x", "s": 18})):
        ax.scatter(g.d2_wdelay[m], g.gz_wdelay[m], label=lab, alpha=0.85, lw=0.8 if kw["marker"] == "x" else 0.3,
                   edgecolors=None if kw["marker"] == "x" else "0.2", **kw)
    s3 = g[expl & (g.seed == 3) & (g.policy == "fixed_priority")]
    if len(s3):
        ax.annotate("Seed 3\n(Supp. Fig. S5)", (s3.d2_wdelay.iloc[0], s3.gz_wdelay.iloc[0]), (62, 135),
                    color="#1a9a73", arrowprops={"arrowstyle": "->", "color": "#1a9a73"}, ha="center")
    dtj = (g.gz_wdelay - g.d2_wdelay)[tj].mean()
    ax.annotate(f"T-junction\n(mean $\\Delta D$ = {dtj:.1f} s)", (92, 57), (118, 32), color="#d2691e", ha="center",
                arrowprops={"arrowstyle": "->", "color": "#d2691e"})
    ax.set(xlim=(15, 170), ylim=(15, 170), xlabel="2D simulator weighted delay [s]",
           ylabel="Gazebo weighted delay [s]")
    ax.grid(alpha=0.3)
    fig.legend(loc="outside upper center", ncol=2, frameon=False, handletextpad=0.2, columnspacing=0.8,
               labelspacing=0.25)
    save(fig, "fig15_gazebo_scatter")
    return g


if __name__ == "__main__":
    which = sys.argv[1:] or ["2", "3", "4", "8"]
    for k, f in (("2", fig_formulation), ("3", fig_scenarios), ("4", fig_bay_geometry), ("8", fig_gazebo_scatter)):
        if k in which:
            f()
