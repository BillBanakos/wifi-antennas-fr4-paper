"""
openEMS (FDTD) simulation of the inset-fed 1x2 array from array_design.py.

  python sim_openems_array.py tune      # single element (half board): tune L and inset to 2.45 GHz / 50 ohm
  python sim_openems_array.py array     # full 160 x 100 mm array with the tuned element: S11 + far field

Mesh: 0.4 mm in the board plane over the board, 4 cells through the 1.6 mm FR4,
graded to 2 mm in air, metal edges on mesh lines, PML_8, NF2FF box inside the air.
Writes results_openems/{tuned.json, S11_*.csv, pattern_*.csv, summary.txt}.
"""
import argparse
import json
import math
import os
import shutil
import sys

import numpy as np

import array_design as ad

from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import EPS0

OUT = os.path.join(ad.HERE, "results_openems")
TMP = os.path.join(os.environ.get("OEMS_TMP", "/tmp"), "oems_runs58")
F0, FC = 5.8e9, 2.0e9
TAN_D = 0.02
RES_FINE, RES_AIR, PAD, NF_PAD = 0.4, 2.0, 40.0, 15.0


def smooth_two_level(mesh, axis, fine_lines, fine_res, outer, air_res):
    mesh.AddLine(axis, sorted(set(np.round(fine_lines, 4))))
    mesh.SmoothMeshLines(axis, fine_res, 1.3)
    mesh.AddLine(axis, list(outer))
    mesh.SmoothMeshLines(axis, air_res, 1.3)


def model(d, mode, sim_path, end_db=-40, run=True):
    h = ad.H
    by = ad.BOARD_Y
    if mode == "patch":
        bx = d["spacing"]
        yp = ad.Y_PATCH_BOTTOM
        polys = None
        rects = ad.patch_rects(d, 0.0) + [("Feed", -d["w50"] / 2, -by / 2, d["w50"], yp + d["y0"] + by / 2)]
    else:
        bx = ad.BOARD_X
        rects = None
        polys = ad.shapes(d)

    fdtd = openEMS(NrTS=200000, EndCriteria=10 ** (end_db / 10))
    fdtd.SetGaussExcite(F0, FC)
    fdtd.SetBoundaryCond(["PML_8"] * 6)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(1e-3)

    kappa = 2 * math.pi * F0 * EPS0 * ad.ER * TAN_D
    fr4 = csx.AddMaterial("FR4", epsilon=ad.ER, kappa=kappa)
    fr4.AddBox([-bx / 2, -by / 2, 0], [bx / 2, by / 2, h], priority=0)
    gnd = csx.AddMetal("GND")
    gnd.AddBox([-bx / 2, -by / 2, 0], [bx / 2, by / 2, 0], priority=10)
    top = csx.AddMetal("TOP")
    xs, ys = [-bx / 2, bx / 2], [-by / 2, by / 2]
    if rects:
        for _, x, y, dx, dy in rects:
            top.AddBox([x, y, h], [x + dx, y + dy, h], priority=10)
            xs += [x, x + dx]
            ys += [y, y + dy]
    else:
        for _, pts in polys:
            p = np.array(pts).T
            top.AddPolygon(p, "z", h, priority=10)
            xs += list(p[0])
            ys += list(p[1])

    w50 = d["w50"]
    port = fdtd.AddLumpedPort(1, 50, [-w50 / 2, -by / 2, 0], [w50 / 2, -by / 2, h], "z", 1.0, priority=5)

    smooth_two_level(mesh, "x", xs, RES_FINE, (-bx / 2 - PAD, bx / 2 + PAD), RES_AIR)
    smooth_two_level(mesh, "y", ys, RES_FINE, (-by / 2 - PAD, by / 2 + PAD), RES_AIR)
    smooth_two_level(mesh, "z", np.linspace(0, h, 5), h / 4, (-PAD, h + PAD), RES_AIR)

    nf2ff = fdtd.CreateNF2FFBox(start=[-bx / 2 - NF_PAD, -by / 2 - NF_PAD, -NF_PAD],
                                stop=[bx / 2 + NF_PAD, by / 2 + NF_PAD, h + NF_PAD])
    n = [len(mesh.GetLines(a)) for a in "xyz"]
    print(f"  mesh {n[0]} x {n[1]} x {n[2]} = {np.prod(n)/1e6:.2f} Mcells", flush=True)

    if run:
        if os.path.isdir(sim_path):
            shutil.rmtree(sim_path)
        os.makedirs(sim_path)
        fdtd.Run(sim_path, verbose=0, cleanup=True, numThreads=os.cpu_count())
    return port, nf2ff


