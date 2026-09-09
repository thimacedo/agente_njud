#!/usr/bin/env python3
"""
Gerador de planejamento GIRO 2026 (Janeiro a Agosto).
Gerada uma vez, os JSONs servem como entrada para o executor único.

Regras:
- Programas semanais às quartas-feiras
- Janela de 4 a 6 dias de boletins (mínimo 4 para viabilizar o programa)
- Código no formato MMSS (ex: 0101, 0102...)
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta

ANO = 2026
MESES_INICIO = 1  # Janeiro
MESES_FIM = 8     # Agosto
DIA_SEMANA_PROGRAMA = 2  # Quarta-feira (0=Seg, 1=Ter, 2=Qua, ...)
MIN_BOLETINS = 4
MAX_BOLETINS = 6
PASTA_PLAN = "config/planejamento_2026"


def quartas_ano(ano: int) -> list[date]:
    """Todas as quartas-feiras do ano."""
    result = []
    d = date(ano, 1, 1)
    while d.year == ano:
        if d.weekday() == DIA_SEMANA_PROGRAMA:
            result.append(d)
        d += timedelta(days=1)
    return result


def janela_coleta(data_programa: date) -> tuple[date, date] | None:
    """
    Janela de dias para coleta de boletins.
    Prioridade: MAX_BOLETINS dias consecutivos terminando na data do programa.
    Se ficar abaixo de MIN_BOLETINS (ex: início do ano), descarta.
    """
    fim = data_programa
    inicio = fim - timedelta(days=MAX_BOLETINS - 1)

    # Não voltar antes de 01/01/2026
    if inicio < date(ANO, 1, 1):
        inicio = date(ANO, 1, 1)

    dias = (fim - inicio).days + 1
    if dias < MIN_BOLETINS:
        return None
    return inicio, fim


def main() -> None:
    os.makedirs(PASTA_PLAN, exist_ok=True)

    quartas = quartas_ano(ANO)
    programas_por_mes: dict[int, list[date]] = {}

    print(f"--- Gerando Planejamentos GIRO {ANO} (Janeiro-Agosto) ---")

    for data_prog in quartas:
        if data_prog.month < MESES_INICIO or data_prog.month > MESES_FIM:
            continue

        j = janela_coleta(data_prog)
        if j is None:
            print(f"[SKIP] {data_prog} — janela inválida")
            continue

        inicio, fim = j
        dias = (fim - inicio).days + 1

        mes = data_prog.month
        programas_por_mes.setdefault(mes, []).append(data_prog)
        num_no_mes = len(programas_por_mes[mes])
        codigo = f"{mes:02d}{num_no_mes:02d}"

        config = {
            "programa": "GIRO",
            "codigo": codigo,
            "data_exibicao": str(data_prog),
            "janela_coleta": {
                "inicio": str(inicio),
                "fim": str(fim),
                "dias_totais": dias,
            },
            "parametros": {
                "boletins_minimos": MIN_BOLETINS,
                "corte_por_silencio": True,
                "duracao_silencio_segundos": 1.0,
                "fallback_audio_completo": False,
                "usar_demucs": False,
            },
            "status": "pendente",
        }

        caminho = os.path.join(PASTA_PLAN, f"giro_{codigo}.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        print(f"[OK] {codigo}: {inicio} até {fim} ({dias} dias) -> giro_{codigo}.json")

    # Resumo Markdown
    linhas = [
        "# Planejamento GIRO 2026 (Janeiro a Agosto)",
        "Gerado automaticamente pelo script `scripts_pipeline/gerar_planejamento_giro.py`.",
        "",
        "## Regras de Negócio",
        "- **Frequência:** Semanal (Quartas-feiras)",
        "- **Janela de Coleta:** 4 a 6 dias anteriores ao programa",
        "- **Mínimo de Boletins:** 4 (programa é descartado se < 4)",
        "- **Corte:** Por silêncio de 1.0s (sem vinheta)",
        "- **Fallback:** Desabilitado (regra rígida: ou corta ou falha)",
    ]

    nomes_meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    }

    total = 0
    for mes in range(MESES_INICIO, MESES_FIM + 1):
        if mes not in programas_por_mes:
            continue
        linhas.append(f"\n### {nomes_meses[mes]} ({len(programas_por_mes[mes])} programas)")
        linhas.append("| Código | Data Exibição | Período Coleta | Dias | Arquivo JSON |")
        linhas.append("|--------|---------------|----------------|------|--------------|")
        for data_prog in programas_por_mes[mes]:
            j = janela_coleta(data_prog)
            if j is None:
                continue
            inicio, fim = j
            dias = (fim - inicio).days + 1
            num_no_mes = programas_por_mes[mes].index(data_prog) + 1
            codigo = f"{mes:02d}{num_no_mes:02d}"
            linhas.append(
                f"| {codigo} | {data_prog.strftime('%d/%m/%Y')} | "
                f"{inicio.strftime('%d/%m')} - {fim.strftime('%d/%m')} | "
                f"{dias} | giro_{codigo}.json |"
            )
            total += 1

    linhas.extend([
        "",
        f"## Programas Gerados: {total}",
        "",
        "## Como Executar",
        "Use o executor genérico passando o JSON desejado:",
        "",
        "```bash",
        "# Exemplo: Executar o primeiro programa de Janeiro",
        "python scripts_pipeline/executar_programa.py config/planejamento_2026/giro_0101.json",
        "",
        "# Exemplo: Executar o último programa de Agosto",
        "python scripts_pipeline/executar_programa.py config/planejamento_2026/giro_0804.json",
        "```",
        "",
        "## Estrutura de Pastas Esperada",
        "Os arquivos de áudio brutos devem estar organizados por data para que o pipeline os encontre:",
        "```",
        "JORNAIS/",
        "├── 2026-01-08/",
        "├── 2026-01-09/",
        "...",
        "```",
    ])

    resumo = "\n".join(linhas)
    with open(os.path.join(PASTA_PLAN, "RESUMO_GIRO_2026.md"), "w", encoding="utf-8") as f:
        f.write(resumo + "\n")

    print(f"\nResumo: {total} programas gerados.")
    print(f"Planos: {PASTA_PLAN}/")
    print(f"Resumo: {PASTA_PLAN}/RESUMO_GIRO_2026.md")


if __name__ == "__main__":
    main()
