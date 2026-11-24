"""
HFSS (non-graphical) for the 1x2 patch array in array_design.py, with auto-tuning:
  each iteration: build -> solve -> read S11
    L      <- L * f0 / 2.45 GHz                  (resonance)
    R_edge <- R_edge * Re(Zin) / 50              (transformer impedances / widths re-derived)
  stops when |f0 - 2.45 GHz| < 15 MHz and S11 < -15 dB, or after --iters.

Outputs in ./results_array:
  tuned.json (final dimensions, used by make_print_array.py), S11_iter<n>.s1p, S11_final.s1p,
  Gain_final.csv, S11.png, Gain.png, summary.txt

  python sim_array.py --cores 8
  python sim_array.py --iters 1 --length 28.5 --redge 250     # single run with your own values
"""
import argparse
import json
import os
import shutil

import numpy as np

import array_design as ad

try:
    from ansys.aedt.core import Hfss
except ImportError:
    from pyaedt import Hfss

OUT = os.path.join(ad.HERE, "results_array")
PAD = 35.0


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


def open_hfss(project, design, version):
    try:
        return Hfss(project=project, design=design, solution_type="Modal",
                    version=version, non_graphical=True, new_desktop=True)
    except TypeError:
        return Hfss(projectname=project, designname=design, solution_type="Modal",
                    specified_version=version, non_graphical=True, new_desktop_session=True)


def build(hfss, d):
    m = hfss.modeler
    m.model_units = "mm"
    bx, by, h = ad.BOARD_X, ad.BOARD_Y, ad.H
    m.create_box([-bx / 2, -by / 2, 0], [bx, by, h], name="Substrate", material="FR4_epoxy")
    gnd = m.create_rectangle("XY", [-bx / 2, -by / 2, 0], [bx, by], name="GND")

    sheets = [m.create_rectangle("XY", [x, y, h], [dx, dy], name=n) for n, x, y, dx, dy in ad.rectangles(d)]
    m.unite([s.name for s in sheets])
    hfss.assign_perfecte_to_sheets([gnd.name, sheets[0].name], "PEC_sheets")

    w50, yb = d["w50"], -by / 2
    port = m.create_polyline([[-w50 / 2, yb, 0], [w50 / 2, yb, 0], [w50 / 2, yb, h], [-w50 / 2, yb, h]],
                             cover_surface=True, close_surface=True, name="PortSheet")
    hfss.lumped_port(port.name, integration_line=[[0, yb, 0], [0, yb, h]], impedance=50, name="P1")

    air = m.create_box([-bx / 2 - PAD, -by / 2 - PAD, -PAD], [bx + 2 * PAD, by + 2 * PAD, h + 2 * PAD],
                       name="Air", material="air")
    hfss.assign_radiation_boundary_to_objects(air.name, "Rad")

    setup = hfss.create_setup("Setup1")
    setup.props["Frequency"] = "2.45GHz"
    setup.props["MaximumPasses"] = 20
    setup.props["MaximumDeltaS"] = 0.01
    setup.update()
    setup.create_frequency_sweep(unit="GHz", start_frequency=2.0, stop_frequency=3.0,
                                 num_of_freq_points=1001, name="Sweep",
                                 sweep_type="Interpolating", save_fields=False)
    hfss.insert_infinite_sphere(theta_start=-180, theta_stop=180, theta_step=2,
                                phi_start=0, phi_stop=90, phi_step=90, name="FF")


def solve(d, it, args):
    proj = os.path.join(ad.HERE, "patch_array.aedt")
    for p in (proj, proj + "results", proj + ".lock", proj + ".auto"):
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.isfile(p):
            os.remove(p)
    hfss = open_hfss(proj, "array1x2", args.version)
    try:
        build(hfss, d)
        hfss.save_project()
        hfss.analyze(cores=args.cores)
        s1p = os.path.join(OUT, f"S11_iter{it}.s1p")
        hfss.export_touchstone("Setup1", "Sweep", s1p)
        if True:
            hfss.post.create_report(
                expressions=["dB(GainTotal)", "dB(RealizedGainTotal)"],
                setup_sweep_name="Setup1 : LastAdaptive",
                variations={"Freq": ["2.45GHz"], "Theta": ["All"], "Phi": ["All"]},
                primary_sweep_variable="Theta", report_category="Far Fields",
                context="FF", plot_name="Gain_final")
            hfss.post.export_report_to_csv(OUT, "Gain_final")
        hfss.save_project()
    finally:
        hfss.release_desktop(True, True)
    return s1p


def metrics(s1p):
    f, s = read_s1p(s1p)
    db = 20 * np.log10(np.abs(s))
    i = int(np.argmin(db))
    z = 50 * (1 + s[i]) / (1 - s[i])
    lo, hi = i, i
    while lo > 0 and db[lo - 1] < -10:
        lo -= 1
    while hi < len(db) - 1 and db[hi + 1] < -10:
        hi += 1
    bw = (f[hi] - f[lo]) if db[i] < -10 else 0.0
    return f, db, f[i], db[i], z, bw


