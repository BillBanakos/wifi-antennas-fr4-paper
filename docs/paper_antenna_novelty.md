# Single-sheet paper antennas: prior art and candidate novel ideas

Web scan done in the chat on 2026-11-16. "Not found" means not found in these searches, not proven
absent. Run a proper IEEE Xplore / Scopus search before claiming novelty.

## Already done (closest prior art)

| Topic | Reference |
|---|---|
| Origami reconfigurable paper antennas (dipole↔spiral, accordion, helix) — Georgakopoulos, Tentzeris et al. | US patent 9847570 "Morphing origami multi-functional and reconfigurable antennas" — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9847570 |
| A4 copy paper + conductive tape dipole + parasitic strip, pattern changes when folded (900 MHz) | D.-K. Park, "Design of a reconfigurable paper antenna using the origami method" — https://koreascience.kr/article/JAKO201631261653372.pdf |
| CPW-fed UWB monopole on general A4 paper + copper tape (measured) | D.-K. Park, 2021 — https://koreascience.or.kr/article/JAKO202107554625982.page |
| CMA + origami (waterbomb) multimode MIMO ring antenna — on 3 mm Rogers 5880, not paper | URSI NRSM 2021 — https://www.usnc-ursi-archive.org/nrsm/2021/papers/1068.pdf |
| Origami/kirigami switch between omni and unidirectional modes, 3.5 GHz | URSI NRSM 2021 — https://www.usnc-ursi-archive.org/nrsm/2021/papers/1118.pdf |
| Folded (origami) patch on paper, 63 % measured efficiency | HAL hal-02068187 — https://hal.archives-ouvertes.fr/hal-02068187 |
| Van Atta retrodirective UHF RFID tag on paper | Cespedes et al., RFID-TA 2012 — https://researchportal.hw.ac.uk/en/publications/a-retro-directive-uhf-rfid-tag-on-paper-substrate/ |
| Dual-band (3.6 / 5.8 GHz) SIW retrodirective reflector on paper | IMS 2013 — https://www.aminer.org/pub/56d851eddabfae2eee0a18ad |
| Inkjet-printed 30 GHz Van Atta humidity sensor | Hester & Tentzeris, IMS 2016 — https://tentzeris.ece.gatech.edu/ims16_hester.pdf |
| Cross-polarizing Van Atta chipless RFID, 2.5–3.0 GHz | MOTL 2025 — https://researchconnect.buffalo.edu/en/publications/retrodirective-chipless-rfid-with-cross-polarized-frequency-encod/ |
| RadioGami: copper-tape paper origami sensors, tunnel diodes, 45.73 m range | IMWUT 2025, arXiv:2506.06473 — https://arxiv.org/abs/2506.06473 |
| Flat-foldable kirigami chipless sensors from copper tape + paper | https://aminer.org/pub/6448f4647ae0ea000c44d31d |
| Pencil / ink-pen drawn paper metamaterials (absorber, polarization converter, coding metasurface) | Zhao et al., Opt. Mater. Express 2022 — https://www.optica.org/about/newsroom/news_releases/2022/october/researchers_develop_automatic_drawing_machine_for/ |
| Pencil-programmed RFID bits (patents) | US 7176900 — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7176900 |
| Mechanically reconfigurable chipless RFID | URSI GASS 2021 — https://www.ursi.org/proceedings/procGA21/papers/URSIGASS2021-Fr-D05-AM1-1.pdf |
| Paper CPW-fed dual-band WiFi monopole (basis of `04_paper_cpw_monopoles`) | Nair, Ray, Swaminathan, arXiv:2202.03266 |

## Candidate ideas (no direct match found)

1. **Fold-steered paper ESPAR, designed with characteristic modes (recommended).**
   Driven CPW monopole + copper-tape parasitic elements on fold-up flaps of the same sheet; fold
   angle sets coupling/reactance → continuous WiFi beam steering. CMA used to shape the flaps and
   explain which mode each fold angle excites. New vs. prior art: continuous steering vs. fold
   angle, CMA-guided design, dual-band WiFi, plain copy paper. Builds on the 3.5 GHz parasitic
   beam-steering work. Measurable with a VNA + simple pattern setup.
   *Next step proposed in the chat:* add two foldable parasitic flaps to the 2.4 GHz CPW monopole
   (variant C) and sweep fold angle 0–90° in openEMS.
2. **Fold-angle-encoded cross-polarizing retrodirective tag** on one sheet, read at 5.8 GHz by a
   Pluto+ ISAC node. Component-free, angle-independent readout, fold as the sensor. Highest
   novelty, highest risk (retrodirectivity under folding must be checked).
3. **Pencil-written / erasable mode selector**: graphite bridges across slots switch characteristic
   modes. Risk: graphite is resistive, may absorb rather than switch.