def s_params(port, sim_path):
    f = np.linspace(5.0e9, 6.6e9, 1601)
    port.CalcPort(sim_path, f)
    s11 = port.uf_ref / port.uf_inc
    zin = port.uf_tot / port.if_tot
    return f, s11, zin, port


def metrics(f, s11, zin):
    db = 20 * np.log10(np.abs(s11))
    i = int(np.argmin(db))
    lo = hi = i
    while lo > 0 and db[lo - 1] < -10:
        lo -= 1
    while hi < len(db) - 1 and db[hi + 1] < -10:
        hi += 1
    bw = (f[hi] - f[lo]) if db[i] < -10 else 0.0
    # resonance = peak of Re(Zin) near the dip (robust even when badly matched)
    k = int(np.argmax(zin.real))
    return dict(f_s11min=f[i], s11min=db[i], bw10=bw, f_res=f[k], r_res=zin.real[k],
                z_at_min=zin[i], i=i)


def save_s(path, f, s11, zin):
    with open(path.replace(".csv", ".s1p"), "w") as fh:
        fh.write("! openEMS\n# GHZ S MA R 50\n")
        for a, b in zip(f, s11):
            fh.write(f"{a/1e9:.6f} {abs(b):.6f} {np.degrees(np.angle(b)):.4f}\n")
    np.savetxt(path, np.c_[f / 1e9, 20 * np.log10(abs(s11)), np.degrees(np.angle(s11)), zin.real, zin.imag],
               delimiter=",", header="f_GHz,S11_dB,S11_deg,ReZ,ImZ", comments="", fmt="%.6f")


def tune(args):
    d = ad.design(length=args.length, inset=args.inset, notch=args.notch)
    log = []
    for it in range(1, args.iters + 1):
        print(f"=== tune iter {it}: L {d['L']:.2f} mm, inset {d['y0']:.2f} mm", flush=True)
        sp = os.path.join(TMP, f"patch_it{it}")
        port, _ = model(d, "patch", sp)
        f, s11, zin, _ = s_params(port, sp)
        m = metrics(f, s11, zin)
        save_s(os.path.join(OUT, f"S11_patch_iter{it}.csv"), f, s11, zin)
        line = (f"iter {it}: L {d['L']:.2f}, inset {d['y0']:.2f} -> S11min {m['s11min']:.1f} dB @ "
                f"{m['f_s11min']/1e9:.4f} GHz, Zin there {m['z_at_min'].real:.1f}{m['z_at_min'].imag:+.1f}j ohm, "
                f"BW {m['bw10']/1e6:.0f} MHz")
        print(line, flush=True)
        log.append(line)
        if abs(m["f_s11min"] - F0) < 10e6 and m["s11min"] < -20:
            break
        if it == args.iters:
            break
        L_new = round(d["L"] * m["f_s11min"] / F0, 2)
        r = m["z_at_min"].real if abs(m["z_at_min"].imag) < 25 else 50.0
        c2 = math.cos(math.pi * d["y0"] / d["L"]) ** 2 * 50 / max(r, 5)
        c2 = min(max(c2, 0.05), 0.99)
        y_new = round(L_new / math.pi * math.acos(math.sqrt(c2)), 2)
        d = ad.design(length=L_new, width=d["W"], inset=y_new, notch=d["notch"])
    d.update(f0_element_GHz=round(m["f_s11min"] / 1e9, 4), S11_element_dB=round(m["s11min"], 2),
             BW10_element_MHz=round(m["bw10"] / 1e6, 1))
    json.dump(d, open(os.path.join(OUT, "tuned.json"), "w"), indent=2)
    open(os.path.join(OUT, "summary_tune.txt"), "w").write("\n".join(log) + "\n")
    print("\n".join(log))


PAT = {}


