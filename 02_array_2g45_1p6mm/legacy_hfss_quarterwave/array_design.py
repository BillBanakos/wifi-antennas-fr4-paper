"""
1x2 edge-fed patch array @ 2.45 GHz, FR4 1.6 mm, board 160 x 100 mm, no copper pour.
Corporate feed with quarter-wave transformers (no inset):

   patch edge (R_edge) --[lambda/4, Zt1 = sqrt(R_edge*50)]-- 50 ohm --+
                                                                      +-- T (25 ohm) --[lambda/4, 35.36 ohm]-- 50 ohm -- port
   patch edge (R_edge) --[lambda/4, Zt1]--------------------- 50 ohm --+

Single source of geometry for the HFSS script, the Gerbers and the A4 print.
Units mm, origin = board centre, array axis = x, feed enters from the -y edge.
"""
import json
import math
import os

import numpy as np

_trapz = getattr(np, "trapezoid", None) or np.trapz   # numpy 1.x / 2.x

F0 = 2.45e9
ER = 4.4                   # FR4_epoxy (AEDT library), tand 0.02
H = 1.6
T_CU = 0.035
BOARD_X, BOARD_Y = 160.0, 100.0
C_MM = 299792458e3         # mm/s
LAM0 = C_MM / F0           # 122.4 mm

SPACING = 80.0             # element spacing (0.65 lambda0)
Y_PATCH_BOTTOM = 6.0       # y of the fed (bottom) radiating edge
Y_JUNCTION = -20.0         # centreline of the horizontal 50-ohm line

HERE = os.path.dirname(os.path.abspath(__file__))
TUNED = os.path.join(HERE, "results_array", "tuned.json")


# ---------------- microstrip (Hammerstad) ----------------
def ms_eeff(w, er=ER, h=H):
    u = w / h
    e = (er + 1) / 2 + (er - 1) / 2 * (1 + 12 / u) ** -0.5
    if u < 1:
        e += (er - 1) / 2 * 0.04 * (1 - u) ** 2
    return e


def ms_width(z0, er=ER, h=H):
    a = z0 / 60 * math.sqrt((er + 1) / 2) + (er - 1) / (er + 1) * (0.23 + 0.11 / er)
    u = 8 * math.exp(a) / (math.exp(2 * a) - 2)
    if u > 2:
        b = 377 * math.pi / (2 * z0 * math.sqrt(er))
        u = 2 / math.pi * (b - 1 - math.log(2 * b - 1) + (er - 1) / (2 * er) * (math.log(b - 1) + 0.39 - 0.61 / er))
    return u * h


def quarter_wave(w, f=F0):
    return C_MM / f / math.sqrt(ms_eeff(w)) / 4


# ---------------- patch ----------------
def patch_dims(f0=F0, er=ER, h=H):
    w = C_MM / (2 * f0) * math.sqrt(2 / (er + 1))
    eeff = (er + 1) / 2 + (er - 1) / 2 * (1 + 12 * h / w) ** -0.5
    dl = 0.412 * h * (eeff + 0.3) * (w / h + 0.264) / ((eeff - 0.258) * (w / h + 0.8))
    return w, C_MM / (2 * f0 * math.sqrt(eeff)) - 2 * dl


def _j0(x):
    tau = np.linspace(0, np.pi, 801)
    return _trapz(np.cos(np.outer(x, np.sin(tau))), tau, axis=1) / np.pi


def edge_resistance(w, l, f0=F0):
    """Balanis: R_in = 1 / (2 (G1 + G12))."""
    k0 = 2 * math.pi * f0 / C_MM
    th = np.linspace(1e-6, math.pi - 1e-6, 4001)
    a = (np.sin(k0 * w / 2 * np.cos(th)) / np.cos(th)) ** 2 * np.sin(th) ** 3
    g1 = _trapz(a, th) / (120 * math.pi ** 2)
    g12 = _trapz(a * _j0(k0 * l * np.sin(th)), th) / (120 * math.pi ** 2)
    return 1 / (2 * (g1 + g12))


