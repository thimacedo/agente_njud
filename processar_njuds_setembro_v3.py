#!/usr/bin/env python3
"""
Processa 4 NJUDs restantes do setembro: 1951, 1953, 1954, 1957.
CORRECAO: exportar PYTHONPATH no subprocess bash para evitar erro de modulo nao encontrado.
"""

import os
import re
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
    filtro 'NJUD_<codigo>*.mp3' nunca casa — por isso a cópia é feita por
    seleção explícita do índice B<N> (que é o dado que o pipeline realmente
    conhece), não por glob de prefixo.
    """
    subdir = njud_info["subdir_audio"]
    codigo = njud_info["codigo"]
    src_base = os.path.join(ICE, subdir)
    dest_base = os.path.join(str(BASE), "tmp", f"njud_{codigo}_workspace")

    os.makedirs(dest_base, exist_ok=True)

    env_path = os.path.join(dest_base, ".env_local")
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(f"ROTEIRO_NJUD={njud_info['roteiro_txt']}\n")

    if not os.path.isdir(src_base):
        print(f"    ERRO: pasta de origem inexistente: {src_base}")
        return False

    print(f"  [COPIAR] NJUD {codigo}: copiando {len(njud_info['boletins'])} boletins...")

    for b in njud_info["boletins"]:
        # Seleciona pelo índice B<N> delimitado (B1 não casa com B10) e
        # exige que o arquivo pertença a este NJUD.
        cmd = [
            "pwsh", "-NoProfile", "-Command",
            (
                f"$f = Get-ChildItem -LiteralPath '{src_base}' -Filter '*.mp3' | "
                f"Where-Object {{ $_.Name -match '(^|[^0-9])B{re.escape(b)}([^0-9]|$)' -and "
                f"$_.Name -match 'NJUD_{re.escape(codigo)}' }} | "
                f"Select-Object -First 1; "
                f"if (-not $f) {{ Write-Error 'nenhum arquivo B{b} para NJUD {codigo}'; exit 2 }}; "
                f"Copy-Item -LiteralPath $f.FullName -Destination '{dest_base}' -ErrorAction Stop; "
                f"Write-Output $f.Name"
            ),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(BASE))

        if result.returncode != 0:
            print(f"    ERRO copiando B{b}: {result.stderr.strip()[:200]}")
            return False

        # Verificação independente no disco: o arquivo existe no destino?
        nome = result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else ""
        destino = os.path.join(dest_base, nome) if nome else None
        if not destino or not os.path.isfile(destino) or os.path.getsize(destino) == 0:
            print(f"    ERRO: B{b} não confirmado no destino (esperado em {dest_base})")
            return False

        print(f"    OK: {nome} ({os.path.getsize(destino)} bytes)")

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