def pattern(d, port, nf2ff, sp, f, s11):
    """Full sphere for Prad / Dmax / efficiency, then the two cuts."""
    i245 = int(np.argmin(abs(f - F0)))
    port.CalcPort(sp, np.array([F0]))
    p_acc = float(np.real(port.P_acc[0]))
    full = nf2ff.CalcNF2FF(sp, F0, np.arange(0.0, 181.0, 2.0), np.arange(0.0, 360.0, 4.0),
                           center=[0, 0, ad.H * 1e-3], outfile="nf2ff_full.h5", read_cached=False)
    dmax, prad = float(full.Dmax[0]), float(full.Prad[0])
    emax = float(np.max(full.E_norm[0]))
    eff = prad / p_acc
    mism = 1 - abs(s11[i245]) ** 2
    theta = np.arange(-180.0, 181.0, 2.0)
    cut = nf2ff.CalcNF2FF(sp, F0, theta, [0.0, 90.0], center=[0, 0, ad.H * 1e-3], outfile="nf2ff_cut.h5", read_cached=False)
    rows = []
    for k, phi in enumerate((0.0, 90.0)):
        e = cut.E_norm[0][:, k] / emax
        dd = 20 * np.log10(np.maximum(e, 1e-6)) + 10 * np.log10(dmax)
        g = dd + 10 * np.log10(eff)
        rows += [(phi, a, b, c, c2) for a, b, c, c2 in zip(theta, dd, g, g + 10 * np.log10(mism))]
    np.savetxt(os.path.join(OUT, "pattern_array.csv"), np.array(rows), delimiter=",",
               header="phi,theta,Directivity_dBi,Gain_dBi,RealizedGain_dBi", comments="", fmt="%.3f")
    PAT.update(Dmax_dBi=round(10 * np.log10(dmax), 2), rad_eff=round(eff, 3),
               gain_dBi=round(10 * np.log10(dmax * eff), 2),
               realized_gain_dBi=round(10 * np.log10(dmax * eff * mism), 2))
    print(f"  Prad {prad:.3e} W, P_acc {p_acc:.3e} W, Dmax {10*np.log10(dmax):.2f} dBi, eff {eff*100:.1f} %")


def array(args):
    d = json.load(open(os.path.join(OUT, "tuned.json")))
    if args.length:
        d = {**d, **ad.design(length=args.length, width=d["W"], inset=args.inset or d["y0"], notch=d["notch"])}
    if args.no_run:
        port, nf2ff = model(d, "array", os.path.join(TMP, "array"), run=False)
        f, s11, zin, port = s_params(port, os.path.join(TMP, "array"))
        pattern(d, port, nf2ff, os.path.join(TMP, "array"), f, s11)
        print(PAT)
        return
    sp = os.path.join(TMP, "array")
    print(f"=== array: L {d['L']:.2f}, inset {d['y0']:.2f}", flush=True)
    port, nf2ff = model(d, "array", sp)
    f, s11, zin, port = s_params(port, sp)
    m = metrics(f, s11, zin)
    save_s(os.path.join(OUT, "S11_array.csv"), f, s11, zin)
    i245 = int(np.argmin(abs(f - F0)))
    pattern(d, port, nf2ff, sp, f, s11)
    d.update(f0_array_GHz=round(m["f_s11min"] / 1e9, 4), S11_array_dB=round(m["s11min"], 2),
             BW10_array_MHz=round(m["bw10"] / 1e6, 1), S11_at_f0_dB=round(20 * np.log10(abs(s11[i245])), 2),
             **PAT)
    json.dump(d, open(os.path.join(OUT, "tuned.json"), "w"), indent=2)
    eff = d["rad_eff"]
    s = (f"array: S11min {m['s11min']:.1f} dB @ {m['f_s11min']/1e9:.4f} GHz, BW {m['bw10']/1e6:.0f} MHz, "
         f"S11@5.8 {d['S11_at_f0_dB']} dB, Dmax {d['Dmax_dBi']} dBi, eff {eff*100:.0f} %, gain {d['gain_dBi']} dBi")
    open(os.path.join(OUT, "summary_array.txt"), "w").write(s + "\n")
    print(s)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["tune", "array"])
    ap.add_argument("--iters", type=int, default=4)
    ap.add_argument("--length", type=float, default=None)
    ap.add_argument("--inset", type=float, default=None)
    ap.add_argument("--notch", type=float, default=1.0)
    ap.add_argument("--no-run", action="store_true", help="array: only post-process the last run")
    ap.add_argument("--res", type=float, default=RES_FINE, help="in-board mesh resolution, mm")
    a = ap.parse_args()
    RES_FINE = a.res
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    tune(a) if a.mode == "tune" else array(a)
