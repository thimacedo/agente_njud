#!/usr/bin/env python3
"""
sync_h_para_workspace.py — Regra Crítica GIRO
==============================================
ORIGEM dos boletins do GIRO = H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\01_BOLETINS_DIARIOS\03_AUDIOS_RADIO\
DESTINO no workspace = data/processed/PRODUCAO_2026/01_BOLETINS_BRUTOS/

ESTE SCRIPT DEVE SER EXECUTADO ANTES DE QUALQUER PROCESSAMENTO DO GIRO.
Sem ele, o pipeline tenta usar dados inexistentes no workspace.

Regra de ouro: H: é a fonte de verdade. Workspace é cópia temporária.
"""
from __future__ import annotations

import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────────────
ORIGEM_H = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
DESTINO_WORKSPACE = Path("data/processed/PRODUCAO_2026/01_BOLETINS_BRUTOS")
DIVISOR = Path(__file__).resolve().parent

# ──────────────────────────────────────────────────────────────────────
# VERIFICAÇÃO
# ──────────────────────────────────────────────────────────────────────

def verificar_acesso_h() -> bool:
    """Verifica se H: está acessível."""
    if not ORIGEM_H.exists():
        print(f"✗ ERRO: H: não acessível em {ORIGEM_H}")
        print("  Conecte o Google Drive e tente novamente.")
        return False
    print(f"✓ H: acessível: {ORIGEM_H}")
    return True


def listar_datas_disponiveis() -> set[date]:
    """Lista datas disponíveis em H:."""
    datas = set()
    for mp3 in ORIGEM_H.rglob("*.mp3"):
        m = re.search(r"BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", mp3.name)
        if m:
            dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
            datas.add(date(ano, mes, dia))
    return datas


def copiar_boletins_janela(janela_inicio: date, janela_fim: date) -> int:
    """Copia boletins de H: para workspace na janela especificada."""
    copiados = 0
    
    for mp3 in ORIGEM_H.rglob("*.mp3"):
        m = re.search(r"BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", mp3.name)
        if not m:
            continue
        dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
        data_boletim = date(ano, mes, dia)
        
        if janela_inicio <= data_boletim <= janela_fim:
            # Copiar mantendo estrutura
            destino = DESTINO_WORKSPACE / f"{dia:02d} {mes:02d} - {data_boletim.strftime('%a').upper()}"
            destino.mkdir(parents=True, exist_ok=True)
            destino_mp3 = destino / mp3.name
            
            if not destino_mp3.exists():
                shutil.copy2(str(mp3), str(destino_mp3))
                copiados += 1
    
    return copiados


def main():
    print("=" * 70)
    print("SYNC H: → WORKSPACE (Regra Crítica GIRO)")
    print("=" * 70)
    print(f"Origem:  {ORIGEM_H}")
    print(f"Destino: {DESTINO_WORKSPACE}")
    print()
    
    # 1. Verificar acesso H:
    if not verificar_acesso_h():
        sys.exit(1)
    
    # 2. Criar pasta destino
    DESTINO_WORKSPACE.mkdir(parents=True, exist_ok=True)
    
    # 3. Copiar todos os boletins (sem filtro de data, para ter tudo disponível)
    print("\nCopiando boletins de H: para workspace...")
    copiados = 0
    erros = 0
    
    for mp3 in ORIGEM_H.rglob("*.mp3"):
        # Extrair data do nome
        m = re.search(r"BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", mp3.name)
        if m:
            dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
            data_boletim = date(ano, mes, dia)
            
            # Criar pasta por data
            pasta_destino = DESTINO_WORKSPACE / f"{dia:02d} {mes:02d} - {data_boletim.strftime('%a').upper()}"
            pasta_destino.mkdir(parents=True, exist_ok=True)
            
            destino_mp3 = pasta_destino / mp3.name
            if not destino_mp3.exists():
                try:
                    shutil.copy2(str(mp3), str(destino_mp3))
                    copiados += 1
                except Exception as e:
                    print(f"  ✗ Erro ao copiar {mp3.name}: {e}")
                    erros += 1
    
    print(f"\n✓ Cópias realizadas: {copiados}")
    if erros:
        print(f"✗ Erros: {erros}")
    
    # 4. Listar datas disponíveis
    datas = listar_datas_disponiveis()
    if datas:
        print(f"\nDatas disponíveis em H: ({len(datas)} dias)")
        for d in sorted(datas):
            print(f"  - {d.isoformat()}")
    
    print("\n" + "=" * 70)
    print("CONCLUÍDO")
    print("=" * 70)


if __name__ == "__main__":
    main()
