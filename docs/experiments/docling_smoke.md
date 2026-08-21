# Experimento preliminar com Docling

## Objetivo

Avaliar preliminarmente a capacidade do Docling de aplicar OCR a resoluções da UFPI, reconstruir sua representação documental em Markdown e produzir uma segmentação inicial com `HybridChunker`.

## Documentos utilizados

- Resolução 089/2018;
- Resolução 162/2016;
- Resolução 186/2006;
- Resolução 177/2012, mantida como referência/baseline quando aplicável.

Os PDFs públicos usados no estudo estão preservados em `data/raw/samples/`. Os três primeiros possuem resultados produzidos pelo experimento Docling; a Resolução 177/2012 não possui artefatos Docling registrados nesta execução.

## Configuração

- Docling 2.121.0;
- Transformers 5.15.1;
- Tesseract OCR 5.4;
- idioma de OCR: português (`por`);
- modo de OCR: página completa (`FULL_PAGE`);
- segmentação inicial: `HybridChunker`.

## Procedimento

Para cada PDF, o conversor foi configurado para forçar OCR em página completa. O documento resultante foi exportado para Markdown e submetido ao `HybridChunker`. Foram registrados o tempo de conversão, volume textual, marcadores estruturais encontrados e quantidade de chunks. Esta documentação descreve os artefatos já existentes; nenhum experimento foi reexecutado durante sua organização.

## Artefatos produzidos

Cada diretório de documento em `experiments/docling_smoke/` contém:

- `document.md`: reconstrução textual em Markdown;
- `chunks.json`: chunks e versões contextualizadas;
- `stats.json`: métricas da execução.

O arquivo `summary.json` existente também foi preservado sem regeneração. As métricas abaixo foram consolidadas diretamente dos três arquivos individuais `stats.json`.

## Resultados

| Documento | Tempo (s) | Caracteres | Palavras | Chunks |
|---|---:|---:|---:|---:|
| 089/2018 | 37,987 | 24.991 | 3.870 | 54 |
| 162/2016 | 5,598 | 1.661 | 255 | 4 |
| 186/2006 | 173,113 | 24.615 | 3.695 | 55 |

Além dessas métricas, foram identificados respectivamente 47, 5 e 31 marcadores de artigo nos documentos 089/2018, 162/2016 e 186/2006.

## Limitações observadas

- símbolos jurídicos podem ser confundidos pelo OCR, como `§` reconhecido como `$` ou `8`;
- existem erros de reconhecimento em algarismos romanos;
- cabeçalhos e rodapés podem permanecer nos chunks;
- o Hybrid Chunking não representa necessariamente a regra jurídica de `1 artigo = 1 chunk`;
- ainda são necessárias normalização textual e reconstrução hierárquica próprias do domínio normativo.

## Próximos testes

A etapa planejada é reproduzir automaticamente a estratégia do TCC anterior: usar o artigo como unidade primária de recuperação e enriquecê-lo com metadados hierárquicos, mantendo o Docling como camada de Document Intelligence. Esse processamento jurídico não foi implementado neste commit.
