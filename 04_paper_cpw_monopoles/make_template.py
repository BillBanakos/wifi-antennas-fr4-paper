"""
A4 template (1:1) for the two CPW-fed monopoles on copy paper, copper tape top side only.
  python make_template.py  ->  cpw_antennas_A4.pdf
"""
import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle

from sim_cpw import rects

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
A4W, A4H, MM = 210.0, 297.0, 1 / 25.4
ANT = [("C", "2.4 GHz WiFi"), ("G", "5.8 GHz WiFi")]


def mm_axes(fig, x0, y0, w, h, xlim, ylim):
    ax = fig.add_axes([x0 / A4W, y0 / A4H, w / A4W, h / A4H])
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_axis_off()
    return ax


def load(tag):
    r = json.load(open(os.path.join(RES, f"result_{tag}.json")))
    d = np.genfromtxt(os.path.join(RES, f"S11_{tag}.csv"), delimiter=",", names=True)
    return r, d


def draw(ax, g):
    sw, sh = g["SHEET_W"], g["SHEET_H"]
    ax.add_patch(Rectangle((-sw / 2, 0), sw, sh, fc="none", ec="0.5", lw=0.4, ls="--"))
    for _, x, y, dx, dy in rects(g):
        ax.add_patch(Rectangle((x, y), dx, dy, fc="black", ec="none"))


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


