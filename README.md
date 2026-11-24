# wifi-antennas-fr4-paper — WiFi patch / array / paper antennas (Nov 2026)

Everything designed, simulated and generated in one long working chat with Claude:
FR4 patch experiments in HFSS, 1x2 inset-fed patch arrays at 2.45 and 5.8 GHz in openEMS,
CPW-fed monopoles on a single sheet of A4 copy paper, plus the fabrication outputs
(Gerbers for EasyTrace5000, 1:1 A4 print templates). The step-by-step story, all numbers and
the open issues are in [`CHAT_LOG.md`](CHAT_LOG.md).

## Layout

| Folder | What | Solver | Status |
|---|---|---|---|
| `01_fr4_patch_0p8mm_hfss/` | Single inset-fed 2.45 GHz patch, 0.8 mm FR4, 100 x 75 mm; effect of a top-layer copper pour (5 / 10 mm clearance); Gerbers | HFSS via PyAEDT | Last run 2.617 GHz (L 26.67 mm) — **retune before milling** (suggested L 28.0, inset 6.8, not run) |
| `02_array_2g45_1p6mm/` | 1x2 inset-fed array, 2.45 GHz, 1.6 mm FR4, 160 x 100 mm, corporate feed + 35 ohm lambda/4 | openEMS | Sim: 2.449 GHz, -29.4 dB, 6.3 dBi. **Built board measured 2.84–2.94 GHz — unresolved** |
| `02_array_2g45_1p6mm/legacy_hfss_quarterwave/` | First version: edge-fed with 127 ohm lambda/4 transformers (0.34 mm line, not hand-cuttable) | HFSS via PyAEDT | Superseded, run never completed |
| `03_array_5g8_1p6mm/` | 1x2 inset-fed array, 5.8 GHz, 1.6 mm FR4, 100 x 75 mm, **mitered feed bends** | openEMS | Sim: S11 < -10 dB over 5.70–6.12 GHz, 6.6 dBi |
| `04_paper_cpw_monopoles/` | Two CPW-fed slotted monopoles on one sheet of 0.1 mm copy paper (2.4 GHz and 5.8 GHz), copper tape, one side only | openEMS | Sim: 2.35–2.97 GHz / 5.16–6.04 GHz, ~2–2.6 dBi, ~94 % eff. Not built yet |
| `docs/` | Notes on paper substrates and a prior-art scan for a novel single-sheet paper antenna | — | — |

## Requirements

- **HFSS scripts** (`01_*`, legacy): Ansys Electronics Desktop (tested 2025.1) + `pip install ansys-aedt-core matplotlib numpy` (tested PyAEDT 1.10.0, Python 3.10). Run non-graphically from a terminal.
- **openEMS scripts** (`02_*`, `03_*`, `04_*`): openEMS + CSXCAD with Python bindings, `numpy`, `h5py`, `matplotlib`. (Built from source on Linux in the chat; on Windows use the official openEMS Windows build and set the DLL path.)
- **Print / Gerber / plot scripts**: only `numpy` + `matplotlib` (except `04_paper_cpw_monopoles/make_template.py`, which imports `sim_cpw.py` and therefore needs the openEMS bindings).

## Quick commands

```bash
# 01 — HFSS, 0.8 mm patch, with and without copper pour
cd 01_fr4_patch_0p8mm_hfss
python sim_patch.py --length 28.0 --inset 6.8 --gap 10 --cores 8
python plot_compare.py                       # results/summary.txt + PNGs
python make_cnc.py --length 28.0 --inset 6.8 --gap 10   # Gerbers in cnc/

# 02 — openEMS, 2.45 GHz array
cd 02_array_2g45_1p6mm
python sim_openems_array.py tune             # single element: L + inset to 2.45 GHz / 50 ohm
python sim_openems_array.py array            # full board, S11 + far field
python plot_array.py --src openems           # results_openems/array_report_A4.pdf
python make_print_array.py                   # print_array/: 1:1 A4 PDF + Gerbers

# 03 — same flow at 5.8 GHz (geometry in array_design.py)
# 04 — paper CPW monopoles
cd 04_paper_cpw_monopoles
python sim_cpw.py --tag C --s 0.5 --ph 24                       # 2.4 GHz antenna
python sim_cpw.py --tag G --s 0.5 --scale 0.42 --ph 24 --gnd_h 5.56 --gap_gp 2.0 --sheet_w 22.6 --top_margin 4   # 5.8 GHz
python make_template.py                      # cpw_antennas_A4.pdf
```

Print every A4 PDF at **100 % / Actual size** and check the 100 mm ruler.

## Not in the repo (see `.gitignore`)

HFSS projects and solver data (`*.aedt`, `*.aedtresults/`, `*.pyaedt/`), `.venv/`, logs, and
personal documents that happened to sit in the working folder.

## License

MIT — see [`LICENSE`](LICENSE). Simulation results are from the scripts here; measured data is noted only where stated in `CHAT_LOG.md`.
