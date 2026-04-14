#!/usr/bin/env python3
"""
kicad_to_diylc.py
Convert a KiCad .kicad_pcb file to a DIYLC v5 .diy file.

Outputs:
  - A BlankBoard sized to the Edge.Cuts outline
  - A SolderPad + Label for every W* footprint

Usage:
    python3 kicad_to_diylc.py PrincetonReverbUpdate.kicad_pcb

Output file: PrincetonReverbUpdate_wires.diy (same directory as input)
"""

import re
import sys
import uuid
from pathlib import Path

# --- Config ---
MARGIN_IN        = 0.5    # canvas margin around the board (inches)
GRID_IN          = 0.1    # snap grid (inches)
PAD_COLOR        = "CC6600"
LABEL_COLOR      = "000000"
LABEL_SIZE       = 11     # font pt
LABEL_OFFSET_IN  = 0.1   # label sits this far above the pad
BOARD_COLOR      = "ccffcc"
BOARD_BORDER     = "ada47d"
BOARD_COORD      = "b6b6b6"


def parse_edge_cuts_rect(pcb_text):
    """Return (x1_mm, y1_mm, x2_mm, y2_mm) of the Edge.Cuts gr_rect, or None."""
    m = re.search(
        r'\(gr_rect\s*\(start ([\d.\-]+) ([\d.\-]+)\)\s*\(end ([\d.\-]+) ([\d.\-]+)\)'
        r'.*?"Edge\.Cuts"',
        pcb_text, re.DOTALL
    )
    if m:
        return tuple(float(v) for v in m.groups())
    return None


def parse_w_footprints(pcb_text):
    """Return sorted list of (ref, x_mm, y_mm, value) for all W* footprints."""
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
        results.append((
            ref,
            float(at_m.group(1)),
            float(at_m.group(2)),
            val_m.group(1) if val_m else ref,
        ))
    results.sort(key=lambda r: int(r[0][1:]))
    return results


def snap(val_in):
    return round(round(val_in / GRID_IN) * GRID_IN, 4)


def mm_to_in(mm):
    return mm / 25.4


def place(mm_val, origin_mm):
    """Convert KiCad mm coord to snapped DIYLC inches relative to origin."""
    return snap(mm_to_in(mm_val - origin_mm) + MARGIN_IN)


def build_diy(board_rect_mm, footprints, canvas_w, canvas_h):
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

    # --- BlankBoard ---
    if board_rect_mm:
        bx1_mm = min(board_rect_mm[0], board_rect_mm[2])
        by1_mm = min(board_rect_mm[1], board_rect_mm[3])
        bx2_mm = max(board_rect_mm[0], board_rect_mm[2])
        by2_mm = max(board_rect_mm[1], board_rect_mm[3])
        ox_mm, oy_mm = bx1_mm, by1_mm

        bx1 = snap(MARGIN_IN)
        by1 = snap(MARGIN_IN)
        bx2 = snap(mm_to_in(bx2_mm - bx1_mm) + MARGIN_IN)
        by2 = snap(mm_to_in(by2_mm - by1_mm) + MARGIN_IN)
        b_w_mm = round(bx2_mm - bx1_mm, 4)
        b_h_mm = round(by2_mm - by1_mm, 4)

        ln('    <diylc.boards.BlankBoard>')
        ln(f'      <id>{uuid.uuid4()}</id>')
        ln('      <n>PCB</n>')
        ln('      <alphaPercent><value>100</value></alphaPercent>')
        ln('      <value></value>')
        ln('      <controlPoints>')
        ln(f'        <point x="{bx1}" y="{by1}"/>')
        ln(f'        <point x="{bx2}" y="{by2}"/>')
        ln('      </controlPoints>')
        ln(f'      <firstPoint x="{bx1}" y="{by1}"/>')
        ln(f'      <secondPoint x="{bx2}" y="{by2}"/>')
        ln(f'      <boardColor hex="{BOARD_COLOR}"/>')
        ln(f'      <borderColor hex="{BOARD_BORDER}"/>')
        ln(f'      <coordinateColor hex="{BOARD_COORD}"/>')
        ln('      <xType>Numbers</xType>')
        ln('      <coordinateOrigin>Top_Left</coordinateOrigin>')
        ln('      <coordinateDisplay>One_Side</coordinateDisplay>')
        ln('      <yType>Letters</yType>')
        ln(f'      <length value="{b_w_mm}" unit="mm"/>')
        ln(f'      <width value="{b_h_mm}" unit="mm"/>')
        ln('      <mode>TwoPoints</mode>')
        ln('      <boardUndersideDisplay>NONE</boardUndersideDisplay>')
        ln('      <undersideOffset value="0.1" unit="in"/>')
        ln('      <undersideTransparency>true</undersideTransparency>')
        ln('      <type>SQUARE</type>')
        ln('    </diylc.boards.BlankBoard>')
    else:
        ox_mm = min(f[1] for f in footprints)
        oy_mm = min(f[2] for f in footprints)

    # --- Wire points ---
    for ref, kx, ky, val in footprints:
        px = place(kx, ox_mm)
        py = place(ky, oy_mm)
        ly = round(py - LABEL_OFFSET_IN, 4)

        ln(f'    <diylc.connectivity.SolderPad>')
        ln(f'      <id>{uuid.uuid4()}</id>')
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
        ln(f'      <id>{uuid.uuid4()}</id>')
        ln(f'      <n>L{ref[1:]}</n>')
        ln(f'      <point x="{px}" y="{ly}"/>')
        ln(f'      <text>{val}</text>')
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

    board_rect = parse_edge_cuts_rect(pcb_text)
    if board_rect:
        x1, y1, x2, y2 = board_rect
        print(f"Board outline: {abs(x2-x1):.2f} x {abs(y2-y1):.2f} mm")
    else:
        print("Warning: no Edge.Cuts rect found — board outline omitted")

    footprints = parse_w_footprints(pcb_text)
    if not footprints:
        print("No W* footprints found.")
        sys.exit(1)
    print(f"Found {len(footprints)} W* footprints")

    if board_rect:
        x1 = min(board_rect[0], board_rect[2])
        y1 = min(board_rect[1], board_rect[3])
        x2 = max(board_rect[0], board_rect[2])
        y2 = max(board_rect[1], board_rect[3])
        canvas_w = round(snap(mm_to_in(x2 - x1) + MARGIN_IN * 2) + 0.2, 1)
        canvas_h = round(snap(mm_to_in(y2 - y1) + MARGIN_IN * 2) + 0.2, 1)
    else:
        xs = [f[1] for f in footprints]
        ys = [f[2] for f in footprints]
        canvas_w = round(snap(mm_to_in(max(xs) - min(xs)) + MARGIN_IN * 2) + 0.5, 1)
        canvas_h = round(snap(mm_to_in(max(ys) - min(ys)) + MARGIN_IN * 2) + 0.5, 1)

    diy_xml = build_diy(board_rect, footprints, canvas_w, canvas_h)

    out_path = pcb_path.with_name(pcb_path.stem + '_wires.diy')
    out_path.write_text(diy_xml, encoding='utf-8')
    print(f"Written: {out_path}")
    print(f"Canvas:  {canvas_w} x {canvas_h} inches")


if __name__ == '__main__':
    main()
