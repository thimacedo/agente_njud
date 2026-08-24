import os
import sys
import json
import shutil
from pathlib import Path

PASTA_ORIGEM_JORNAIS = Path("F:/Projetos/DIVISOR/data/output")
PASTA_DESTINO_DRIVE_PAI = Path(r"H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\02_JORNAIS_NJUD\03_AUDIOS_RADIO")

MAPEAMENTO_MESES = {
    "JAN": "01 - JAN - 26",
    "FEV": "02 - FEV - 26",
    "MAR": "03 - MAR - 26",
    "ABR": "04 - ABR - 26",
    "MAI": "05 - MAI - 26",
    "JUN": "06 - JUN - 26",
    "JUL": "07 - JUL - 26",
    "AGO": "08 - AGO - 26",
    "SET": "09 - SET - 26",
    "OUT": "10 - OUT - 26",
    "NOV": "11 - NOV - 26",
    "DEZ": "12 - DEZ - 26",
}

def obter_pasta_mes_destino(nome_arquivo):
    parts = nome_arquivo.replace(".mp3", "").split("_")
    if len(parts) >= 3:
        data_str = parts[2]
        data_parts = data_str.split("-")
        if len(data_parts) == 3:
            mes_num = data_parts[1]
            mes_nomes = {
                "01": "JAN", "02": "FEV", "03": "MAR", "04": "ABR",
                "05": "MAI", "06": "JUN", "07": "JUL", "08": "AGO",
                "09": "SET", "10": "OUT", "11": "NOV", "12": "DEZ"
            }
            mes_sigla = mes_nomes.get(mes_num)
            if mes_sigla and mes_sigla in MAPEAMENTO_MESES:
                return PASTA_DESTINO_DRIVE_PAI / MAPEAMENTO_MESES[mes_sigla]
    return None

def sincronizar_com_drive():
    if not os.path.exists(str(PASTA_DESTINO_DRIVE_PAI)):
        print(f" ⚠ Google Drive não está montado ou acessível em: {PASTA_DESTINO_DRIVE_PAI}")
        print(" O processo será pausado. Conecte o Google Drive e execute este script novamente.")
        return

    # Alinhamento 2026-08-24 (DECISOES.md item 6): a montagem grava em
    # data/output/JORNAIS_FINAL/. Raiz de data/output mantida como fallback
    # por compatibilidade com jornais montados antes do alinhamento.
    pasta_jornais = PASTA_ORIGEM_JORNAIS / "JORNAIS_FINAL"
    if not pasta_jornais.is_dir():
        pasta_jornais = PASTA_ORIGEM_JORNAIS
        print(" ⚠ JORNAIS_FINAL não existe; usando raiz de data/output (fallback).")
    jornais = [pasta_jornais / f for f in os.listdir(pasta_jornais) if f.endswith('.mp3')]
    print(f"=== Sincronizando {len(jornais)} jornais montados com o Google Drive ===")
    
    sucesso = 0
    erros = 0
    
    for j in jornais:
        pasta_destino = obter_pasta_mes_destino(j.name)
        if not pasta_destino:
            print(f" ⚠ Não foi possível mapear mês para: {j.name}")
            erros += 1
            continue
            
        pasta_destino.mkdir(parents=True, exist_ok=True)
        caminho_destino = pasta_destino / j.name
        
        if caminho_destino.exists():
            # REGRA DE OPERAÇÃO: sobrescreve sem criar cópias _old no Drive
            # (decisão do operador, 2026-08-24 — nenhuma cópia extra no H:).
            print(f" ↺ Arquivo existente será sobrescrito: {caminho_destino.name}")
            caminho_destino.unlink()
            
        print(f" ➜ Copiando {j.name} -> {pasta_destino.name}")
        try:
            shutil.copy2(str(j), str(caminho_destino))
            sucesso += 1
        except Exception as e:
            print(f" ✖ Erro ao copiar {j.name}: {e}")
            erros += 1
            
    print(f"\n=== Sincronização concluída: {sucesso}/{len(jornais)} enviados. Erros: {erros} ===")

if __name__ == "__main__":
    sincronizar_com_drive()
