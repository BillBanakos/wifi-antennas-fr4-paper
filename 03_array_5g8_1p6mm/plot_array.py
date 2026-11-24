"""
Plots for the 1x2 array after sim_array.py. Works on whatever is in ./results_array
(also partial runs). Writes PNGs + one printable A4 PDF report.

  python plot_array.py            # -> results_array/array_report_A4.pdf + PNGs
  python plot_array.py --show     # also open the figures on screen
"""
import argparse
import csv
import glob
import json
import os

import numpy as np
import matplotlib

import array_design as ad

OUT = os.path.join(ad.HERE, "results_array")
A4 = (8.27, 11.69)


def read_s1p(path):
    scale_map = {"HZ": 1, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}
    scale, fmt, f, s = 1e9, "MA", [], []
    for line in open(path):
        line = line.split("!")[0].strip()
        if not line or line.startswith("["):
            continue
        if line.startswith("#"):
            for tok in line[1:].upper().split():
                scale = scale_map.get(tok, scale)
                fmt = tok if tok in ("MA", "DB", "RI") else fmt
            continue
        v = [float(x) for x in line.split()]
        if len(v) >= 3:
            f.append(v[0] * scale)
            a, b = v[1], v[2]
            s.append(complex(a, b) if fmt == "RI" else
                     (a if fmt == "MA" else 10 ** (a / 20)) * np.exp(1j * np.radians(b)))
    return np.array(f), np.array(s)


def s_metrics(f, s):
    db = 20 * np.log10(np.abs(s))
    i = int(np.argmin(db))
    lo = hi = i
    while lo > 0 and db[lo - 1] < -10:
        lo -= 1
    while hi < len(db) - 1 and db[hi + 1] < -10:
        hi += 1
    return db, i, ((f[hi] - f[lo]) if db[i] < -10 else 0.0)


def read_gain(path):
    rows = list(csv.reader(open(path, newline="")))
    hdr = rows[0]
    ip = next(k for k, x in enumerate(hdr) if "phi" in x.lower())
    it = next(k for k, x in enumerate(hdr) if "theta" in x.lower())
    lo = [x.lower() for x in hdr]
    ig = next(k for k, x in enumerate(lo) if "gain" in x and "realized" not in x)
    ir = next(k for k, x in enumerate(lo) if "realized" in x)
    return np.array([[float(r[ip]), float(r[it]), float(r[ig]), float(r[ir])] for r in rows[1:] if r])


