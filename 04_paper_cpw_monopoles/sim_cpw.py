"""
CPW-fed slotted rectangular monopole (after Nair, Ray, Swaminathan, arXiv:2202.03266), copper tape on paper.
openEMS FDTD. Geometry (mm), origin at the bottom-centre of the sheet, y up:

  grounds   : two rectangles, y 0..GND_H, from the CPW gap outward to the sheet edge
  strip     : width W, y 0..Y_PAT
  pattern   : PW x PH rectangle starting at Y_PAT = GND_H + GAP_GP, with a SW x SH slot,
              slot top TOP_BAR below the pattern top
  port      : two 100-ohm lumped ports across the two CPW gaps at y = 0 (even mode) -> 50 ohm total

  python sim_cpw.py --tag A --s 0.2
  python sim_cpw.py --tag B --s 0.5 --scale 1.0
"""
import argparse
import json
import math
import os
import shutil

import numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import EPS0

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")


def geometry(a):
    sc = a.scale
    g = dict(W=a.w, S=a.s, GND_H=a.gnd_h, GAP_GP=a.gap_gp, PW=a.pw * sc, PH=a.ph * sc,
             SW=a.sw * sc, SH=a.sh * sc, TOP_BAR=a.top_bar * sc, SHEET_W=a.sheet_w, H=a.h, ER=a.er, TD=a.td)
    g["Y_PAT"] = g["GND_H"] + g["GAP_GP"]
    g["SHEET_H"] = g["Y_PAT"] + g["PH"] + a.top_margin
    return g


def rects(g):
    W, S, sw = g["W"], g["S"], g["SHEET_W"]
    xg = W / 2 + S
    yp, ph, pw = g["Y_PAT"], g["PH"], g["PW"]
    yst = yp + ph - g["TOP_BAR"] - g["SH"]           # slot bottom
    r = [("GndL", -sw / 2, 0, sw / 2 - xg, g["GND_H"]),
         ("GndR", xg, 0, sw / 2 - xg, g["GND_H"]),
         ("Strip", -W / 2, 0, W, yp),
         ("PatBottom", -pw / 2, yp, pw, yst - yp),
         ("PatTop", -pw / 2, yst + g["SH"], pw, g["TOP_BAR"]),
         ("PatLeft", -pw / 2, yst, (pw - g["SW"]) / 2, g["SH"]),
         ("PatRight", g["SW"] / 2, yst, (pw - g["SW"]) / 2, g["SH"])]
    return r