# ---------------- full design ----------------
def design(length=None, width=None, redge=None, spacing=SPACING):
    w0, l0 = patch_dims()
    W = width or round(w0, 2)
    L = length or round(l0, 2)
    R = redge or edge_resistance(W, L)
    zt1 = math.sqrt(R * 50)
    zt2 = math.sqrt(25 * 50)
    d = dict(W=W, L=L, R_edge=R, spacing=spacing, h=H, er=ER,
             Z_t1=zt1, w_t1=ms_width(zt1), Z_t2=zt2, w_t2=ms_width(zt2), w50=ms_width(50))
    d["l_t1"] = quarter_wave(d["w_t1"])
    d["l_t2"] = quarter_wave(d["w_t2"])
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


def load_design(**over):
    """Tuned design from the last HFSS run if it exists, else analytic."""
    if os.path.exists(TUNED) and not any(over.values()):
        with open(TUNED) as fh:
            return json.load(fh)
    return design(**over)


def rectangles(d):
    """List of (name, x0, y0, dx, dy) copper rectangles on the top layer (overlaps are intended)."""
    W, L, s, w50 = d["W"], d["L"], d["spacing"], d["w50"]
    yb, yp, yj = -BOARD_Y / 2, Y_PATCH_BOTTOM, Y_JUNCTION
    r = []
    for i, xc in enumerate((-s / 2, s / 2)):
        y_t1 = yp - d["l_t1"]
        r += [(f"Patch{i}", xc - W / 2, yp, W, L),
              (f"Trans{i}", xc - d["w_t1"] / 2, y_t1, d["w_t1"], d["l_t1"]),
              (f"Feed{i}", xc - w50 / 2, yj - w50 / 2, w50, y_t1 - (yj - w50 / 2))]
    y_t2 = yj - w50 / 2 - d["l_t2"]
    r += [("Hbar", -s / 2 - w50 / 2, yj - w50 / 2, s + w50, w50),
          ("Trans35", -d["w_t2"] / 2, y_t2, d["w_t2"], d["l_t2"]),
          ("Main50", -w50 / 2, yb, w50, y_t2 - yb)]
    return r


def check(d):
    top = Y_PATCH_BOTTOM + d["L"]
    assert top < BOARD_Y / 2 - 5, "patch too close to top edge"
    assert d["spacing"] / 2 + d["W"] / 2 < BOARD_X / 2 - 5, "patch too close to side edge"
    assert Y_PATCH_BOTTOM - d["l_t1"] > Y_JUNCTION + d["w50"], "transformer runs into junction"
    assert Y_JUNCTION - d["w50"] / 2 - d["l_t2"] > -BOARD_Y / 2 + 3, "35-ohm section hits board edge"


def table(d):
    rows = [("Board", f"{BOARD_X:.0f} x {BOARD_Y:.0f} mm, FR4 er {ER}, h {H} mm, 35 um Cu, full ground on bottom"),
            ("Patch W x L (x2)", f"{d['W']:.2f} x {d['L']:.2f} mm"),
            ("Element spacing (centre-centre)", f"{d['spacing']:.2f} mm ({d['spacing']/LAM0:.2f} lambda0)"),
            ("Patch edge resistance (model)", f"{d['R_edge']:.0f} ohm"),
            ("lambda/4 transformer at patch", f"Z {d['Z_t1']:.1f} ohm: w {d['w_t1']:.2f} mm, l {d['l_t1']:.2f} mm"),
            ("50-ohm lines", f"w {d['w50']:.2f} mm"),
            ("lambda/4 transformer at T", f"Z {d['Z_t2']:.2f} ohm: w {d['w_t2']:.2f} mm, l {d['l_t2']:.2f} mm"),
            ("Patch fed edge / T-line centre", f"y = {Y_PATCH_BOTTOM:+.1f} / {Y_JUNCTION:+.1f} mm (board centre = 0)")]
    return rows


if __name__ == "__main__":
    d = load_design()
    check(d)
    for k, v in table(d):
        print(f"{k:34s} {v}")
    print()
    for n, x, y, dx, dy in rectangles(d):
        print(f"{n:8s} x0 {x:8.3f}  y0 {y:8.3f}  dx {dx:7.3f}  dy {dy:7.3f}")
