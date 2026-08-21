#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-$ROOT_DIR/local_results/ocr_quick}"
SAMPLES="$ROOT_DIR/data/raw/samples"
mkdir -p "$OUT"
run_pdf(){
  pdf="$1"; pages="$2"; name=$(basename "$pdf" .pdf)
  mkdir -p "$OUT/$name"
  start=$(date +%s)
  pdftoppm -f 1 -l "$pages" -r 200 -png "$pdf" "$OUT/$name/page" >/dev/null 2>&1
  for img in "$OUT/$name"/*.png; do
    base="${img%.png}"
    tesseract "$img" "$base" -l por --psm 6 >/dev/null 2>&1 || true
  done
  cat "$OUT/$name"/*.txt > "$OUT/$name.txt"
  end=$(date +%s)
  chars=$(wc -m < "$OUT/$name.txt")
  words=$(wc -w < "$OUT/$name.txt")
  arts=$(grep -Eio '\bArt\.?[[:space:]]*[0-9]+' "$OUT/$name.txt" | wc -l || true)
  resol=$(grep -Eio 'RESOLU[CÇ][AÃ]O' "$OUT/$name.txt" | wc -l || true)
  echo "$name,pages=$pages,seconds=$((end-start)),chars=$chars,words=$words,art_markers=$arts,resolucao_markers=$resol"
}
run_pdf "$SAMPLES/resolucao_089_2018.pdf" 3
run_pdf "$SAMPLES/resolucao_162_2016.pdf" 1
run_pdf "$SAMPLES/resolucao_186_2006.pdf" 3
