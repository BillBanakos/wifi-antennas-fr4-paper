"""
Inset-microstrip-fed patch @ 2.45 GHz on 0.8 mm FR4, board 100 x 75 mm.

  case 'bare'   : only the patch + feed line on the top layer
  case 'copper' : floating copper pour on the top layer, GAP mm clearance around
                  the patch AND on both sides of the feed line

Runs HFSS non-graphically and exports to ./results:
  S11_<case>.s1p        (interpolating sweep 2-3 GHz, 1 MHz step)
  Gain_<case>.csv       (GainTotal / RealizedGainTotal, phi = 0 and 90 deg cuts @ 2.45 GHz)

Usage:
  python sim_patch.py                       # both cases, gap 10 mm
  python sim_patch.py --case copper --gap 10 --length 26.67 --inset 6.5 --cores 8
"""
import argparse
import math
import os
import shutil

try:
    from ansys.aedt.core import Hfss
except ImportError:  # older installs
    from pyaedt import Hfss

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")

import patch_design as pd
from patch_design import H, BOARD_X, BOARD_Y

PAD = 35.0          # air padding (> lambda0/4 = 30.6 mm)


def open_hfss(project, design, version, new_desktop=True):
    try:
        return Hfss(project=project, design=design, solution_type="Modal",
                    version=version, non_graphical=True, new_desktop=new_desktop)
    except TypeError:  # pyaedt < 0.9 argument names
        return Hfss(projectname=project, designname=design, solution_type="Modal",
                    specified_version=version, non_graphical=True,
                    new_desktop_session=new_desktop)


def build(hfss, case, g):
    w, l, wf, y0, notch, gap = g['w'], g['l'], g['wf'], g['y0'], g['notch'], g['gap']
    m = hfss.modeler
    m.model_units = "mm"
    yb = -BOARD_Y / 2          # board edge where the port sits
    yp = -l / 2                # radiating edge facing the feed

    m.create_box([-BOARD_X / 2, yb, 0], [BOARD_X, BOARD_Y, H], name="Substrate", material="FR4_epoxy")
    gnd = m.create_rectangle("XY", [-BOARD_X / 2, yb, 0], [BOARD_X, BOARD_Y], name="GND")

    # patch with inset notches, united with the feed line
    patch = m.create_rectangle("XY", [-w / 2, yp, H], [w, l], name="Patch")
    slot = m.create_rectangle("XY", [-wf / 2 - notch, yp, H], [wf + 2 * notch, y0], name="Inset")
    m.subtract(patch, slot, keep_originals=False)
    line = m.create_rectangle("XY", [-wf / 2, yb, H], [wf, (yp + y0) - yb], name="Feed")
    m.unite([patch.name, line.name])

    pec = [gnd.name, patch.name]
    if case == "copper":
        cu = m.create_rectangle("XY", [-BOARD_X / 2, yb, H], [BOARD_X, BOARD_Y], name="CopperPour")
        cut_p = m.create_rectangle("XY", [-w / 2 - gap, yp - gap, H], [w + 2 * gap, l + 2 * gap], name="CutPatch")
        cut_f = m.create_rectangle("XY", [-wf / 2 - gap, yb, H], [wf + 2 * gap, yp - yb], name="CutFeed")
        m.subtract(cu, [cut_p, cut_f], keep_originals=False)
        pec.append(cu.name)   # floating (not tied to ground)
    hfss.assign_perfecte_to_sheets(pec, "PEC_sheets")

    # lumped port: vertical sheet at the board edge, ground -> line
    port = m.create_polyline([[-wf / 2, yb, 0], [wf / 2, yb, 0], [wf / 2, yb, H], [-wf / 2, yb, H]],
                             cover_surface=True, close_surface=True, name="PortSheet")
    iline = [[0, yb, 0], [0, yb, H]]
    try:
        hfss.lumped_port(port.name, integration_line=iline, impedance=50, name="P1")
    except TypeError:
        hfss.lumped_port(port.name, integration_line=iline, impedance=50, portname="P1")

    air = m.create_box([-BOARD_X / 2 - PAD, yb - PAD, -PAD],
                       [BOARD_X + 2 * PAD, BOARD_Y + 2 * PAD, H + 2 * PAD], name="Air", material="air")
    hfss.assign_radiation_boundary_to_objects(air.name, "Rad")

    setup = hfss.create_setup("Setup1")
    setup.props["Frequency"] = "2.45GHz"
    setup.props["MaximumPasses"] = 20
    setup.props["MaximumDeltaS"] = 0.01
    setup.update()
    try:
        setup.create_frequency_sweep(unit="GHz", start_frequency=2.0, stop_frequency=3.0,
                                     num_of_freq_points=1001, name="Sweep",
                                     sweep_type="Interpolating", save_fields=False)
    except TypeError:
        setup.create_frequency_sweep("GHz", 2.0, 3.0, 1001, "Sweep", sweep_type="Interpolating")

    try:  # PyAEDT >= 1.x
        hfss.insert_infinite_sphere(theta_start=-180, theta_stop=180, theta_step=2,
                                    phi_start=0, phi_stop=90, phi_step=90, name="FF")
    except TypeError:  # older PyAEDT (x = theta, y = phi)
        hfss.insert_infinite_sphere(x_start=-180, x_stop=180, x_step=2,
                                    y_start=0, y_stop=90, y_step=90, name="FF")


def export(hfss, case):
    os.makedirs(OUT, exist_ok=True)
    hfss.export_touchstone("Setup1", "Sweep", os.path.join(OUT, f"S11_{case}.s1p"))

    name = f"Gain_{case}"
    hfss.post.create_report(
        expressions=["dB(GainTotal)", "dB(RealizedGainTotal)"],
        setup_sweep_name="Setup1 : LastAdaptive",
        variations={"Freq": ["2.45GHz"], "Theta": ["All"], "Phi": ["All"]},
        primary_sweep_variable="Theta",
        report_category="Far Fields",
        context="FF",
        plot_name=name,
    )
    hfss.post.export_report_to_csv(OUT, name)


def run(case, args, g):
    proj = os.path.join(HERE, f"patch_{case}.aedt")
    for p in (proj, proj + "results", proj + ".lock", proj + ".auto"):   # fresh project every run
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.isfile(p):
            os.remove(p)

    hfss = open_hfss(proj, f"patch_{case}", args.version)
    try:
        build(hfss, case, g)
        hfss.save_project()
        try:
            hfss.analyze(cores=args.cores)
        except TypeError:
            hfss.analyze(num_cores=args.cores)
        export(hfss, case)
        hfss.save_project()
    finally:
        hfss.release_desktop(True, True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=["bare", "copper", "both"], default="both")
    pd.add_args(ap)
    ap.add_argument("--cores", type=int, default=4)
    ap.add_argument("--version", default=None, help="e.g. 2025.1 (default: latest installed)")
    args = ap.parse_args()
    g = pd.geometry(args)

    print(pd.describe(g))
    cases = ["bare", "copper"] if args.case == "both" else [args.case]
    for c in cases:
        print(f"=== running {c} ===")
        run(c, args, g)
    print(f"done -> {OUT}")
