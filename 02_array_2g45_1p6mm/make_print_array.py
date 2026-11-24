"""
A4 print (1:1, real size) + Gerbers for the 1x2 patch array.
Uses results_array/tuned.json from sim_array.py if present, otherwise the analytic design.

  python make_print_array.py

Output in ./print_array:
  array_A4_1to1.pdf   p1: top copper, real size (normal)       -> CNC/visual check, place on board
                      p2: top copper, real size, MIRRORED      -> toner transfer
                      p3: dimensioned drawing + table
  array_F_Cu.gbr, array_Edge_Cuts.gbr  (Gerber RS-274X, origin = board lower-left)
PRINT AT 100% / "Actual size" (no "Fit to page"), then check the 100 mm ruler.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle

import array_design as ad

OUT = os.path.join(ad.HERE, "print_array")
A4W, A4H = 210.0, 297.0
MM = 1 / 25.4
BX, BY = ad.BOARD_X, ad.BOARD_Y


def mm_axes(fig, x0, y0, w, h, xlim, ylim):
    """Axes where 1 data unit = 1 mm on paper."""
    ax = fig.add_axes([x0 / A4W, y0 / A4H, w / A4W, h / A4H])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_axis_off()
    return ax


def draw_copper(ax, d, mirror=False, color="black"):
    s = -1 if mirror else 1
    for n, x, y, dx, dy in ad.rectangles(d):
        xx = x if not mirror else -(x + dx)
        ax.add_patch(Rectangle((xx, y), dx, dy, fc=color, ec="none"))
    ax.add_patch(Rectangle((-BX / 2, -BY / 2), BX, BY, fc="none", ec="black", lw=0.3))
    # corner crop marks + centre cross
    for cx in (-BX / 2, BX / 2):
        for cy in (-BY / 2, BY / 2):
            ax.plot([cx - 3 * s * (1 if cx > 0 else -1) * 0, cx], [cy, cy], "k", lw=0.2)
    ax.plot([-2, 2], [0, 0], "k", lw=0.2)
    ax.plot([0, 0], [-2, 2], "k", lw=0.2)


def ruler(fig, x0, y0):
    ax = mm_axes(fig, x0, y0 - 6, 110, 12, (0, 110), (-6, 6))
    ax.plot([0, 100], [0, 0], "k", lw=0.6)
    for k in range(0, 101, 5):
        ax.plot([k, k], [0, 3 if k % 10 == 0 else 1.5], "k", lw=0.4)
        if k % 10 == 0:
            ax.text(k, 3.6, str(k), ha="center", va="bottom", fontsize=5)
    ax.text(103, 0, "mm", va="center", fontsize=6)
    ax.text(0, -2.5, "Must measure exactly 100 mm. Print at 100 % / Actual size, NOT 'Fit to page'.",
            fontsize=6, va="top")


def layout_page(pdf, d, mirror):
    fig = plt.figure(figsize=(A4W * MM, A4H * MM))
    x0, y0 = (A4W - BX) / 2, 150
    ax = mm_axes(fig, x0, y0, BX, BY, (-BX / 2, BX / 2), (-BY / 2, BY / 2))
    draw_copper(ax, d, mirror)
    ruler(fig, 50, 110)
    t = ("1x2 inset-fed patch array 2.45 GHz - TOP COPPER, REAL SIZE 1:1" + (" - MIRRORED (toner transfer)" if mirror else "")
         + f"\nBoard {BX:.0f} x {BY:.0f} mm, FR4 1.6 mm, bottom = solid ground. Port / SMA at the bottom edge centre.")
    fig.text(0.5, (y0 + BY + 12) / A4H, t, ha="center", fontsize=8)
    if "f0_array_GHz" in d:
        fig.text(0.5, 0.33, f"openEMS: f0 = {d['f0_array_GHz']} GHz, S11 = {d['S11_array_dB']} dB, "
                 f"-10 dB BW = {d['BW10_array_MHz']} MHz, gain {d.get('gain_dBi','?')} dBi", ha="center", fontsize=7)
    elif "f0_sim_GHz" in d:
        fig.text(0.5, 0.33, f"HFSS: f0 = {d['f0_sim_GHz']} GHz, S11 = {d['S11_min_dB']} dB, "
                 f"-10 dB BW = {d['BW10_MHz']} MHz", ha="center", fontsize=7)
    else:
        fig.text(0.5, 0.33, "Analytic dimensions - NOT yet verified in HFSS (run sim_array.py first)",
                 ha="center", fontsize=7, color="red")
    pdf.savefig(fig)
    plt.close(fig)


def dim(ax, p1, p2, text, off=(0, 0), fs=6):
    ax.annotate("", p1, p2, arrowprops=dict(arrowstyle="<->", lw=0.5, shrinkA=0, shrinkB=0))
    ax.text((p1[0] + p2[0]) / 2 + off[0], (p1[1] + p2[1]) / 2 + off[1], text, fontsize=fs,
            ha="center", va="center", bbox=dict(fc="white", ec="none", pad=0.3))


def dims_page(pdf, d):
    fig = plt.figure(figsize=(A4W * MM, A4H * MM))
    ax = mm_axes(fig, 10, 150, 190, 125, (-95, 95), (-62, 63))
    for n, x, y, dx, dy in ad.rectangles(d):
        ax.add_patch(Rectangle((x, y), dx, dy, fc="#d9a441", ec="k", lw=0.3))
    ax.add_patch(Rectangle((-BX / 2, -BY / 2), BX, BY, fc="none", ec="k", lw=0.6))
    W, L, s, w50 = d["W"], d["L"], d["spacing"], d["w50"]
    yp, yj = ad.Y_PATCH_BOTTOM, ad.Y_JUNCTION
    xr = s / 2
    dim(ax, (-BX / 2, -BY / 2 - 6), (BX / 2, -BY / 2 - 6), f"{BX:.0f}")
    dim(ax, (BX / 2 + 6, -BY / 2), (BX / 2 + 6, BY / 2), f"{BY:.0f}")
    dim(ax, (xr - W / 2, yp + L + 4), (xr + W / 2, yp + L + 4), f"W {W:.2f}")
    dim(ax, (xr + W / 2 + 4, yp), (xr + W / 2 + 4, yp + L), f"L {L:.2f}")
    dim(ax, (-xr, yp + L + 9), (xr, yp + L + 9), f"spacing {s:.2f}")
    dim(ax, (xr - w50 / 2 - d["notch"], yp - 3), (xr + w50 / 2 + d["notch"], yp - 3),
        f"notch {d['notch']:.2f} | line {w50:.2f} | {d['notch']:.2f}", off=(0, -3), fs=5)
    dim(ax, (xr - W / 2 - 4, yp), (xr - W / 2 - 4, yp + d["y0"]), f"inset {d['y0']:.2f}", off=(-7, 0), fs=5)
    dim(ax, (6, yj - w50 / 2 - d["l_t2"]), (6, yj - w50 / 2), f"{d['l_t2']:.2f}", off=(5, 0))
    ax.text(-26, yj - w50 / 2 - d["l_t2"] / 2, f"w {d['w_t2']:.2f}\n({d['Z_t2']:.1f} ohm)", fontsize=5)
    ax.text(-xr - 22, yj + 3, f"50 ohm lines w {w50:.2f}", fontsize=5)
    dim(ax, (-BX / 2 - 6, -BY / 2), (-BX / 2 - 6, yp), f"{yp + BY/2:.2f}", off=(-5, 0))
    dim(ax, (-BX / 2 - 12, -BY / 2), (-BX / 2 - 12, yj), f"{yj + BY/2:.2f}", off=(-5, 0))
    fig.text(0.5, 0.95, "1x2 patch array - dimensions in mm (drawing not to scale; use page 1 for 1:1)",
             ha="center", fontsize=9)

    rows = ad.table(d)
    if "f0_array_GHz" in d:
        rows.append(("openEMS result", f"f0 {d['f0_array_GHz']} GHz, S11 {d['S11_array_dB']} dB, "
                     f"BW {d['BW10_array_MHz']} MHz, gain {d.get('gain_dBi','?')} dBi, eff {d.get('rad_eff','?')}"))
    elif "f0_sim_GHz" in d:
        rows.append(("HFSS result", f"f0 {d['f0_sim_GHz']} GHz, S11 {d['S11_min_dB']} dB, BW {d['BW10_MHz']} MHz"
                     + (f", gain {d['peak_gain_dBi']} dBi" if "peak_gain_dBi" in d else "")))
    else:
        rows.append(("HFSS result", "not run yet - analytic values"))
    rects = [(n, f"x {x + BX/2:.2f} .. {x + dx + BX/2:.2f}", f"y {y + BY/2:.2f} .. {y + dy + BY/2:.2f}")
             for n, x, y, dx, dy in ad.rectangles(d)]
    ty = 0.43
    for k, v in rows:
        fig.text(0.07, ty, k, fontsize=7, weight="bold")
        fig.text(0.42, ty, v, fontsize=7)
        ty -= 0.02
    ty -= 0.015
    fig.text(0.07, ty, "Copper rectangles, coordinates from board lower-left corner (mm):", fontsize=7, weight="bold")
    ty -= 0.02
    for n, a, b in rects:
        fig.text(0.09, ty, n, fontsize=6.5)
        fig.text(0.25, ty, a, fontsize=6.5)
        fig.text(0.50, ty, b, fontsize=6.5)
        ty -= 0.017
    pdf.savefig(fig)
    plt.close(fig)


def gerbers(d):
    def f(v):
        return str(int(round(v * 1e6)))
    hdr = ["%FSLAX46Y46*%", "%MOMM*%", "%LPD*%", "%ADD10C,0.100*%", "G01*"]
    cu = ["G04 1x2 patch array top copper*"] + hdr
    for n, x, y, dx, dy in ad.rectangles(d):
        x, y = x + BX / 2, y + BY / 2
        pts = [(x, y), (x + dx, y), (x + dx, y + dy), (x, y + dy), (x, y)]
        cu += ["G36*"] + [f"X{f(a)}Y{f(b)}{'D02' if k == 0 else 'D01'}*" for k, (a, b) in enumerate(pts)] + ["G37*"]
    edge = ["G04 board outline*"] + hdr + ["D10*"] + [
        f"X{f(a)}Y{f(b)}{'D02' if k == 0 else 'D01'}*" for k, (a, b) in enumerate([(0, 0), (BX, 0), (BX, BY), (0, BY), (0, 0)])]
    for name, lines in (("array_F_Cu.gbr", cu), ("array_Edge_Cuts.gbr", edge)):
        with open(os.path.join(OUT, name), "w", newline="\n") as fh:
            fh.write("\n".join(lines + ["M02*"]) + "\n")


def main():
    d = ad.load_design()
    ad.check(d)
    os.makedirs(OUT, exist_ok=True)
    with PdfPages(os.path.join(OUT, "array_A4_1to1.pdf")) as pdf:
        layout_page(pdf, d, mirror=False)
        layout_page(pdf, d, mirror=True)
        dims_page(pdf, d)
    gerbers(d)
    print("source:", "openEMS" if "f0_array_GHz" in d else ("HFSS" if "f0_sim_GHz" in d else "analytic (not simulated)"))
    for k, v in ad.table(d):
        print(f"{k:34s} {v}")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
