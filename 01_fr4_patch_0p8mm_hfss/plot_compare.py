"""
Compare bare vs copper-pour patch: S11 + gain cuts.
Reads ./results/S11_*.s1p and ./results/Gain_*.csv, writes PNGs + summary.txt to ./results.

  python plot_compare.py
"""
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
CASES = {"bare": "no copper", "copper": "copper pour"}


def read_s1p(path):
    scale_map = {"HZ": 1, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9}
    scale, fmt = 1e9, "MA"
    f, s = [], []
    with open(path) as fh:
        for line in fh:
            line = line.split("!")[0].strip()
            if not line or line.startswith("["):
                continue
            if line.startswith("#"):
                for tok in line[1:].upper().split():
                    if tok in scale_map:
                        scale = scale_map[tok]
                    if tok in ("MA", "DB", "RI"):
                        fmt = tok
                continue
            v = [float(x) for x in line.split()]
            if len(v) < 3:
                continue
            f.append(v[0] * scale)
            a, b = v[1], v[2]
            if fmt == "RI":
                s.append(complex(a, b))
            elif fmt == "MA":
                s.append(a * np.exp(1j * np.radians(b)))
            else:
                s.append(10 ** (a / 20) * np.exp(1j * np.radians(b)))
    return np.array(f), np.array(s)


def s11_metrics(f, s):
    db = 20 * np.log10(np.abs(s))
    i = int(np.argmin(db))
    bw = None
    if db[i] < -10:
        lo = i
        while lo > 0 and db[lo - 1] < -10:
            lo -= 1
        hi = i
        while hi < len(db) - 1 and db[hi + 1] < -10:
            hi += 1
        bw = f[hi] - f[lo]
    return f[i], db[i], bw, db


def read_gain(path):
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))
    hdr = [h.strip() for h in rows[0]]

    def col(key, exclude=None):
        for k, h in enumerate(hdr):
            if key in h and (exclude is None or exclude not in h):
                return k
        raise KeyError(f"{key} not in {hdr}")

    ip, it = col("Phi"), col("Theta")
    ig, ir = col("GainTotal", exclude="Realized"), col("RealizedGainTotal")
    data = np.array([[float(r[ip]), float(r[it]), float(r[ig]), float(r[ir])]
                     for r in rows[1:] if r])
    return data  # phi, theta, gain_dB, realized_dB


def main():
    have = [c for c in CASES if os.path.exists(os.path.join(OUT, f"S11_{c}.s1p"))]
    lines = []

    # ---- S11 ----
    fig, ax = plt.subplots(figsize=(8, 4.5))
    res = {}
    for c in have:
        f, s = read_s1p(os.path.join(OUT, f"S11_{c}.s1p"))
        fr, smin, bw, db = s11_metrics(f, s)
        res[c] = fr
        ax.plot(f / 1e9, db, label=f"{CASES[c]}  (f0 = {fr/1e9:.4f} GHz, {smin:.1f} dB)")
        bw_txt = f"{bw/1e6:.1f} MHz" if bw else "n/a (S11 > -10 dB)"
        lines.append(f"[{c}] f_res = {fr/1e9:.4f} GHz, S11_min = {smin:.2f} dB, -10 dB BW = {bw_txt}")
    if len(res) == 2:
        lines.append(f"Delta f_res (copper - bare) = {(res['copper'] - res['bare'])/1e6:+.1f} MHz")
    ax.axhline(-10, ls="--", c="gray", lw=0.8)
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("|S11| (dB)")
    ax.grid(True, alpha=0.4)
    ax.legend()
    ax.set_title("Patch on 0.8 mm FR4: effect of top-layer copper pour")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "S11_compare.png"), dpi=150)

    # ---- gain cuts ----
    fig, axs = plt.subplots(1, 2, subplot_kw={"projection": "polar"}, figsize=(11, 5.5))
    titles = {0.0: "phi = 0 deg (XZ, H-plane)", 90.0: "phi = 90 deg (YZ, E-plane)"}
    for c in have:
        p = os.path.join(OUT, f"Gain_{c}.csv")
        if not os.path.exists(p):
            continue
        d = read_gain(p)
        for ax, phi in zip(axs, (0.0, 90.0)):
            sel = np.isclose(d[:, 0], phi)
            th, g = d[sel, 1], d[sel, 2]
            o = np.argsort(th)
            ax.plot(np.radians(th[o]), np.maximum(g[o], -30), label=CASES[c])
        lines.append(f"[{c}] peak GainTotal = {d[:,2].max():.2f} dBi, "
                     f"peak RealizedGain = {d[:,3].max():.2f} dBi (@ 2.45 GHz)")
    for ax, phi in zip(axs, (0.0, 90.0)):
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(-30, 10)
        ax.set_title(titles[phi], pad=18)
        ax.legend(loc="lower right", fontsize=8)
    fig.suptitle("Gain (dBi) @ 2.45 GHz")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "Gain_compare.png"), dpi=150)

    txt = "\n".join(lines)
    print(txt)
    with open(os.path.join(OUT, "summary.txt"), "w") as fh:
        fh.write(txt + "\n")


if __name__ == "__main__":
    main()
