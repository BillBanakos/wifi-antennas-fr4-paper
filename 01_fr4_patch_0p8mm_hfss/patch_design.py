"""
Single source of truth for the patch geometry, shared by sim_patch.py (HFSS) and make_cnc.py (Gerbers).
All dimensions in mm, origin at the board centre, feed enters from the -y board edge.
"""
import math

F0 = 2.45e9
ER = 4.4            # FR4_epoxy (AEDT library): er 4.4, tand 0.02
H = 0.8
BOARD_X, BOARD_Y = 100.0, 75.0

# First HFSS run (inset microstrip, TL-model length 29.05 mm) resonated at 2.249 GHz.
# Scale the length by that ratio as the starting point for 2.45 GHz.
SIM_F_FIRST_RUN = 2.249e9


def patch_dims(f0=F0, er=ER, h=H):
    """Transmission-line model (Balanis)."""
    c = 299792458e3  # mm/s
    w = c / (2 * f0) * math.sqrt(2 / (er + 1))
    eeff = (er + 1) / 2 + (er - 1) / 2 * (1 + 12 * h / w) ** -0.5
    dl = 0.412 * h * (eeff + 0.3) * (w / h + 0.264) / ((eeff - 0.258) * (w / h + 0.8))
    l = c / (2 * f0 * math.sqrt(eeff)) - 2 * dl
    return w, l


def microstrip_width(z0=50.0, er=ER, h=H):
    """Hammerstad synthesis (W/h < 2 branch)."""
    a = z0 / 60 * math.sqrt((er + 1) / 2) + (er - 1) / (er + 1) * (0.23 + 0.11 / er)
    return h * 8 * math.exp(a) / (math.exp(2 * a) - 2)


W_TL, L_TL = patch_dims()
DEFAULT_LENGTH = round(L_TL * SIM_F_FIRST_RUN / F0, 2)   # ~26.67 mm
DEFAULT_INSET = 6.5      # first run gave ~29 ohm at 8.92 mm inset -> move toward edge
DEFAULT_NOTCH = 1.0
DEFAULT_GAP = 10.0


def add_args(ap):
    ap.add_argument("--gap", type=float, default=DEFAULT_GAP, help="pour clearance from patch and feed line, mm")
    ap.add_argument("--length", type=float, default=DEFAULT_LENGTH, help="patch length L (resonant, along y), mm")
    ap.add_argument("--width", type=float, default=round(W_TL, 2), help="patch width W (along x), mm")
    ap.add_argument("--inset", type=float, default=DEFAULT_INSET, help="inset depth, mm")
    ap.add_argument("--notch", type=float, default=DEFAULT_NOTCH, help="gap each side of the line inside the inset, mm")


def geometry(args):
    return dict(w=args.width, l=args.length, wf=microstrip_width(),
                y0=args.inset, notch=args.notch, gap=args.gap)


def describe(g):
    return (f"Patch W = {g['w']:.2f} mm, L = {g['l']:.2f} mm, h = {H} mm | 50-ohm line = {g['wf']:.2f} mm | "
            f"inset = {g['y0']} mm, notch = {g['notch']} mm | pour gap = {g['gap']} mm")


def patch_polygon(g):
    """Patch with inset notches + feed line, one closed contour (centred coords)."""
    w, l, wf, y0, n = g["w"], g["l"], g["wf"], g["y0"], g["notch"]
    yb, yp = -BOARD_Y / 2, -l / 2
    return [(-wf / 2, yb), (-wf / 2, yp + y0), (-wf / 2 - n, yp + y0), (-wf / 2 - n, yp),
            (-w / 2, yp), (-w / 2, yp + l), (w / 2, yp + l), (w / 2, yp),
            (wf / 2 + n, yp), (wf / 2 + n, yp + y0), (wf / 2, yp + y0), (wf / 2, yb)]


def pour_polygon(g):
    """Top-layer pour = board minus (patch clearance + feed channel). Simply connected U shape."""
    w, l, wf, gap = g["w"], g["l"], g["wf"], g["gap"]
    xb, yb = BOARD_X / 2, BOARD_Y / 2
    yp = -l / 2
    assert l / 2 + gap < yb and w / 2 + gap < xb and yp - gap > -yb, "gap too large for the board"
    return [(-xb, -yb), (-wf / 2 - gap, -yb), (-wf / 2 - gap, yp - gap), (-w / 2 - gap, yp - gap),
            (-w / 2 - gap, yp + l + gap), (w / 2 + gap, yp + l + gap), (w / 2 + gap, yp - gap),
            (wf / 2 + gap, yp - gap), (wf / 2 + gap, -yb), (xb, -yb), (xb, yb), (-xb, yb)]
