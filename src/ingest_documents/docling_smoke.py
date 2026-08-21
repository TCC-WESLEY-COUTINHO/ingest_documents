#!/usr/bin/env python3
"""Smoke benchmark for OCR + structural chunking on UFPI resolution PDFs.

Usage:
  pip install -r requirements.txt
  # Requires Tesseract CLI + Portuguese traineddata (por)
  python -m ingest_documents.docling_smoke arquivo1.pdf arquivo2.pdf

Outputs one directory per PDF under ./local_results/docling_smoke/ by default.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from pathlib import Path

from docling.chunking import HybridChunker
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import OcrMode, PdfPipelineOptions, TesseractCliOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


def build_converter() -> DocumentConverter:
    # UFPI has image-only PDFs, so for this smoke test we force OCR on the full page.
    # Use Portuguese Tesseract data. Change to lang=["auto"] if preferred/available.
    project_root = Path(__file__).resolve().parents[2]
    local_tessdata = project_root / ".tessdata"
    if (local_tessdata / "por.traineddata").exists():
        os.environ.setdefault("TESSDATA_PREFIX", str(local_tessdata))

    tesseract_cmd = shutil.which("tesseract")
    windows_tesseract = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tesseract_cmd is None and windows_tesseract.exists():
        tesseract_cmd = str(windows_tesseract)

    ocr = TesseractCliOcrOptions(
        lang=["por"],
        mode=OcrMode.FULL_PAGE,
        tesseract_cmd=tesseract_cmd or "tesseract",
    )
    pipeline = PdfPipelineOptions(do_ocr=True, ocr_options=ocr)
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline),
        }
    )


def benchmark(pdf: Path, out_root: Path, converter: DocumentConverter) -> dict:
    t0 = time.perf_counter()
    result = converter.convert(pdf)
    elapsed = time.perf_counter() - t0
    doc = result.document

    md = doc.export_to_markdown()
    out_dir = out_root / pdf.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "document.md").write_text(md, encoding="utf-8")

    chunker = HybridChunker()
    chunks = []
    for i, chunk in enumerate(chunker.chunk(dl_doc=doc)):
        chunks.append(
            {
                "id": i,
                "text": chunk.text,
                "contextualized": chunker.contextualize(chunk=chunk),
            }
        )
    (out_dir / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    stats = {
        "file": str(pdf),
        "seconds": round(elapsed, 3),
        "markdown_chars": len(md),
        "words": len(md.split()),
        "article_markers": len(re.findall(r"\bArt\.?\s*\d+", md, flags=re.I)),
        "title_markers": len(re.findall(r"\bT[ÍI]TULO\b", md, flags=re.I)),
        "chapter_markers": len(re.findall(r"\bCAP[ÍI]TULO\b", md, flags=re.I)),
        "section_markers": len(re.findall(r"\bSE[CÇ][AÃ]O\b", md, flags=re.I)),
        "hybrid_chunks": len(chunks),
        "output_dir": str(out_dir),
    }
    (out_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Executa o experimento preliminar de OCR e chunking com Docling."
    )
    ap.add_argument("pdfs", nargs="+", type=Path, help="PDFs que serão processados")
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("local_results/docling_smoke"),
        help="diretório de saída (padrão: local_results/docling_smoke)",
    )
    args = ap.parse_args()

    converter = build_converter()
    all_stats = []
    for pdf in args.pdfs:
        if not pdf.exists():
            print(f"[skip] not found: {pdf}")
            continue
        print(f"[docling] {pdf}")
        stats = benchmark(pdf, args.out, converter)
        all_stats.append(stats)
        print(json.dumps(stats, ensure_ascii=False))

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(
        json.dumps(all_stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
