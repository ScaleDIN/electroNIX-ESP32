#!/bin/bash
# fab.sh KICAD_DIR OUT_ZIP - Gerbers, drill files and pick-and-place for a board.
set -euo pipefail
dir=$1; zip=$(realpath -m "$2")
pcb="$dir/electroNIX-USB.kicad_pcb"
tmp=$(mktemp -d)
kicad-cli pcb export gerbers -o "$tmp/" --use-drill-file-origin \
  --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts "$pcb" >/dev/null
kicad-cli pcb export drill -o "$tmp/" --format excellon --excellon-separate-th \
  --drill-origin absolute --excellon-units mm "$pcb" >/dev/null
kicad-cli pcb export pos -o "$tmp/electroNIX-USB-pos.csv" --format csv --units mm --side both "$pcb" >/dev/null
rm -f "$zip"
(cd "$tmp" && zip -q -j "$zip" ./*)
rm -rf "$tmp"
unzip -l "$zip"