def plots(hist, gain_csv):
    import csv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for k, (f, db, lab) in enumerate(hist):
        ax.plot(f / 1e9, db, lw=2 if k == len(hist) - 1 else 0.8, label=lab)
    ax.axhline(-10, ls="--", c="gray", lw=0.8)
    ax.axvspan(2.4, 2.4835, color="g", alpha=0.1, label="WiFi 2.4 GHz band")
    ax.set_xlabel("Frequency (GHz)")
    ax.set_ylabel("|S11| (dB)")
    ax.grid(True, alpha=0.4)
    ax.legend(fontsize=8)
    ax.set_title("1x2 patch array, FR4 1.6 mm")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "S11.png"), dpi=150)

    if not os.path.exists(gain_csv):
        return None
    rows = list(csv.reader(open(gain_csv, newline="")))
    hdr = rows[0]
    ip = next(k for k, x in enumerate(hdr) if "Phi" in x)
    it = next(k for k, x in enumerate(hdr) if "Theta" in x)
    ig = next(k for k, x in enumerate(hdr) if "GainTotal" in x and "Realized" not in x)
    ir = next(k for k, x in enumerate(hdr) if "RealizedGainTotal" in x)
    dat = np.array([[float(r[ip]), float(r[it]), float(r[ig]), float(r[ir])] for r in rows[1:] if r])
    fig, axs = plt.subplots(1, 2, subplot_kw={"projection": "polar"}, figsize=(11, 5.5))
    for ax, phi, t in zip(axs, (0.0, 90.0), ("phi = 0 (XZ, array plane / H-plane)", "phi = 90 (YZ, E-plane)")):
        sel = np.isclose(dat[:, 0], phi)
        o = np.argsort(dat[sel, 1])
        ax.plot(np.radians(dat[sel, 1][o]), np.maximum(dat[sel, 2][o], -30), label="Gain")
        ax.plot(np.radians(dat[sel, 1][o]), np.maximum(dat[sel, 3][o], -30), "--", label="Realized gain")
        ax.set_theta_zero_location("N")
        ax.set_theta_direction(-1)
        ax.set_rlim(-30, 12)
        ax.set_title(t, pad=18)
        ax.legend(loc="lower right", fontsize=8)
    fig.suptitle("Gain (dBi) @ 2.45 GHz")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "Gain.png"), dpi=150)
    return dat[:, 2].max(), dat[:, 3].max()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=4)
    ap.add_argument("--length", type=float, default=None)
    ap.add_argument("--redge", type=float, default=None)
    ap.add_argument("--cores", type=int, default=4)
    ap.add_argument("--version", default=None)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    d = ad.design(length=args.length, redge=args.redge)
    hist, log = [], []
    for it in range(1, args.iters + 1):
        ad.check(d)
        print(f"=== iteration {it}: L = {d['L']:.2f} mm, R_edge = {d['R_edge']:.0f} ohm, "
              f"Zt1 = {d['Z_t1']:.1f} ohm (w {d['w_t1']:.2f} mm) ===")
        s1p = solve(d, it, args)
        f, db, f0, smin, z, bw = metrics(s1p)
        line = (f"iter {it}: L {d['L']:.2f} mm, R_edge {d['R_edge']:.0f} ohm -> f0 {f0/1e9:.4f} GHz, "
                f"S11 {smin:.1f} dB, Zin {z.real:.1f}{z.imag:+.1f}j ohm, BW {bw/1e6:.0f} MHz")
        print(line)
        log.append(line)
        hist.append((f, db, f"iter {it}: L {d['L']:.2f}, f0 {f0/1e9:.3f} GHz"))
        done = abs(f0 - ad.F0) < 15e6 and smin < -15
        if done or it == args.iters:
            break
        r_new = float(np.clip(d["R_edge"] * z.real / 50, 80, 500)) if smin > -15 else d["R_edge"]
        d = ad.design(length=round(d["L"] * f0 / ad.F0, 2), width=d["W"], redge=r_new)

    shutil.copy(s1p, os.path.join(OUT, "S11_final.s1p"))
    g = plots(hist, os.path.join(OUT, "Gain_final.csv"))

    d.update(f0_sim_GHz=round(f0 / 1e9, 4), S11_min_dB=round(smin, 2), BW10_MHz=round(bw / 1e6, 1))
    if g:
        d.update(peak_gain_dBi=round(g[0], 2), peak_realized_gain_dBi=round(g[1], 2))
    with open(ad.TUNED, "w") as fh:
        json.dump(d, fh, indent=2)
    summary = "\n".join(log + [f"FINAL: f0 {f0/1e9:.4f} GHz, S11 {smin:.1f} dB, -10 dB BW {bw/1e6:.0f} MHz"
                               + (f", peak gain {g[0]:.2f} dBi, realized {g[1]:.2f} dBi" if g else "")]
                        + [f"{k:34s} {v}" for k, v in ad.table(d)])
    print(summary)
    open(os.path.join(OUT, "summary.txt"), "w").write(summary + "\n")
    print("next: python make_print_array.py")


if __name__ == "__main__":
    main()
