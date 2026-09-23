#!/usr/bin/env python3
"""
Orquestrador de processamento de setembro.
Processa 1 audio por vez, do mais antigo ao mais novo.
Pula boletins ja editados por SAM.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SENTENCA_DIR = PROJECT_ROOT / "setembro"
ROTEIROS_DIR = PROJECT_ROOT / "setembro"

# Mapeamento dia -> roteiros (do arquivo baixado)
ROTEIROS_POR_DIA = {
    "01": "roteiros_2026-09-01.txt",
    "02": "roteiros_2026-09-02.txt",
    "03": "roteiros_2026-09-03.txt",
    "04": "roteiros_2026-09-04.txt",
    "08": "roteiros_2026-09-08.txt",
    "09": "roteiros_2026-09-09.txt",
    "10": "roteiros_2026-09-10.txt",
    "11": "roteiros_2026-09-11.txt",
    "14": "roteiros_2026-09-14.txt",
    "15": "roteiros_2026-09-15.txt",
    "16": "roteiros_2026-09-16.txt",
    "17": "roteiros_2026-09-17.txt",
    "18": "roteiros_2026-09-18.txt",
    "21": "roteiros_2026-09-21.txt",
    "22": "roteiros_2026-09-22.txt",
    "23": "roteiros_2026-09-23.txt",
}

# Parse da lista completa para identificar quais boletins SAM editou
# Formato: (dia, lista de boletins SAM)
def parse_sam_exceptions():
    """Identifica boletins editados por SAM a partir da lista."""
    sam_boletins = {}  # dia -> set de números B
    
    lista_path = Path(r"C:\Users\THIAGO\AppData\Roaming\Hermes\composer-pastes\pasted_content_2026-09-23_12-29-53-923_81881c.txt")
    if not lista_path.exists():
        print(f"⚠️ Lista não encontrada: {lista_path}")
        return sam_boletins
    
    texto = lista_path.read_text(encoding="utf-8")
    
    for line in texto.strip().split("\n"):
        if "SAM" not in line:
            continue
        
        # Extrair dia (DD no formato DD/MM)
        m_dia = re.search(r'(\d{2})/\d{2}', line)
        if not m_dia:
            continue
        dia = m_dia.group(1)
        
        # Extrair número do boletim (B seguido de número)
        m_b = re.search(r'B(\d{1,2})', line)
        if not m_b:
            continue
        b_num = int(m_b.group(1))
        
        if dia not in sam_boletins:
            sam_boletins[dia] = set()
        sam_boletins[dia].add(b_num)
    
    return sam_boletins


def get_audio_files():
    """Lista e ordena arquivos de áudio por data."""
    audios = []
    
    for f in SENTENCA_DIR.glob("*.mp3"):
        nome = f.name
        
        # Extrair dia do nome do arquivo
        # Formatos: "01 SET B1-B5.mp3", "03 - SET - B1-B4.mp3", "090 SET B1-B5.mp3",
        #           "10 ST B1-B5.mp3", "16 SET B1B5.mp3", "04 SET - B6 E B7.mp3"
        m = re.match(r'(\d{2,3})\s*(?:-\s*)?(?:SET|ST)', nome, re.I)
        if not m:
            continue
        
        dia_raw = m.group(1).zfill(2)
        # Corrigir "090" -> "09"
        if len(dia_raw) == 3 and dia_raw.endswith("0"):
            dia_raw = dia_raw[:2]
        
        # Extrair faixa de boletins (suporta "B1-B5", "B1B5", "B6 E B7")
        m_faixa = re.search(r'B(\d{1,2})\s*(?:[-–]|E)\s*B?(\d{1,2})', nome, re.I)
        if not m_faixa:
            continue
        
        b_ini = int(m_faixa.group(1))
        b_fim = int(m_faixa.group(2))
        
        audios.append({
            "path": f,
            "nome": nome,
            "dia": dia_raw,
            "b_ini": b_ini,
            "b_fim": b_fim,
        })
    
    # Ordenar por dia
    audios.sort(key=lambda x: x["dia"])
    return audios


def processar_audio(audio_info, sam_boletins):
    """Processa 1 arquivo de áudio."""
    dia = audio_info["dia"]
    nome = audio_info["nome"]
    path = audio_info["path"]
    b_ini = audio_info["b_ini"]
    b_fim = audio_info["b_fim"]
    
    # Verificar se todos os boletins deste arquivo são SAM
    sam_neste = sam_boletins.get(dia, set())
    todos_sam = all(b in sam_neste for b in range(b_ini, b_fim + 1))
    
    if todos_sam:
        print(f"\n⏭️ PULANDO {nome} (todos os boletins já editados por SAM)")
        return {"status": "pulado_sam"}
    
    # Roteiro correspondente
    roteiro_file = ROTEIROS_DIR / ROTEIROS_POR_DIA.get(dia, "")
    if not roteiro_file.exists():
        print(f"\n⚠️ Roteiro não encontrado para dia {dia}: {ROTEIROS_POR_DIA.get(dia)}")
        return {"status": "erro", "motivo": "roteiro_nao_encontrado"}
    
    print(f"\n{'='*60}")
    print(f"🎵 PROCESSANDO: {nome}")
    print(f"   Dia: {dia}/09 | Boletins: B{b_ini}-B{b_fim}")
    if sam_neste:
        nao_sam = [b for b in range(b_ini, b_fim + 1) if b not in sam_neste]
        print(f"   SAM editou: {sorted(sam_neste & set(range(b_ini, b_fim+1)))}")
        print(f"   Para processar: {nao_sam}")
    print(f"   Roteiro: {roteiro_file.name}")
    print(f"{'='*60}")
    
    # Comando do pipeline - usar .venv_pipeline isolado
    venv_python = PROJECT_ROOT / ".venv_pipeline" / "Scripts" / "python.exe"
    cmd = [
        str(venv_python),
        str(PROJECT_ROOT / "scripts_pipeline" / "boletim" / "processar_boletim_canonico.py"),
        str(path),
        "--roteiros", str(ROTEIROS_DIR),
    ]
    
    print(f"   Comando: {' '.join(cmd)}")
    print(f"   Iniciando processamento...\n")
    
    inicio = time.time()
    
    # Ambiente isolado (sem paths do Hermes)
    env_limpo = {
        "PATH": ":".join(p for p in os.environ.get("PATH", "").split(":") if "hermes" not in p.lower()),
        "PYTHONPATH": str(PROJECT_ROOT / "scripts_pipeline"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONIOENCODING": "utf-8",
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
        "SYSTEMDRIVE": os.environ.get("SYSTEMDRIVE", "C:"),
        "TEMP": os.environ.get("TEMP", "C:\\Temp"),
        "TMP": os.environ.get("TMP", "C:\\Temp"),
        "HOMEDRIVE": os.environ.get("HOMEDRIVE", "C:"),
        "HOMEPATH": os.environ.get("HOMEPATH", "\\Users\\THIAGO"),
        "USERPROFILE": os.environ.get("USERPROFILE", "C:\\Users\\THIAGO"),
    }
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=1800,  # 30 min max
            cwd=str(PROJECT_ROOT),
            env=env_limpo,
        )
        
        duracao = time.time() - inicio
        
        if result.returncode == 0:
            print(f"\n   ✅ CONCLUÍDO em {duracao:.0f}s")
            if result.stdout:
                # Últimas linhas do output
                linhas = result.stdout.strip().split("\n")
                for l in linhas[-5:]:
                    print(f"   {l}")
            return {"status": "sucesso", "duracao": duracao}
        else:
            print(f"\n   ❌ ERRO (exit {result.returncode}) em {duracao:.0f}s")
            stderr_txt = result.stderr or ""
            if stderr_txt:
                print(f"   STDERR: {stderr_txt[-500:]}")
            return {"status": "erro", "duracao": duracao, "stderr": stderr_txt[-500:]}
    
    except subprocess.TimeoutExpired:
        print(f"\n   ⏰ TIMEOUT após 30 min")
        return {"status": "timeout"}
    except Exception as e:
        import traceback
        print(f"\n   ❌ EXCEPTION: {e}")
        traceback.print_exc()
        return {"status": "erro", "motivo": str(e)}


def main():
    print("=" * 60)
    print("🎙️  PROCESSAMENTO DE BOLETINS — SETEMBRO 2026")
    print("=" * 60)
    
    sam_boletins = parse_sam_exceptions()
    audios = get_audio_files()
    
    print(f"\n📊 Resumo:")
    print(f"   Arquivos de áudio: {len(audios)}")
    print(f"   Dias com SAM: {sorted(sam_boletins.keys())}")
    print(f"   Roteiros disponíveis: {len(list(ROTEIROS_DIR.glob('roteiros_2026-09-*.txt')))}")
    
    print(f"\n📋 Ordem de processamento:")
    pulados = 0
    for a in audios:
        dia = a["dia"]
        sam_neste = sam_boletins.get(dia, set())
        todos_sam = all(b in sam_neste for b in range(a["b_ini"], a["b_fim"] + 1))
        status = "⏭️ PULAR (SAM)" if todos_sam else "✅ PROCESSAR"
        if todos_sam:
            pulados += 1
        print(f"   {status} | {a['nome']} (B{a['b_ini']}-B{a['b_fim']})")
    
    print(f"\n   Total: {len(audios) - pulados} para processar, {pulados} pulados")
    
    # Processar 1 por vez
    resultados = []
    for audio in audios:
        resultado = processar_audio(audio, sam_boletins)
        resultados.append({**audio, **resultado})
        
        # Salvar progresso
        with open(SENTENCA_DIR / "progresso_processamento.json", "w", encoding="utf-8") as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False, default=str)
    
    # Resumo final
    print(f"\n{'='*60}")
    print(f"📊 RESUMO FINAL")
    print(f"{'='*60}")
    ok = sum(1 for r in resultados if r.get("status") == "sucesso")
    erros = sum(1 for r in resultados if r.get("status") == "erro")
    pulos = sum(1 for r in resultados if r.get("status") == "pulado_sam")
    print(f"   ✅ Sucesso: {ok}")
    print(f"   ❌ Erro: {erros}")
    print(f"   ⏭️ Pulados (SAM): {pulos}")


if __name__ == "__main__":
    main()
