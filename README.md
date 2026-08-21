# Ingestão documental das normas da UFPI

Este repositório contém o pipeline experimental de ingestão documental do TCC **Arquitetura de RAG Agêntico Escalável e Baseada em Grafos para o Ecossistema Normativo da UFPI**. O escopo atual é a avaliação preliminar de Document Intelligence e OCR; o RAG e o chunking jurídico ainda não estão implementados.

## Contexto

O TCC de referência trabalhou com a Resolução 177/2012 previamente convertida e estruturada, seguida de segmentação orientada a artigos e enriquecimento com metadados hierárquicos. Esta nova etapa investiga como automatizar a ingestão de um corpus normativo maior e heterogêneo usando o Docling. O experimento não demonstra que o Hybrid Chunking do Docling já resolva a segmentação jurídica.

## Estrutura

```text
.
├── data/raw/samples/          # PDFs públicos usados como amostras
├── docs/experiments/          # Registro metodológico dos experimentos
├── experiments/docling_smoke/ # Artefatos reais preservados
├── scripts/                   # Utilitários auxiliares de benchmark
└── src/ingest_documents/      # Código Python de ingestão
```

## Experimento preliminar

Foram usadas as Resoluções 089/2018, 162/2016 e 186/2006. A Resolução 177/2012 está incluída como documento de referência/baseline quando aplicável. As amostras incluem PDFs digitalizados, e o teste avalia OCR, reconstrução documental e uma geração inicial de chunks.

Os resultados registrados nos arquivos `stats.json` são:

| Documento | Tempo (s) | Caracteres Markdown | Palavras | Hybrid Chunks |
|---|---:|---:|---:|---:|
| 089/2018 | 37,987 | 24.991 | 3.870 | 54 |
| 162/2016 | 5,598 | 1.661 | 255 | 4 |
| 186/2006 | 173,113 | 24.615 | 3.695 | 55 |

Os artefatos completos estão em [`experiments/docling_smoke`](experiments/docling_smoke), e os detalhes metodológicos estão em [`docs/experiments/docling_smoke.md`](docs/experiments/docling_smoke.md).

## Execução

Requisitos externos: Python 3.12 e Tesseract OCR com os dados de idioma português (`por`) e de orientação (`osd`). No Windows, o script também detecta a instalação padrão em `C:\Program Files\Tesseract-OCR`. Dados locais do Tesseract podem ser mantidos em `.tessdata/`, que não é versionada.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "src"
python -m ingest_documents.docling_smoke --help
python -m ingest_documents.docling_smoke data/raw/samples/resolucao_089_2018.pdf
```

Por padrão, novas execuções escrevem em `local_results/docling_smoke`, uma pasta ignorada pelo Git, para não sobrescrever os artefatos já registrados. Use `--out` para escolher outro destino. Na primeira execução, o Docling pode baixar modelos do Hugging Face.
