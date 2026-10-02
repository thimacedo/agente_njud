#!/usr/bin/env python3
"""
Processa 4 NJUDs restantes do setembro: 1951, 1953, 1954, 1957.
CORRECAO: exportar PYTHONPATH no subprocess bash para evitar erro de modulo nao encontrado.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(r"E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")

NJUDs = [
    {
        "codigo": "1951",
        "data": "03",
        "subdir_audio": "03 09 - QUI",
        "boletins": ["B1", "B2", "B3", "B4"],
        "roteiro_txt": "setembro/roteiros_2026-09-03.txt",
        "saida_divisao": "data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/NJUD_1951",
        "output": "data/output/JORNAIS_FINAL",
    },
    {
        "codigo": "1953",
        "data": "04",
        "subdir_audio": "04 09 - SEX",
        "boletins": ["B1", "B2", "B3", "B7"],
        "roteiro_txt": "setembro/roteiros_2026-09-04.txt",
        "saida_divisao": "data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/NJUD_1953",
        "output": "data/output/JORNAIS_FINAL",
    },
    {
        "codigo": "1954",
        "data": "09",
        "subdir_audio": "09 09 - QUA",
        "boletins": ["B3", "B5", "B6", "B7"],
        "roteiro_txt": "setembro/roteiros_2026-09-09.txt",
        "saida_divisao": "data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/NJUD_1954",
        "output": "data/output/JORNAIS_FINAL",
    },
    {
        "codigo": "1957",
        "data": "14",
        "subdir_audio": "14 09 - SEG",
        "boletins": ["B1", "B5", "B6", "B7"],
        "roteiro_txt": "setembro/roteiros_2026-09-14.txt",
        "saida_divisao": "data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS/NJUD_1957",
        "output": "data/output/JORNAIS_FINAL",
    },
]

ICE = str(BASE / "boletins" / "09 - SET - 26")
BASH_PATH = r"C:/Program Files/Git/bin/bash.exe"
PYTHON_PATH = str(BASE / ".venv_pipeline" / "Scripts" / "python.exe")
SCRIPTS_PIPELINE_PATH = str(BASE / "scripts_pipeline")
NJUD_DIVIDIR_SH = str(BASE / "scripts_pipeline" / "njud" / "njud_dividir.sh")

def copiar_mp3(njud_info):
    """Copia os boletins do NJUD para o workspace local.

    Fail-closed: cada boletim é copiado e VERIFICADO no destino. Se qualquer
    arquivo não for copiado, retorna False — nunca reporta sucesso sem prova.

    Nota: o nome real dos boletins é
        BOLETIM_RADIO_TJRN_DD_MM_AAAA_B<N>_..._NJUD_<codigo>.mp3
    ou seja, o código do NJUD está no SUFIXO do nome, não no prefixo. Um
    filtro 'NJUD_<codigo>*.mp3' nunca casa — por isso a seleção é feita pelo
    índice B<N> (o dado que o pipeline realmente conhece), com exigência de
    que o arquivo pertença a este NJUD.

    A cópia é feita em Python puro (shutil): não depende de pwsh/powershell
    estar no PATH, que é uma fonte de falha silenciosa no ambiente Windows.
    """
    subdir = njud_info["subdir_audio"]
    codigo = njud_info["codigo"]
    src_base = Path(ICE) / subdir
    dest_base = Path(BASE) / "tmp" / f"njud_{codigo}_workspace"

    dest_base.mkdir(parents=True, exist_ok=True)

    env_path = dest_base / ".env_local"
    env_path.write_text(f"ROTEIRO_NJUD={njud_info['roteiro_txt']}\n", encoding="utf-8")

    if not src_base.is_dir():
        print(f"    ERRO: pasta de origem inexistente: {src_base}")
        return False

    print(f"  [COPIAR] NJUD {codigo}: copiando {len(njud_info['boletins'])} boletins...")

    candidatos = sorted(src_base.glob("*.mp3"))
    if not candidatos:
        print(f"    ERRO: nenhum MP3 em {src_base}")
        return False

    for b in njud_info["boletins"]:
        # B<N> delimitado (B1 não casa com B10) + pertence a este NJUD.
        pat_b = re.compile(rf"(^|[^0-9]){re.escape(b)}([^0-9]|$)")
        pat_njud = re.compile(rf"NJUD_{re.escape(codigo)}")

        matches = [f for f in candidatos if pat_b.search(f.name) and pat_njud.search(f.name)]
        if len(matches) != 1:
            print(f"    ERRO: {b} resolveu para {len(matches)} arquivos (esperado 1) em {src_base}")
            return False

        origem = matches[0]
        destino = dest_base / origem.name
        try:
            shutil.copy2(origem, destino)
        except Exception as e:
            print(f"    ERRO copiando {origem.name}: {e}")
            return False

        # Verificação independente no disco: existe e não está vazio?
        if not destino.is_file() or destino.stat().st_size == 0:
            print(f"    ERRO: {b} não confirmado no destino ({destino})")
            return False

        print(f"    OK: {origem.name} ({destino.stat().st_size} bytes)")

    print(f"  [OK] Workspace NJUD {codigo} pronto")
    return True

def executar_divisao(njud_info):
    codigo = njud_info["codigo"]
    saida = njud_info["saida_divisao"]
    workspace = f"tmp/njud_{codigo}_workspace"
    
    print(f"  [DIVIDIR] NJUD {codigo}...")
    
    # Exportar PYTHONPATH e PYTHON no subprocess bash
    cmd = [
        BASH_PATH, "-c",
        f'export PYTHONPATH="{SCRIPTS_PIPELINE_PATH}" && '
        f'export PYTHON="{PYTHON_PATH}" && '
        f'bash "{NJUD_DIVIDIR_SH}" divide "{BASE}/{workspace}" "{BASE}/{saida}"'
    ]
    
    log_file = open(os.path.join(str(BASE), "tmp", f"divisao_{codigo}.log"), "wb")
    result = subprocess.run(cmd, stdout=log_file, stderr=subprocess.STDOUT, timeout=600, cwd=str(BASE))
    log_file.close()
    
    if result.returncode != 0:
        with open(os.path.join(str(BASE), "tmp", f"divisao_{codigo}.log"), "rb") as f:
            log_content = f.read().decode('utf-8', errors='replace')[-500:]
        print(f"    ERRO divisao: exit {result.returncode}")
        print(f"    LOG: {log_content}")
        return False
    
    print(f"    OK: divisao concluida")
    return True

def executar_montagem(njud_info):
    codigo = njud_info["codigo"]
    saida_divisao = njud_info["saida_divisao"]
    output_dir = njud_info["output"]
    
    print(f"  [MONTAR] NJUD {codigo}...")
    
    cmd = [
        BASH_PATH, "-c",
        f'export PYTHONPATH="{SCRIPTS_PIPELINE_PATH}" && '
        f'bash "{NJUD_DIVIDIR_SH}" montar "{BASE}/{saida_divisao}" "{BASE}/{output_dir}"'
    ]
    
    log_file = open(os.path.join(str(BASE), "tmp", f"montagem_{codigo}.log"), "wb")
    result = subprocess.run(cmd, stdout=log_file, stderr=subprocess.STDOUT, timeout=300, cwd=str(BASE))
    log_file.close()
    
    if result.returncode != 0:
        with open(os.path.join(str(BASE), "tmp", f"montagem_{codigo}.log"), "rb") as f:
            log_content = f.read().decode('utf-8', errors='replace')[-500:]
        print(f"    ERRO montagem: exit {result.returncode}")
        print(f"    LOG: {log_content}")
        return False
    
    print(f"    OK: montagem concluida")
    return True

def verificar_ffprobe(njud_info):
    codigo = njud_info["codigo"]
    output_file = os.path.join(str(BASE), njud_info["output"], f"NJUD_{codigo}.mp3")
    print(f"  [FFPROBE] Verificando NJUD_{codigo}.mp3...")
    
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
             "-of", "csv=p=0", output_file],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            duracao, tamanho = result.stdout.strip().split(",")
            print(f"    OK: {tamanho} bytes, {float(duracao):.1f}s ({float(duracao)/60:.1f}min)")
            return True
        else:
            print(f"    ERRO ffprobe: {result.stderr}")
            return False
    except Exception as e:
        print(f"    ERRO: {e}")
        return False

def main():
    print("=" * 60)
    print("PROCESSAMENTO NJUDs SETEMBRO")
    print("=" * 60)
    
    for njud_info in NJUDs:
        print(f"\n{'='*40}")
        print(f"NJUD {njud_info['codigo']} (dia {njud_info['data']}/SET, {njud_info['subdir_audio']})")
        print(f"{'='*40}")
        
        if not copiar_mp3(njud_info):
            print(f"  ERRO: falha ao copiar MP3s para NJUD {njud_info['codigo']}")
            continue
        
        if not executar_divisao(njud_info):
            print(f"  ERRO: falha na divisao NJUD {njud_info['codigo']}")
            continue
        
        if not executar_montagem(njud_info):
            print(f"  ERRO: falha na montagem NJUD {njud_info['codigo']}")
            continue
        
        verificar_ffprobe(njud_info)
    
    print(f"\n{'='*40}")
    print("PROCESSAMENTO CONCLUIDO")
    print(f"{'='*40}")

if __name__ == "__main__":
    main()
