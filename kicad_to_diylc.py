#!/usr/bin/env python3
"""
kicad_to_diylc.py
Convert W* wire-point footprints from a KiCad .kicad_pcb file to a DIYLC v5 .diy file.

Usage:
    python3 kicad_to_diylc.py PrincetonReverbUpdate.kicad_pcb

Output:
    PrincetonReverbUpdate_wires.diy  (same directory as input)

Each W* footprint becomes a solder pad + label showing "Wn: Value".
Coordinates are preserved relative to the bottom-left of the W* bounding box,
snapped to a 0.1" grid, with a 0.5" margin.
"""

import re
import sys
import uuid
from pathlib import Path

# --- Config ---
MARGIN_IN   = 0.5    # canvas margin in inches
GRID_IN     = 0.1    # snap grid in inches
PAD_COLOR   = "CC6600"
LABEL_COLOR = "000000"
LABEL_SIZE  = 11     # font pt
LABEL_OFFSET_IN = 0.1  # label sits this far above the pad


def parse_w_footprints(pcb_text):
    """Extract (ref, x_mm, y_mm, value) for all W* footprints."""
    results = []
    for fp in pcb_text.split('\n\t(footprint ')[1:]:
        ref_m = re.search(r'\(property "Reference" "(W\d+)"', fp)
        if not ref_m:
            continue
        ref   = ref_m.group(1)
        at_m  = re.search(r'\t\(at ([\d.\-]+) ([\d.\-]+)', fp)
        val_m = re.search(r'\(property "Value" "([^"]*)"', fp)
        if not at_m:
            continue
        x   = float(at_m.group(1))
        y   = float(at_m.group(2))
        val = val_m.group(1) if val_m else ref
        results.append((ref, x, y, val))
    results.sort(key=lambda r: int(r[0][1:]))
    return results


def snap(val_in):
    return round(round(val_in / GRID_IN) * GRID_IN, 4)


def mm_to_in(mm):
    return mm / 25.4


def build_diy(footprints, canvas_w, canvas_h):
    lines = []

    def ln(s=""):
        lines.append(s)

    ln('<?xml version="1.0" encoding="UTF-8" ?>')
    ln('<project>')
    ln('  <fileVersion>')
    ln('    <major>5</major>')
    ln('    <minor>13</minor>')
    ln('    <build>0</build>')
    ln('  </fileVersion>')
    ln('  <title>Princeton Reverb Wire Points</title>')
    ln('  <author></author>')
    ln(f'  <width value="{canvas_w}" unit="in"/>')
    ln(f'  <height value="{canvas_h}" unit="in"/>')
    ln('  <gridSpacing value="0.1" unit="in"/>')
    ln('  <dotSpacing>1</dotSpacing>')
    ln('  <components>')

    for ref, px, py, val in footprints:
        label_text = f'{val}'
        pad_id = str(uuid.uuid4())
        lbl_id = str(uuid.uuid4())
        ly = round(py - LABEL_OFFSET_IN, 4)

        ln(f'    <diylc.connectivity.SolderPad>')
        ln(f'      <id>{pad_id}</id>')
        ln(f'      <n>{ref}</n>')
        ln(f'      <alphaPercent><value>100</value></alphaPercent>')
        ln(f'      <size value="0.09" unit="in"/>')
        ln(f'      <color hex="{PAD_COLOR}"/>')
        ln(f'      <point x="{px}" y="{py}"/>')
        ln(f'      <type>ROUND</type>')
        ln(f'      <holeSize value="0.8" unit="mm"/>')
        ln(f'      <layer>_1</layer>')
        ln(f'      <holeType>NTPH</holeType>')
        ln(f'    </diylc.connectivity.SolderPad>')

        ln(f'    <diylc.misc.Label>')
        ln(f'      <id>{lbl_id}</id>')
        ln(f'      <n>L{ref[1:]}</n>')
        ln(f'      <point x="{px}" y="{ly}"/>')
        ln(f'      <text>{label_text}</text>')
        ln(f'      <font name="Dialog" size="{LABEL_SIZE}" style="0"/>')
        ln(f'      <color hex="{LABEL_COLOR}"/>')
        ln(f'      <horizontalAlignment>CENTER</horizontalAlignment>')
        ln(f'      <verticalAlignment>CENTER</verticalAlignment>')
        ln(f'      <orientation>DEFAULT</orientation>')
        ln(f'    </diylc.misc.Label>')

    ln('  </components>')
    ln('  <groups/>')
    ln('  <groupsEx/>')
    ln('  <lockedLayers/>')
    ln('  <lockedComponents/>')
    ln('  <hiddenLayers/>')
    ln('  <font name="Dialog" size="14" style="0"/>')
    ln('</project>')

    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python3 {sys.argv[0]} <file.kicad_pcb>")
        sys.exit(1)

    pcb_path = Path(sys.argv[1])
    if not pcb_path.exists():
        print(f"Error: {pcb_path} not found")
        sys.exit(1)

    pcb_text = pcb_path.read_text(encoding='utf-8')
    footprints = parse_w_footprints(pcb_text)

    if not footprints:
        print("No W* footprints found.")
        sys.exit(1)

    print(f"Found {len(footprints)} W* footprints")

    # Convert mm -> inches, origin at bounding box min, add margin, snap to grid
    xs_mm = [f[1] for f in footprints]
    ys_mm = [f[2] for f in footprints]
    x_min_mm, y_min_mm = min(xs_mm), min(ys_mm)

    placed = []
    for ref, kx, ky, val in footprints:
        px = snap(mm_to_in(kx - x_min_mm) + MARGIN_IN)
        py = snap(mm_to_in(ky - y_min_mm) + MARGIN_IN)
        placed.append((ref, px, py, val))

    canvas_w = round(snap(mm_to_in(max(xs_mm) - x_min_mm) + MARGIN_IN * 2) + 0.5, 1)
    canvas_h = round(snap(mm_to_in(max(ys_mm) - y_min_mm) + MARGIN_IN * 2) + 0.5, 1)

    diy_xml = build_diy(placed, canvas_w, canvas_h)

    out_path = pcb_path.with_name(pcb_path.stem + '_wires.diy')
    out_path.write_text(diy_xml, encoding='utf-8')
    print(f"Written: {out_path}")
    print(f"Canvas:  {canvas_w} x {canvas_h} inches")


if __name__ == '__main__':
    main()
