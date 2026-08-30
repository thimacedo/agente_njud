#!/usr/bin/env python3
"""Organiza boletins BOLETIM_RADIO_TJRN_* por data em subpastas DD-MM-AAAA."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import re
import shutil
from datetime import datetime

try:
    from config.settings import Settings
    settings = Settings()
    BASE = Path(settings.BASE_DIR)
except Exception:
    BASE = Path("F:/Projetos/DIVISOR")

PASTAS_ALVO = [
    BASE / "data/processed/JORNAIS_DIVIDIDOS",
    BASE / "data/output",
    BASE / "data/processed/JORNAIS_DIVIDIDOS_JUN_JUL_AGO_2026",
]
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
LOG_ORGANIZACAO = LOGS / "organizacao_boletins.log"

# Padrão de data no nome do boletim
PATTERN_BOLETIM = re.compile(r"^BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", re.IGNORECASE)

# Mapeamento mês numérico -> pasta de mês (formato existente no projeto)
MES_NUM_TO_PASTA = {
    "01": "01 - JAN - 26",
    "02": "02 - FEV - 26",
    "03": "03 - MAR - 26",
    "04": "04 - ABR - 26",
    "05": "05 - MAI - 26",
    "06": "06 - JUN - 26",
    "07": "07 - JUL - 26",
    "08": "08 - AGO - 26",
    "09": "09 - SET - 26",
    "10": "10 - OUT - 26",
    "11": "11 - NOV - 26",
    "12": "12 - DEZ - 26",
}


def extrair_data(nome_arquivo):
    m = PATTERN_BOLETIM.match(nome_arquivo)
    if m:
        dia, mes, ano = m.groups()
        return dia, mes, ano
    return None, None, None


def main():
    print("=== ORGANIZAÇÃO FÍSICA DE BOLETINS POR DATA ===\n")
    LOG_ORGANIZACAO.parent.mkdir(parents=True, exist_ok=True)
    log_lines = []
    log_lines.append(f"[{datetime.now().isoformat()}] Iniciando organização de boletins por data")

    movidos = 0
    erros = 0
    ignorados = 0

    for pasta_alvo in PASTAS_ALVO:
        if not pasta_alvo.exists():
            continue

        # Escanear todos os arquivos de boletim
        for arquivo in pasta_alvo.rglob("BOLETIM_RADIO_TJRN*.mp3"):
            dia, mes, ano = extrair_data(arquivo.name)
            if not dia or not mes or not ano:
                log_lines.append(f"IGNORADO (data não extraída): {arquivo}")
                ignorados += 1
                continue

            # Determinar pasta de mês
            pasta_mes_nome = MES_NUM_TO_PASTA.get(mes)
            if not pasta_mes_nome:
                log_lines.append(f"IGNORADO (mês inválido): {arquivo}")
                ignorados += 1
                continue

            # Criar estrutura: pasta_alvo / pasta_mes / DD-MM-AAAA /
            pasta_mes = pasta_alvo / pasta_mes_nome
            pasta_data = pasta_mes / f"{dia}-{mes}-{ano}"
            pasta_data.mkdir(parents=True, exist_ok=True)

            # Mover arquivo para a subpasta de data
            destino = pasta_data / arquivo.name
            try:
                if destino.exists():
                    # Se já existe, pular
                    log_lines.append(f"IGNORADO (já existe): {destino}")
                    ignorados += 1
                else:
                    shutil.move(str(arquivo), str(destino))
                    log_lines.append(f"MOVIDO: {arquivo} -> {destino}")
                    movidos += 1
            except Exception as e:
                log_lines.append(f"ERRO: {arquivo} -> {e}")
                erros += 1

    log_lines.append(f"Concluído: movidos={movidos}, erros={erros}, ignorados={ignorados}")
    LOG_ORGANIZACAO.write_text("\n".join(log_lines), encoding="utf-8")

    print(f"Movidos: {movidos}")
    print(f"Erros: {erros}")
    print(f"Ignorados: {ignorados}")
    print(f"Log: {LOG_ORGANIZACAO}")


if __name__ == "__main__":
    main()
