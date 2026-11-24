"""
Write Gerber RS-274X files for CNC milling (EasyTrace5000 / any Gerber CAM), from the SAME
parameters as sim_patch.py (patch_design.py). Board origin moved to the lower-left corner (0,0).

  python make_cnc.py                 # defaults = same as sim_patch.py defaults
  python make_cnc.py --length 26.9 --inset 6.2 --gap 10

Output in ./cnc:
  patch_copper-pour_F_Cu.gbr   top copper: patch + feed + pour with GAP clearance   <- the board you want
  patch_only_F_Cu.gbr          top copper: patch + feed only (reference)
  board_Edge_Cuts.gbr          100 x 75 mm outline (cutout)
  preview.png                  quick visual check
Bottom layer = solid ground: nothing to mill there.
"""
import argparse
import os

import patch_design as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cnc")
DX, DY = pd.BOARD_X / 2, pd.BOARD_Y / 2      # shift centred coords -> lower-left origin


def fmt(v):
    return str(int(round(v * 1e6)))           # FSLAX46Y46, mm


def header(comment):
    return [f"G04 {comment}*", "%FSLAX46Y46*%", "%MOMM*%", "%LPD*%", "%ADD10C,0.100*%", "G01*"]


def region(poly):
    out = ["G36*"]
    for k, (x, y) in enumerate(poly + [poly[0]]):
        out.append(f"X{fmt(x + DX)}Y{fmt(y + DY)}{'D02' if k == 0 else 'D01'}*")
    out.append("G37*")
    return out


def write(path, lines):
    with open(path, "w", newline="\n") as fh:
        fh.write("\n".join(lines + ["M02*"]) + "\n")


def main():
    ap = argparse.ArgumentParser()
    pd.add_args(ap)
    args = ap.parse_args()
    g = pd.geometry(args)
    os.makedirs(OUT, exist_ok=True)
    print(pd.describe(g))

    patch, pour = pd.patch_polygon(g), pd.pour_polygon(g)
    write(os.path.join(OUT, "patch_copper-pour_F_Cu.gbr"),
          header(f"Top copper, patch + {g['gap']} mm clearance pour") + region(pour) + region(patch))
    write(os.path.join(OUT, "patch_only_F_Cu.gbr"), header("Top copper, patch only") + region(patch))

    edge = ["D10*"] + [f"X{fmt(x)}Y{fmt(y)}{'D02' if k == 0 else 'D01'}*" for k, (x, y) in
                       enumerate([(0, 0), (pd.BOARD_X, 0), (pd.BOARD_X, pd.BOARD_Y), (0, pd.BOARD_Y), (0, 0)])]
    write(os.path.join(OUT, "board_Edge_Cuts.gbr"), header("Board outline") + edge)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon
        fig, ax = plt.subplots(figsize=(8, 6.2))
        for poly, c in ((pour, "#c58b3a"), (patch, "#e0a040")):
            ax.add_patch(Polygon([(x + DX, y + DY) for x, y in poly], closed=True, fc=c, ec="k", lw=0.6))
        ax.plot([0, pd.BOARD_X, pd.BOARD_X, 0, 0], [0, 0, pd.BOARD_Y, pd.BOARD_Y, 0], "k-", lw=1)
        ax.set_aspect("equal")
        ax.set_xlim(-3, pd.BOARD_X + 3)
        ax.set_ylim(-3, pd.BOARD_Y + 3)
        ax.set_title(pd.describe(g), fontsize=7)
        ax.set_xlabel("x (mm)")
        ax.set_ylabel("y (mm)")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT, "preview.png"), dpi=150)
    except ImportError:
        pass
    print(f"Gerbers -> {OUT}")


if __name__ == "__main__":
    main()