def main():
    data = {t: load(t) for t, _ in ANT}
    out = os.path.join(HERE, "cpw_antennas_A4.pdf")
    with PdfPages(out) as pdf:
        # ---- page 1: real size ----
        fig = plt.figure(figsize=(A4W * MM, A4H * MM))
        fig.text(0.5, 0.955, "CPW-fed monopoles on one sheet of A4 copy paper - REAL SIZE 1:1",
                 ha="center", fontsize=10, weight="bold")
        fig.text(0.5, 0.94, "Copper tape on ONE side only (no ground on the back). Black = copper. "
                 "Dashed = trim line. SMA at the bottom edge.", ha="center", fontsize=7)
        x = 25.0
        for (tag, name) in ANT:
            g = data[tag][0]["geometry"]
            sw, sh = g["SHEET_W"], g["SHEET_H"]
            y0 = 175.0
            ax = mm_axes(fig, x, y0, sw, sh, (-sw / 2, sw / 2), (0, sh))
            draw(ax, g)
            fig.text((x + sw / 2) / A4W, (y0 + sh + 6) / A4H, name, ha="center", fontsize=9, weight="bold")
            fig.text((x + sw / 2) / A4W, (y0 - 7) / A4H, f"{sw:.1f} x {sh:.1f} mm", ha="center", fontsize=7)
            x += sw + 35
        ruler(fig, 50, 150)
        fig.text(0.07, 0.42, "How to make it", fontsize=9, weight="bold")
        steps = ["1. Print this page at 100 % and check the ruler (100 mm).",
                 "2. Stick copper tape (conductive-adhesive type if possible) over each black area on the printed side.",
                 "   Make each antenna from ONE piece of tape: overlapping pieces with normal glue do not connect.",
                 "3. Cut through the tape along the black edges with a sharp scalpel and peel off the excess.",
                 "   The two CPW gaps beside the centre strip are 0.5 mm: cut both edges, lift the 0.5 mm sliver.",
                 "4. Trim the paper on the dashed line. Leave the bottom edge straight for the SMA.",
                 "5. Edge-mount SMA: centre pin on the strip, body/legs soldered to BOTH ground pads.",
                 "   Solder fast (paper burns): tin the tape first, then touch for ~1 s per joint.",
                 "6. Keep the area around the radiator free of metal/hands when measuring S11."]
        for k, s in enumerate(steps):
            fig.text(0.07, 0.40 - k * 0.018, s, fontsize=6.8)
        pdf.savefig(fig)
        plt.close(fig)

        # ---- page 2: dimensions + results ----
        fig = plt.figure(figsize=(A4W * MM, A4H * MM))
        fig.text(0.5, 0.96, "Dimensions (mm) and simulated performance (openEMS)", ha="center", fontsize=10, weight="bold")
        rows = [("Sheet / trim size", lambda g: f"{g['SHEET_W']:.2f} x {g['SHEET_H']:.2f}"),
                ("CPW centre strip width", lambda g: f"{g['W']:.2f}"),
                ("CPW gap (each side)", lambda g: f"{g['S']:.2f}"),
                ("Ground pads (each, W x H)", lambda g: f"{g['SHEET_W']/2 - g['W']/2 - g['S']:.2f} x {g['GND_H']:.2f}"),
                ("Ground top -> radiator gap", lambda g: f"{g['GAP_GP']:.2f}"),
                ("Strip length (bottom edge -> radiator)", lambda g: f"{g['Y_PAT']:.2f}"),
                ("Radiator W x H", lambda g: f"{g['PW']:.2f} x {g['PH']:.2f}"),
                ("Slot W x H (centred in x)", lambda g: f"{g['SW']:.2f} x {g['SH']:.2f}"),
                ("Radiator top bar (above slot)", lambda g: f"{g['TOP_BAR']:.2f}"),
                ("Slot bottom from bottom edge", lambda g: f"{g['Y_PAT'] + g['PH'] - g['TOP_BAR'] - g['SH']:.2f}")]
        fig.text(0.07, 0.92, "Parameter", fontsize=8, weight="bold")
        for j, (_, name) in enumerate(ANT):
            fig.text(0.55 + j * 0.2, 0.92, name, fontsize=8, weight="bold")
        for i, (lab, fn) in enumerate(rows):
            y = 0.90 - i * 0.02
            fig.text(0.07, y, lab, fontsize=7.5)
            for j, (tag, _) in enumerate(ANT):
                fig.text(0.55 + j * 0.2, y, fn(data[tag][0]["geometry"]), fontsize=7.5)
        y = 0.90 - len(rows) * 0.02 - 0.015
        res_rows = [("-10 dB band(s), GHz", lambda r, t: ", ".join(f"{a:.2f}-{b:.2f}" for a, b, _, _ in r["bands_lo_hi_min_dB"])),
                    ("Gain / efficiency @ design freq", lambda r, t: (lambda q: f"{q['gain_dBi']:.1f} dBi / {min(q['eff'],1)*100:.0f} %")(
                        r["gains"]["2.44" if t == "C" else "5.80"]))]
        for lab, fn in res_rows:
            fig.text(0.07, y, lab, fontsize=7.5)
            for j, (tag, _) in enumerate(ANT):
                fig.text(0.55 + j * 0.2, y, fn(data[tag][0], tag), fontsize=7.5)
            y -= 0.02
        fig.text(0.07, y - 0.005, "Model: copy paper 0.1 mm, er 3.0, tan d 0.06; copper as perfect conductor; "
                 "lumped 50-ohm feed at the edge (no SMA model).", fontsize=6.5, style="italic")
        for j, (tag, name) in enumerate(ANT):
            ax = fig.add_axes([0.1, 0.30 - j * 0.24, 0.82, 0.18])
            d = data[tag][1]
            ax.plot(d["f_GHz"], d["S11_dB"], "k")
            band = (2.4, 2.4835) if tag == "C" else (5.725, 5.875)
            ax.axvspan(*band, color="g", alpha=0.15)
            ax.axhline(-10, ls="--", c="gray", lw=0.8)
            ax.set_xlim((1.5, 4.0) if tag == "C" else (4.0, 7.0))
            ax.set_ylim(-30, 0)
            ax.set_ylabel("|S11| (dB)", fontsize=7)
            ax.set_title(f"{name} antenna", fontsize=8)
            ax.tick_params(labelsize=6)
            ax.grid(True, alpha=0.4)
        ax.set_xlabel("Frequency (GHz)", fontsize=7)
        pdf.savefig(fig)
        plt.close(fig)
    print("->", out)


if __name__ == "__main__":
    main()
