#!/usr/bin/env python3
"""Padroniza nomes de NJUD e atualiza metadados ID3 conforme projeção."""
import os
import re
import logging
import sys
from pathlib import Path

# Garantir que src/ está no path para imports absolutos de pacote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3

from config.settings import settings

ROOT = Path(settings.BASE_DIR)
LOG_DIR = ROOT / "logs"
CSV_PATH = ROOT / "data" / "processed" / "dias_uteis_programas_projetado_do_ultimo.csv"
ALT_CSV = Path(r"C:\Users\THIAGO\AppData\Local\hermes\profiles\divisor\attachments\dias_uteis_programas_projetado_do_ultimo.csv")
if not CSV_PATH.exists() and ALT_CSV.exists():
    CSV_PATH = ALT_CSV
PASTAS_ALVO = [
    ROOT / "data" / "processed" / "JORNAIS_DIVIDIDOS",
    ROOT / "data" / "output",
    ROOT / "data" / "processed" / "JORNAIS_DIVIDIDOS_JUN_JUL_AGO_2026",
]

LOG_DIR.mkdir(parents=True, exist_ok=True)
ERROR_LOG_PATH = LOG_DIR / "padronizador_completo.log"

logging.basicConfig(
    filename=ERROR_LOG_PATH,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def carregar_mapeamento_projetado(csv_path: Path):
    df_proj = pd.read_csv(csv_path)
    num_para_data = dict(zip(df_proj["Programa_Projetado"].astype(int), df_proj["Data_Formatada"]))
    data_para_num = dict(zip(df_proj["Data_Formatada"], df_proj["Programa_Projetado"].astype(int)))
    todas_datas_uteis = list(df_proj["Data_Formatada"])
    return num_para_data, data_para_num, todas_datas_uteis


def atualizar_metadados_id3(caminho_arquivo: Path, artista: str, titulo: str, album: str) -> None:
    try:
        audio = EasyID3(caminho_arquivo)
    except Exception:
        try:
            audio = ID3(caminho_arquivo)
            audio.save(v2_version=3)
            audio = EasyID3(caminho_arquivo)
        except Exception as e:
            logging.error(f"Erro ao inicializar tags ID3 para {caminho_arquivo}: {str(e)}")
            return

    if audio is not None:
        try:
            audio["artist"] = artista
            audio["title"] = titulo
            audio["album"] = album
            audio.save()
        except Exception as e:
            logging.error(f"Erro ao salvar tags ID3 para {caminho_arquivo}: {str(e)}")


def processar_remanejo_pastas(pastas_alvo: list[Path], csv_path: Path) -> None:
    num_para_data, data_para_num, todas_datas_uteis = carregar_mapeamento_projetado(csv_path)

    for pasta in pastas_alvo:
        if not pasta.exists():
            continue

        try:
            arquivos = list(pasta.iterdir())
        except Exception as e:
            logging.error(f"Erro de permissão ou acesso à pasta {pasta}: {str(e)}")
            continue

        for caminho_antigo in arquivos:
            if not caminho_antigo.name.lower().endswith(".mp3"):
                continue

            filename = caminho_antigo.name
            match = re.search(r"(?:NJUD|BOLETIM_RADIO_TJRN)[_-]?(\d+)", filename, re.IGNORECASE)
            if not match:
                continue

            num_programa = int(match.group(1))
            data_correta_str = num_para_data.get(num_programa)

            if not data_correta_str:
                continue

            data_format_filename = data_correta_str.replace("/", "-")
            novo_nome = f"NJUD_{num_programa}_{data_format_filename}.mp3"
            target_path = pasta / novo_nome

            if caminho_antigo.name == novo_nome:
                atualizar_metadados_id3(caminho_antigo, "TJRN", f"Programa {num_programa}", "Jornal do Judiciário")
                continue

            if target_path.exists() and caminho_antigo != target_path:
                idx_atual = todas_datas_uteis.index(data_correta_str) if data_correta_str in todas_datas_uteis else 0
                livre_encontrada = False
                for offset in range(1, len(todas_datas_uteis)):
                    novo_idx = idx_atual + offset
                    if novo_idx < len(todas_datas_uteis):
                        cand_data = todas_datas_uteis[novo_idx]
                        cand_num = data_para_num[cand_data]
                        cand_filename = f"NJUD_{cand_num}_{cand_data.replace('/', '-')}.mp3"
                        cand_path = pasta / cand_filename
                        if not cand_path.exists():
                            num_programa = cand_num
                            data_correta_str = cand_data
                            target_path = cand_path
                            livre_encontrada = True
                            break
                if not livre_encontrada:
                    continue

            try:
                caminho_antigo.rename(target_path)
                atualizar_metadados_id3(target_path, "TJRN", f"Programa {num_programa}", "Jornal do Judiciário")
            except Exception as e:
                logging.error(f"Erro ao renomear ou atualizar arquivo {filename}: {str(e)}")

    print(f"Processamento concluído. Log: {ERROR_LOG_PATH}")


def main():
    processar_remanejo_pastas(PASTAS_ALVO, CSV_PATH)


if __name__ == "__main__":
    main()