def smith_grid(ax):
    t = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(t), np.sin(t), "k", lw=0.8)
    for r in (0.2, 0.5, 1, 2, 5):
        c, rad = r / (1 + r), 1 / (1 + r)
        ax.plot(c + rad * np.cos(t), rad * np.sin(t), color="0.75", lw=0.5)
    for x in (0.2, 0.5, 1, 2, 5):
        for sgn in (1, -1):
            z = 1j * sgn * x + np.linspace(0, 50, 2000)
            g = (z - 1) / (z + 1)
            ax.plot(g.real, g.imag, color="0.75", lw=0.5)
    ax.plot([-1, 1], [0, 0], color="0.75", lw=0.5)
    ax.set_aspect("equal")
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_axis_off()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--src", choices=["hfss", "openems"], default="hfss")
    args = ap.parse_args()
    global OUT
    if args.src == "openems":
        OUT = os.path.join(ad.HERE, "results_openems")
    if not args.show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    pat = "S11_iter*.s1p" if args.src == "hfss" else "S11_patch_iter*.s1p"
    iters = sorted(glob.glob(os.path.join(OUT, pat)),
                   key=lambda p: int("".join(c for c in os.path.basename(p) if c.isdigit()) or 0))
    if args.src == "openems" and os.path.exists(os.path.join(OUT, "S11_array.s1p")):
        iters.append(os.path.join(OUT, "S11_array.s1p"))
    if not iters:
        raise SystemExit(f"no S11_iter*.s1p in {OUT} yet - run sim_array.py first")
    final = iters[-1]
    f, s = read_s1p(final)
    db, i0, bw = s_metrics(f, s)
    z = 50 * (1 + s) / (1 - s)
    i245 = int(np.argmin(abs(f - ad.F0)))
    tj = os.path.join(OUT, "tuned.json")
    tuned = json.load(open(tj)) if os.path.exists(tj) else None
    gain_csv = os.path.join(OUT, "Gain_final.csv" if args.src == "hfss" else "pattern_array.csv")
    gd = read_gain(gain_csv) if os.path.exists(gain_csv) else None

    figs = []

    # ---- page 1: S11, Zin, Smith ----
    fig = plt.figure(figsize=A4)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1, 1.4], hspace=0.45, wspace=0.3)
    ax = fig.add_subplot(gs[0, :])
    for p in iters[:-1]:
        ff, ss = read_s1p(p)
        ax.plot(ff / 1e9, 20 * np.log10(abs(ss)), lw=0.7, alpha=0.6,
                label=os.path.basename(p).replace("S11_", "").replace(".s1p", ""))
    ax.plot(f / 1e9, db, "k", lw=1.8, label="final")
    ax.axhline(-10, ls="--", c="gray", lw=0.8)
    ax.axvspan(5.725, 5.875, color="g", alpha=0.12, label="WiFi 5.8 GHz (5.725-5.875)")
    ax.plot(f[i0] / 1e9, db[i0], "ro")
    ax.annotate(f"{f[i0]/1e9:.3f} GHz\n{db[i0]:.1f} dB", (f[i0] / 1e9, db[i0]), (10, 5),
                textcoords="offset points", fontsize=8)
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("|S11| (dB)")
    ax.set_title("Return loss")
    ax.grid(True, alpha=0.4)
    ax.legend(fontsize=7, ncol=3)

    ax = fig.add_subplot(gs[1, :])
    ax.plot(f / 1e9, z.real, label="Re(Zin)")
    ax.plot(f / 1e9, z.imag, label="Im(Zin)")
    ax.axhline(50, ls="--", c="gray", lw=0.8)
    ax.axhline(0, c="k", lw=0.5)
    ax.set_ylim(-150, 200)
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("Ohm")
    ax.set_title("Input impedance (final)")
    ax.grid(True, alpha=0.4)
    ax.legend(fontsize=8)

    ax = fig.add_subplot(gs[2, 0])
    smith_grid(ax)
    ax.plot(s.real, s.imag, "b", lw=1)
    ax.plot(s[i245].real, s[i245].imag, "ro", ms=4)
    ax.set_title("Smith chart (red = 5.8 GHz)", fontsize=9)

    ax = fig.add_subplot(gs[2, 1])
    ax.set_axis_off()
    txt = [f"f0 (S11 min)      {f[i0]/1e9:.4f} GHz",
           f"S11 min           {db[i0]:.2f} dB",
           f"-10 dB bandwidth  {bw/1e6:.1f} MHz",
           f"S11 @ 5.8 GHz     {db[i245]:.2f} dB",
           f"Zin @ 5.8 GHz     {z[i245].real:.1f} {z[i245].imag:+.1f}j ohm",
           f"iterations        {len(iters)}"]
    if tuned:
        txt += ["", f"L {tuned['L']:.2f} mm, W {tuned['W']:.2f} mm"]
        if "y0" in tuned:
            txt += [f"inset {tuned['y0']:.2f} mm, notch {tuned['notch']:.2f} mm"]
        if "w_t1" in tuned:
            txt += [f"Zt1 {tuned['Z_t1']:.1f} ohm: w {tuned['w_t1']:.2f}, l {tuned['l_t1']:.2f} mm"]
        txt += [f"Zt2 {tuned['Z_t2']:.1f} ohm: w {tuned['w_t2']:.2f}, l {tuned['l_t2']:.2f} mm"]
        if "rad_eff" in tuned:
            txt += [f"rad. efficiency {tuned['rad_eff']*100:.0f} %, Dmax {tuned['Dmax_dBi']} dBi"]
    if gd is not None:
        txt += ["", f"peak gain          {gd[:,2].max():.2f} dBi",
                f"peak realized gain {gd[:,3].max():.2f} dBi"]
    ax.text(0, 1, "\n".join(txt), va="top", family="monospace", fontsize=8)
    fig.suptitle(f"1x2 patch array 5.8 GHz, FR4 1.6 mm, 100 x 75 mm - S-parameters ({args.src})", fontsize=11)
    figs.append(("S11", fig))

    # ---- page 2: gain ----
    if gd is not None:
        fig = plt.figure(figsize=A4)
        gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.3)
        cuts = ((0.0, "phi = 0 (XZ, array axis / H-plane)"), (90.0, "phi = 90 (YZ, E-plane)"))
        for k, (phi, title) in enumerate(cuts):
            sel = np.isclose(gd[:, 0], phi)
            th, g, gr = gd[sel, 1], gd[sel, 2], gd[sel, 3]
            o = np.argsort(th)
            th, g, gr = th[o], g[o], gr[o]
            ax = fig.add_subplot(gs[0, k], projection="polar")
            ax.plot(np.radians(th), np.maximum(g, -30), label="Gain")
            ax.plot(np.radians(th), np.maximum(gr, -30), "--", label="Realized")
            ax.set_theta_zero_location("N")
            ax.set_theta_direction(-1)
            ax.set_rlim(-30, 12)
            ax.set_title(title, fontsize=9, pad=15)
            ax.legend(fontsize=7, loc="lower right")
            ax = fig.add_subplot(gs[1, k])
            ax.plot(th, g, label="Gain")
            ax.plot(th, gr, "--", label="Realized")
            gmax = g.max()
            above = th[g >= gmax - 3]
            hpbw = above.max() - above.min() if len(above) else 0
            ax.axhline(gmax - 3, ls=":", c="gray")
            ax.set_xlim(-180, 180)
            ax.set_ylim(-30, 12)
            ax.set_xlabel("Theta (deg)")
            ax.set_ylabel("dBi")
            ax.set_title(f"{title}\nmax {gmax:.2f} dBi, HPBW ~ {hpbw:.0f} deg", fontsize=8)
            ax.grid(True, alpha=0.4)
            ax.legend(fontsize=7)
        fig.suptitle("Radiation pattern @ 5.8 GHz", fontsize=11)
        figs.append(("Gain", fig))

    pdf_path = os.path.join(OUT, "array_report_A4.pdf")
    with PdfPages(pdf_path) as pdf:
        for name, fig in figs:
            fig.savefig(os.path.join(OUT, f"plot_{name}.png"), dpi=150)
            pdf.savefig(fig)
    print("\n".join(txt))
    print(f"-> {pdf_path}")
    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
