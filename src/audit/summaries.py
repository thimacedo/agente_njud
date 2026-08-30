#!/usr/bin/env python3
"""
Resumo de Métodos — AUDIT_cortes.json
=======================================

Lê um (ou mais) AUDIT_cortes.json e imprime a distribuição de métodos
usados por vinheta (abertura/passagem/encerramento), além da lista de
arquivos que caíram em fallback textual/proporcional — os candidatos
prioritários para validação manual (Etapa D).

Funciona tanto com o formato do lote VAD+texto atual (campo "metodo"
único) quanto com o formato novo, pós-correlação (campos
"metodo_abertura"/"metodo_passagem"/"metodo_encerramento" separados) —
detecta automaticamente qual formato está lendo.

Uso
----
    python resumo_metodos.py caminho/para/AUDIT_cortes.json
    python resumo_metodos.py lote_vad_texto/AUDIT_cortes.json lote_correlacao/AUDIT_cortes.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def carregar_audit(caminho: Path) -> dict:
    if not caminho.exists():
        print(f"✖ Não encontrado: {caminho}", file=sys.stderr)
        sys.exit(1)
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def resumir(audit: dict, nome_lote: str):
    resultados = audit.get("resultados", [])
    print(f"\n{'='*70}")
    print(f"LOTE: {nome_lote}")
    print(f"{'='*70}")
    print(f"Total de arquivos: {audit.get('total_arquivos', '?')}")
    print(f"Processados com sucesso: {audit.get('processados', '?')}")
    print(f"Erros: {audit.get('erros', '?')}")

    if not resultados:
        print("Nenhum resultado no relatório.")
        return

    formato_novo = "metodo_abertura" in resultados[0]

    if formato_novo:
        contagem_abertura = Counter(r.get("metodo_abertura", "?") for r in resultados)
        contagem_passagem = Counter(r.get("metodo_passagem", "?") for r in resultados)
        contagem_encerramento = Counter(r.get("metodo_encerramento", "?") for r in resultados)

        print("\nMétodo — ABERTURA:")
        for metodo, qtd in contagem_abertura.most_common():
            print(f"    {metodo}: {qtd} ({100*qtd/len(resultados):.1f}%)")

        print("\nMétodo — PASSAGEM:")
        for metodo, qtd in contagem_passagem.most_common():
            print(f"    {metodo}: {qtd} ({100*qtd/len(resultados):.1f}%)")

        print("\nMétodo — ENCERRAMENTO:")
        for metodo, qtd in contagem_encerramento.most_common():
            print(f"    {metodo}: {qtd} ({100*qtd/len(resultados):.1f}%)")

        arquivos_fallback = [
            r["arquivo_entrada"] for r in resultados
            if "correlacao" not in (
                r.get("metodo_abertura", ""),
                r.get("metodo_passagem", ""),
                r.get("metodo_encerramento", ""),
            )
        ]
    else:
        contagem = Counter(r.get("metodo", "?") for r in resultados)
        print("\nMétodo (único, formato antigo):")
        for metodo, qtd in contagem.most_common():
            print(f"    {metodo}: {qtd} ({100*qtd/len(resultados):.1f}%)")

        arquivos_fallback = [
            r["arquivo_entrada"] for r in resultados
            if r.get("metodo") in ("ancoras_fallback", "grade_fixa_locucao")
            or r.get("avisos")
        ]

    print(f"\nArquivos com aviso/fallback ({len(arquivos_fallback)}) "
          f"— candidatos prioritários para validação manual:")
    for a in arquivos_fallback[:30]:
        print(f"    {a}")
    if len(arquivos_fallback) > 30:
        print(f"    ... e mais {len(arquivos_fallback) - 30}")


def main():
    parser = argparse.ArgumentParser(
        description="Resume a distribuição de métodos em um ou mais AUDIT_cortes.json"
    )
    parser.add_argument("audits", nargs="+", help="Caminho(s) para AUDIT_cortes.json")
    args = parser.parse_args()

    for caminho_str in args.audits:
        caminho = Path(caminho_str)
        audit = carregar_audit(caminho)
        resumir(audit, nome_lote=str(caminho.parent.name or caminho))


if __name__ == "__main__":
    main()