def run(g, sim_path, res=0.25, res_air=3.0, pad=45.0, do_run=True):
    h = g["H"]
    fdtd = openEMS(NrTS=300000, EndCriteria=1e-3)
    fdtd.SetGaussExcite(4.0e9, 3.0e9)
    fdtd.SetBoundaryCond(["PML_8"] * 6)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(1e-3)
    sw, sh = g["SHEET_W"], g["SHEET_H"]
    kappa = 2 * math.pi * 2.45e9 * EPS0 * g["ER"] * g["TD"]
    paper = csx.AddMaterial("paper", epsilon=g["ER"], kappa=kappa)
    paper.AddBox([-sw / 2, 0, 0], [sw / 2, sh, h], priority=0)
    cu = csx.AddMetal("copper")
    xs, ys = [-sw / 2, sw / 2], [0, sh]
    for _, x, y, dx, dy in rects(g):
        cu.AddBox([x, y, h], [x + dx, y + dy, h], priority=10)
        xs += [x, x + dx]
        ys += [y, y + dy]
    W, S = g["W"], g["S"]
    # even CPW mode: field points from the strip outward in both gaps
    pl = fdtd.AddLumpedPort(1, 100, [-W / 2 - S, 0, h], [-W / 2, 0, h], "x", -1.0, priority=5)
    pr = fdtd.AddLumpedPort(2, 100, [W / 2, 0, h], [W / 2 + S, 0, h], "x", 1.0, priority=5)
    xs += list(np.linspace(-W / 2 - S, -W / 2, 3)) + list(np.linspace(W / 2, W / 2 + S, 3))

    for ax, fine, outer in (("x", xs, (-sw / 2 - pad, sw / 2 + pad)), ("y", ys, (-pad, sh + pad))):
        mesh.AddLine(ax, sorted(set(np.round(fine, 4))))
        mesh.SmoothMeshLines(ax, res, 1.3)
        mesh.AddLine(ax, list(outer))
        mesh.SmoothMeshLines(ax, res_air, 1.3)
    mesh.AddLine("z", [0, h])
    mesh.SmoothMeshLines("z", h, 1.3)
    mesh.AddLine("z", [-pad, h + pad])
    mesh.SmoothMeshLines("z", res_air, 1.3)
    nf2ff = fdtd.CreateNF2FFBox(start=[-sw / 2 - 20, -20, -20], stop=[sw / 2 + 20, sh + 20, h + 20])
    n = [len(mesh.GetLines(a)) for a in "xyz"]
    print(f"  mesh {n} = {np.prod(n)/1e6:.2f} Mcells", flush=True)
    if do_run:
        if os.path.isdir(sim_path):
            shutil.rmtree(sim_path)
        os.makedirs(sim_path)
        fdtd.Run(sim_path, verbose=0, cleanup=True, numThreads=os.cpu_count())

    f = np.linspace(1.5e9, 7.0e9, 1101)
    pl.CalcPort(sim_path, f)
    pr.CalcPort(sim_path, f)
    zl, zr = pl.uf_tot / pl.if_tot, pr.uf_tot / pr.if_tot
    z = 1 / (1 / zl + 1 / zr)          # the two 100-ohm gap ports in parallel
    s11 = (z - 50) / (z + 50)
    pacc = np.real(pl.P_acc + pr.P_acc)
    gains = {}
    for f0 in (2.44e9, 5.8e9):
        r = nf2ff.CalcNF2FF(sim_path, f0, np.arange(0, 181, 3.0), np.arange(0, 360, 6.0),
                            center=[0, sh / 2 * 1e-3, h * 1e-3], outfile=f"ff_{f0/1e9:.2f}.h5", read_cached=False)
        k = int(np.argmin(abs(f - f0)))
        eff = float(r.Prad[0] / pacc[k])
        gains[f"{f0/1e9:.2f}"] = dict(Dmax_dBi=round(10 * np.log10(r.Dmax[0]), 2), eff=round(eff, 3),
                                      gain_dBi=round(10 * np.log10(r.Dmax[0] * eff), 2))
    return f, s11, z, gains


def bands(f, s11):
    db = 20 * np.log10(abs(s11))
    below = db < -10
    out, k = [], 0
    while k < len(f):
        if below[k]:
            j = k
            while j + 1 < len(f) and below[j + 1]:
                j += 1
            seg = slice(k, j + 1)
            m = k + int(np.argmin(db[seg]))
            out.append((round(f[k] / 1e9, 3), round(f[j] / 1e9, 3), round(f[m] / 1e9, 3), round(db[m], 1)))
            k = j + 1
        else:
            k += 1
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--w", type=float, default=3.0)
    ap.add_argument("--s", type=float, default=0.2)
    ap.add_argument("--gnd_h", type=float, default=12.3)
    ap.add_argument("--gap_gp", type=float, default=2.3)
    ap.add_argument("--pw", type=float, default=23.0)
    ap.add_argument("--ph", type=float, default=20.0)
    ap.add_argument("--sw", type=float, default=15.0)
    ap.add_argument("--sh", type=float, default=8.0)
    ap.add_argument("--top_bar", type=float, default=3.0)
    ap.add_argument("--scale", type=float, default=1.0, help="scales the radiating pattern + slot")
    ap.add_argument("--sheet_w", type=float, default=50.0)
    ap.add_argument("--top_margin", type=float, default=8.0)
    ap.add_argument("--h", type=float, default=0.1)
    ap.add_argument("--er", type=float, default=3.0)
    ap.add_argument("--td", type=float, default=0.06)
    ap.add_argument("--post", action="store_true", help="only post-process an existing run")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    g = geometry(a)
    print(f"=== {a.tag}: {json.dumps(g)}", flush=True)
    f, s11, z, gains = run(g, f"/tmp/cpw_runs/{a.tag}", do_run=not a.post)
    np.savetxt(os.path.join(OUT, f"S11_{a.tag}.csv"),
               np.c_[f / 1e9, 20 * np.log10(abs(s11)), z.real, z.imag], delimiter=",",
               header="f_GHz,S11_dB,ReZ,ImZ", comments="", fmt="%.5f")
    b = bands(f, s11)
    rec = dict(tag=a.tag, geometry=g, bands_lo_hi_min_dB=b, gains=gains)
    json.dump(rec, open(os.path.join(OUT, f"result_{a.tag}.json"), "w"), indent=2)
    print(f"RESULT {a.tag}: bands {b} | {gains}", flush=True)
