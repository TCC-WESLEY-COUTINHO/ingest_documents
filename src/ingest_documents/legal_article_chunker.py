"""Segmentação determinística de normas em chunks de um artigo por vez.

Este módulo adapta a estratégia metodológica de ``chunks_v2.py`` ao Markdown
produzido pelo Docling. Ele não normaliza nem corrige o conteúdo de OCR.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    PROJECT_ROOT
    / "experiments"
    / "docling_smoke"
    / "resolucao_177_2012_cepex"
    / "document.md"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "experiments"
    / "legal_article_chunking"
    / "resolucao_177_2012"
)

# O ponto é opcional porque o OCR produziu casos reais como ``Art 69``.
ARTICLE_RE = re.compile(r"\bArt(?:\.)?\s+(\d{1,3})(?:\s*[º°])?")
ARTICLE_ONLY_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?Art(?:\.)?\s*$"
)
ARTICLE_NUMBER_CONTINUATION_RE = re.compile(r"^\s*(\d{1,3})(?:\s*[º°])?(.*)$")

# O Docling nivelou Título, Capítulo, Seção e Subseção como ``##``. Por isso,
# o tipo hierárquico é identificado pelo conteúdo do cabeçalho, não pelo nível.
HEADING_RE = re.compile(
    r"^\s*#{1,6}\s+"
    r"(?:[\s\"'.º*,-]|o\s+)*"
    r"(?P<kind>SUBSE(?:C|Ç)[AÃÁ]O|SE(?:C|Ç)[AÃÁ]O|CAP[IÍ]TULO|T[IÍ]TULO)"
    r"(?P<tail>.*)$",
    re.IGNORECASE,
)
ROMANISH_RE = re.compile(r"^([IVXLCDM|!]+)(?=\s|[.,;:—-]|$)", re.IGNORECASE)

SHORT_ARTICLE_CHARS = 100
LONG_ARTICLE_CHARS = 5_000


def _canonical_heading_kind(raw_kind: str) -> str:
    folded = raw_kind.upper()
    if folded.startswith("SUBSE"):
        return "subsection"
    if folded.startswith("SE"):
        return "section"
    if folded.startswith("CAP"):
        return "chapter"
    return "title"


def _parse_heading(line: str) -> tuple[str, str | None, str | None] | None:
    """Extrai tipo, número observado e nome de um cabeçalho Docling.

    Tokens romanos degradados pelo OCR, como ``|`` ou ``Il``, são preservados
    literalmente. Isso evita introduzir correção automática no corpus.
    """

    match = HEADING_RE.match(line)
    if not match:
        return None

    kind = _canonical_heading_kind(match.group("kind"))
    tail = match.group("tail").strip(" \t.,;:—-\"'º")
    number: str | None = None

    number_match = ROMANISH_RE.match(tail)
    if number_match:
        number = number_match.group(1)
        tail = tail[number_match.end() :].strip(" \t.,;:—-\"'º)")

    return kind, number, tail or None


def _is_definition_marker(line: str, marker: re.Match[str]) -> bool:
    """Distingue início de artigo de referência abreviada no corpo.

    Um marcador é definição quando aparece no início lógico da linha (aceitando
    prefixos Markdown) ou depois de pontuação que encerra o conteúdo anterior.
    Assim, ``no Art. 98`` não abre chunk, enquanto ``... anterior. Art. 213``
    abre um novo artigo concatenado pelo Docling.
    """

    prefix = line[: marker.start()]
    logical_prefix = re.sub(r"^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?", "", prefix)
    if not logical_prefix.strip():
        return True

    previous = prefix.rstrip()
    # O único ``Art. N`` maiúsculo usado como referência no documento real é
    # introduzido por preposição (``no Art. 98``). A exclusão por contexto é
    # geral e mantém definições concatenadas mesmo quando o OCR perdeu o ponto
    # final anterior, como ocorreu nos artigos 90, 96 e 113.
    if re.search(r"(?i)\b(?:no|do|ao|pelo|neste|nesse|deste)\s*$", previous):
        return False
    return bool(previous)


def _article_markers(line: str) -> list[re.Match[str]]:
    return [match for match in ARTICLE_RE.finditer(line) if _is_definition_marker(line, match)]


def _clean_article_start(text: str) -> str:
    return re.sub(r"^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?", "", text).strip()


@dataclass
class Hierarchy:
    title_number: str | None = None
    title_name: str | None = None
    chapter_number: str | None = None
    chapter_name: str | None = None
    section_number: str | None = None
    section_name: str | None = None
    subsection_number: str | None = None
    subsection_name: str | None = None

    def update(self, kind: str, number: str | None, name: str | None) -> None:
        if kind == "title":
            self.title_number = number
            self.title_name = name
            self.chapter_number = self.chapter_name = None
            self.section_number = self.section_name = None
            self.subsection_number = self.subsection_name = None
        elif kind == "chapter":
            self.chapter_number = number
            self.chapter_name = name
            self.section_number = self.section_name = None
            self.subsection_number = self.subsection_name = None
        elif kind == "section":
            self.section_number = number
            self.section_name = name
            self.subsection_number = self.subsection_name = None
        else:
            self.subsection_number = number
            self.subsection_name = name

    def as_metadata(self) -> dict[str, str | None]:
        return {
            "title_number": self.title_number,
            "title_name": self.title_name,
            "chapter_number": self.chapter_number,
            "chapter_name": self.chapter_name,
            "section_number": self.section_number,
            "section_name": self.section_name,
            "subsection_number": self.subsection_number,
            "subsection_name": self.subsection_name,
        }


@dataclass
class LegalArticleParser:
    hierarchy: Hierarchy = field(default_factory=Hierarchy)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    _current_number: str | None = None
    _current_metadata: dict[str, str | None] | None = None
    _current_lines: list[str] = field(default_factory=list)
    _pending_article_marker: bool = False

    def _start_article(self, number: str, initial_text: str) -> None:
        self._finish_article()
        self._current_number = number
        self._current_metadata = self.hierarchy.as_metadata()
        self._current_lines = [_clean_article_start(initial_text)]

    def _finish_article(self) -> None:
        if self._current_number is None:
            return

        text = "\n".join(part for part in self._current_lines if part.strip()).strip()
        self.chunks.append(
            {
                "article_number": self._current_number,
                "text": text,
                "metadata": self._current_metadata,
            }
        )
        self._current_number = None
        self._current_metadata = None
        self._current_lines = []

    def _process_content_line(self, line: str) -> None:
        if self._pending_article_marker:
            if not line.strip():
                return
            continuation = ARTICLE_NUMBER_CONTINUATION_RE.match(line)
            self._pending_article_marker = False
            if continuation:
                initial_text = f"Art. {continuation.group(1)}{continuation.group(2)}"
                self._start_article(continuation.group(1), initial_text)
                return

        if ARTICLE_ONLY_RE.match(line):
            self._pending_article_marker = True
            return

        markers = _article_markers(line)
        if not markers:
            if self._current_number is not None and line.strip():
                self._current_lines.append(line.strip())
            return

        cursor = 0
        for index, marker in enumerate(markers):
            prefix = line[cursor : marker.start()].strip()
            if prefix and self._current_number is not None:
                self._current_lines.append(prefix)

            next_start = markers[index + 1].start() if index + 1 < len(markers) else len(line)
            article_text = line[marker.start() : next_start]
            self._start_article(marker.group(1), article_text)
            cursor = next_start

    def parse(self, markdown: str) -> list[dict[str, Any]]:
        for line in markdown.splitlines():
            heading = _parse_heading(line)
            if heading:
                self.hierarchy.update(*heading)
                continue
            self._process_content_line(line)

        self._finish_article()
        return self.chunks


def build_stats(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    numbers = [chunk["article_number"] for chunk in chunks]
    counts = Counter(numbers)

    def coverage(level: str) -> int:
        return sum(
            chunk["metadata"][f"{level}_number"] is not None
            or chunk["metadata"][f"{level}_name"] is not None
            for chunk in chunks
        )

    def sized(chunk: dict[str, Any]) -> dict[str, int | str]:
        return {
            "article_number": chunk["article_number"],
            "characters": len(chunk["text"]),
        }

    return {
        "articles_detected": len(chunks),
        "articles_with_title": coverage("title"),
        "articles_with_chapter": coverage("chapter"),
        "articles_with_section": coverage("section"),
        "articles_with_subsection": coverage("subsection"),
        "duplicate_article_numbers": sorted(
            (number for number, count in counts.items() if count > 1), key=int
        ),
        "first_article": numbers[0] if numbers else None,
        "last_article": numbers[-1] if numbers else None,
        "abnormally_short_articles": [
            sized(chunk) for chunk in chunks if len(chunk["text"]) < SHORT_ARTICLE_CHARS
        ],
        "abnormally_long_articles": [
            sized(chunk) for chunk in chunks if len(chunk["text"]) > LONG_ARTICLE_CHARS
        ],
        "thresholds": {
            "short_below_characters": SHORT_ARTICLE_CHARS,
            "long_above_characters": LONG_ARTICLE_CHARS,
        },
    }


def write_outputs(
    chunks: list[dict[str, Any]], stats: dict[str, Any], output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "article_chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def print_report(chunks: list[dict[str, Any]], stats: dict[str, Any]) -> None:
    print(f"Total de artigos: {stats['articles_detected']}")
    print(f"Primeiro artigo: {stats['first_article']}")
    print(f"Último artigo: {stats['last_article']}")
    print(f"Números duplicados: {stats['duplicate_article_numbers']}")
    print(
        "Cobertura: "
        f"título={stats['articles_with_title']}, "
        f"capítulo={stats['articles_with_chapter']}, "
        f"seção={stats['articles_with_section']}, "
        f"subseção={stats['articles_with_subsection']}"
    )

    by_number: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        by_number.setdefault(chunk["article_number"], []).append(chunk)

    for number in ("118", "148", "213", "249"):
        matches = by_number.get(number, [])
        sizes = [len(chunk["text"]) for chunk in matches]
        print(f"Tamanho do artigo {number}: {sizes if sizes else 'N/A'}")

    for number in ("148", "249"):
        matches = by_number.get(number, [])
        preview = matches[0]["text"][:300] if matches else "N/A"
        print(f"Primeiros 300 caracteres do artigo {number}: {preview}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Segmenta Markdown Docling em chunks de artigos normativos."
    )
    parser.add_argument("input", nargs="?", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    markdown = args.input.read_text(encoding="utf-8")
    chunks = LegalArticleParser().parse(markdown)
    stats = build_stats(chunks)
    write_outputs(chunks, stats, args.out)
    print_report(chunks, stats)


if __name__ == "__main__":
    main()
