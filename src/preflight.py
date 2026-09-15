"""
src/preflight.py — Pré-flight check OBRIGATÓRIO para qualquer pipeline.

Regra crítica: H: é a fonte verdadeira. Workspace é cópia temporária.
Os pipelines NÃO devem executar sem verificar disponibilidade dos dados.

Uso:
    from src.preflight import preflight_giro, preflight_njud
    
    # No início de cada script de pipeline:
    boletins = preflight_giro(janela_inicio, janela_fim)
    # ou
    boletins = preflight_njud(data_exibicao)
"""
from __future__ import annotations

import re
import shutil
import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger("preflight")

# ──────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────────────

H_BOLETINS = Path("H:/Meu Drive/RADIO TJRN CONTEUDO/00_PRODUCAO_2026/01_BOLETINS_DIARIOS/03_AUDIOS_RADIO")
H_GIRO = Path("H:/Meu Drive/RADIO TJRN CONTEUDO/00_PRODUCAO_2026/03_GIRO_NAS_COMARCAS")
WORKSPACE_BOLETINS = Path("data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS")


# ──────────────────────────────────────────────────────────────────────
# FUNÇÕES
# ──────────────────────────────────────────────────────────────────────


def verificar_h_acessivel() -> bool:
    """Verifica se o drive H: está acessível."""
    if not H_BOLETINS.exists():
        logger.error("Drive H: não acessível: %s", H_BOLETINS)
        logger.error("Conecte o Google Drive e tente novamente.")
        return False
    return True


def listar_datas_boletins_h() -> set[date]:
    """Lista datas de boletins disponíveis em H:."""
    datas = set()
    for mp3 in H_BOLETINS.rglob("*.mp3"):
        m = re.search(r"BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", mp3.name)
        if m:
            dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
            datas.add(date(ano, mes, dia))
    return datas


def copiar_boletins_de_h(janela_inicio: date, janela_fim: date) -> list[Path]:
    """Copia boletins de H: para workspace na janela especificada."""
    copiados = []
    
    for mp3 in H_BOLETINS.rglob("*.mp3"):
        m = re.search(r"BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", mp3.name)
        if not m:
            continue
        dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
        data_boletim = date(ano, mes, dia)
        
        if janela_inicio <= data_boletim <= janela_fim:
            # Criar pasta por data
            pasta_destino = WORKSPACE_BOLETINS / f"{dia:02d} {mes:02d} - {data_boletim.strftime('%a').upper()}"
            pasta_destino.mkdir(parents=True, exist_ok=True)
            
            destino_mp3 = pasta_destino / mp3.name
            if not destino_mp3.exists():
                shutil.copy2(str(mp3), str(destino_mp3))
                copiados.append(destino_mp3)
    
    return copiados


def preflight_giro(janela_inicio: date, janela_fim: date) -> list[Path]:
    """
    Pré-flight check para o GIRO.
    
    1. Verifica se H: está acessível
    2. Verifica se os boletins necessários existem no workspace
    3. Se não existirem, copia automaticamente de H:
    
    Returns:
        Lista de caminhos dos boletins disponíveis no workspace
        
    Raises:
        FileNotFoundError: Se H: não estiver acessível
    """
    logger.info("=" * 60)
    logger.info("PRE-FLIGHT CHECK: GIRO")
    logger.info("Janela: %s a %s", janela_inicio, janela_fim)
    
    # 1. Verificar H:
    if not verificar_h_acessivel():
        raise FileNotFoundError(
            f"Drive H: não acessível. Conecte o Google Drive.\n"
            f"  Caminho esperado: {H_BOLETINS}"
        )
    
    # 2. Verificar datas disponíveis em H:
    datas_h = listar_datas_boletins_h()
    datas_janela = set()
    atual = janela_inicio
    while atual <= janela_fim:
        datas_janela.add(atual)
        atual += timedelta(days=1)
    
    datas_faltando = datas_janela - datas_h
    
    if datas_faltando:
        logger.warning("Datas faltando em H:: %s", sorted(datas_faltando))
    
    # 3. Copiar boletins de H: para workspace
    logger.info("Copiando boletins de H: para workspace...")
    copiados = copiar_boletins_de_h(janela_inicio, janela_fim)
    
    if copiados:
        logger.info("✓ %d boletins copiados", len(copiados))
    else:
        logger.info("✓ Todos os boletins já existem no workspace")
    
    # 4. Verificar boletins no workspace
    boletins_workspace = []
    for mp3 in WORKSPACE_BOLETINS.rglob("*.mp3"):
        m = re.search(r"BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_", mp3.name)
        if m:
            dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
            data_boletim = date(ano, mes, dia)
            if janela_inicio <= data_boletim <= janela_fim:
                boletins_workspace.append(mp3)
    
    logger.info("✓ %d boletins disponíveis no workspace", len(boletins_workspace))
    
    if len(boletins_workspace) < 4:
        logger.warning(
            "Menos que 4 boletins na janela. "
            "Verifique se os boletins brutos estão em H: "
            "para as datas %s",
            sorted(datas_faltando) if datas_faltando else "desconhecidas"
        )
    
    logger.info("=" * 60)
    
    return boletins_workspace


def preflight_njud(data_njud: date, njud_id: str) -> list[Path]:
    """
    Pré-flight check para o NJUD.
    
    Returns:
        Lista de caminhos dos boletins NJUD
    """
    logger.info("=" * 60)
    logger.info("PRE-FLIGHT CHECK: NJUD %s (data: %s)", njud_id, data_njud)
    
    if not verificar_h_acessivel():
        raise FileNotFoundError("Drive H: não acessível.")
    
    # Verificar se existem boletins para o NJUD
    # (implementar conforme necessário)
    
    logger.info("=" * 60)
    return []


# ──────────────────────────────────────────────────────────────────────
# TESTE
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Testar com janela de exemplo
    from datetime import date
    
    janela_inicio = date(2026, 4, 16)
    janela_fim = date(2026, 4, 21)
    
    try:
        boletins = preflight_giro(janela_inicio, janela_fim)
        print(f"\n✓ Pré-flight OK: {len(boletins)} boletins")
    except FileNotFoundError as e:
        print(f"\n✗ Erro: {e}")
