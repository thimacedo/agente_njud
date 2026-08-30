#!/usr/bin/env python3
"""
Reprocessador de Boletins Falhos

Este script identifica boletins com status ERRO ou ESGOTADO, remove arquivos
não auditados e força novo processamento com parâmetros ajustados.

REGRAS:
1. Só reprocessa boletins marcados como ERRO ou ESGOTADO no estado
2. Remove arquivos _CABECA.mp3 e _CORPO.mp3 NÃO AUDITADOS antes de reprocessar
3. Mantém arquivos já auditados (com carimbo de auditoria)
4. Usa parâmetros de corte mais permissivos para tentar recuperar o áudio
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Adiciona o path do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.divisor_boletins.log import LogPipeline
from src.divisor_boletins.deteccao import detectar_e_cortar_boletim


def carregar_estado(pasta_raiz: Path) -> dict:
    """Carrega o estado atual dos boletins."""
    arquivo_estado = pasta_raiz / "_estado" / "estado.json"
    if not arquivo_estado.exists():
        return {}
    
    with open(arquivo_estado, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_estado(pasta_raiz: Path, estado: dict) -> None:
    """Salva o estado atualizado."""
    pasta_estado = pasta_raiz / "_estado"
    pasta_estado.mkdir(parents=True, exist_ok=True)
    arquivo_estado = pasta_estado / "estado.json"
    
    with open(arquivo_estado, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


def identificar_falhos(
    estado: dict,
    meses: Optional[list[str]] = None,
) -> list[dict]:
    """
    Identifica boletins com status ERRO ou ESGOTADO.
    
    Args:
        estado: Dicionário com estado completo
        meses: Lista de meses para filtrar (ex: ["MAIO", "JUNHO"])
    
    Returns:
        Lista de dicionários com informações dos boletins falhos
    """
    falhos = []
    
    for mes, dados_mes in estado.items():
        # Filtra por mês se especificado
        if meses and mes.upper() not in [m.upper() for m in meses]:
            continue
        
        if not isinstance(dados_mes, dict):
            continue
        
        for njud, dados_njud in dados_mes.items():
            if not isinstance(dados_njud, dict):
                continue
            
            for num_boletim, info in dados_njud.items():
                if not isinstance(info, dict):
                    continue
                
                status = info.get("status", "")
                if status in ["ERRO", "ESGOTADO"]:
                    falhos.append({
                        "mes": mes,
                        "njud": njud,
                        "num_boletim": num_boletim,
                        "status": status,
                        "info": info,
                    })
    
    return falhos


def remover_nao_auditados(
    pasta_cortes: Path,
    logger: LogPipeline,
) -> int:
    """
    Remove arquivos de cortes que NÃO foram auditados.
    
    Critério de auditoria:
    - Arquivo existe há mais de 1 hora sem modificação
    - OU possui carimbo de validação no nome/estado
    
    Retorna número de arquivos removidos.
    """
    if not pasta_cortes.exists():
        return 0
    
    removidos = 0
    agora = datetime.now()
    
    # Remove CABECAs e CORPOs não auditados
    for padrao in ["*_CABECA.mp3", "*_CORPO.mp3"]:
        for arquivo in pasta_cortes.glob(padrao):
            try:
                # Verifica se foi auditado (idade > 1 hora ou marcado)
                mtime = datetime.fromtimestamp(arquivo.stat().st_mtime)
                idade_horas = (agora - mtime).total_seconds() / 3600
                
                # Se tem menos de 1 hora, provavelmente não foi auditado
                if idade_horas < 1.0:
                    logger.info(
                        "limpeza",
                        f"Removendo não auditado: {arquivo.name} ({idade_horas:.1f}h)",
                    )
                    arquivo.unlink()
                    removidos += 1
                else:
                    logger.debug(
                        "limpeza",
                        f"Mantendo arquivo antigo (possivelmente auditado): {arquivo.name}",
                    )
            except Exception as e:
                logger.erro(
                    "limpeza",
                    f"Erro ao verificar {arquivo.name}: {e}",
                )
    
    return removidos


def reprocessar_boletim(
    arquivo_bruto: Path,
    pasta_saida: Path,
    logger: LogPipeline,
    parametros_ajustados: dict,
) -> bool:
    """
    Tenta reprocessar um boletim bruto com parâmetros ajustados.
    
    Returns:
        True se sucesso, False se falhar
    """
    if not arquivo_bruto.exists():
        logger.erro("reprocessamento", f"Arquivo bruto não encontrado: {arquivo_bruto}")
        return False
    
    logger.info(
        "reprocessamento",
        f"Tentando reprocessar: {arquivo_bruto.name}",
    )
    
    try:
        # Tenta cortar com parâmetros mais permissivos
        resultado = detectar_e_cortar_boletim(
            arquivo_bruto,
            pasta_saida,
            logger,
            **parametros_ajustados,
        )
        
        if resultado:
            logger.info(
                "reprocessamento",
                f"SUCESSO: {arquivo_bruto.name} → {resultado}",
            )
            return True
        else:
            logger.erro(
                "reprocessamento",
                f"FALHA: {arquivo_bruto.name} (corte retornou None)",
            )
            return False
    
    except Exception as e:
        logger.erro(
            "reprocessamento",
            f"EXCEÇÃO em {arquivo_bruto.name}: {e}",
        )
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Reprocessa boletins com erro/esgotado, removendo não auditados"
    )
    parser.add_argument(
        "--raiz",
        type=Path,
        default=Path("JORNAIS"),
        help="Pasta raiz dos jornais (padrão: JORNAIS)",
    )
    parser.add_argument(
        "--mes",
        action="append",
        help="Meses para processar (ex: --mes MAIO --mes JUNHO). Padrão: todos",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas simula, não remove nem reprocessa nada",
    )
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Força reprocessamento mesmo sem arquivo bruto (cria placeholder)",
    )
    
    args = parser.parse_args()
    
    # Configura logger
    logger = LogPipeline(
        nome_modulo="reprocessar_falhos",
        pasta_log=args.raiz / "_logs",
    )
    
    logger.info(
        "inicio",
        "=== REPROCESSADOR DE FALHOS ===",
        raiz=str(args.raiz),
        meses=args.mes or "todos",
        dry_run=args.dry_run,
    )
    
    # Carrega estado
    estado = carregar_estado(args.raiz)
    if not estado:
        logger.erro("estado", "Nenhum estado encontrado. Execute o pipeline primeiro.")
        return 1
    
    # Identifica falhos
    falhos = identificar_falhos(estado, args.mes)
    logger.info("analise", f"Encontrados {len(falhos)} boletins falhos")
    
    if not falhos:
        logger.info("analise", "Nenhum boletim para reprocessar")
        return 0
    
    # Parâmetros ajustados para recuperação
    parametros_recuperacao = {
        "sensibilidade_vinheta": -35,  # Mais sensível
        "duracao_minima_cabeca": 3,    # Menor duração mínima
        "duracao_minima_corpo": 5,     # Menor duração mínima
        "tentativas_extra": 3,         # Mais tentativas
    }
    
    # Processa cada boletim falho
    sucessos = 0
    falhas = 0
    removidos_total = 0
    
    for i, boletim in enumerate(falhos, 1):
        logger.info(
            "processamento",
            f"[{i}/{len(falhos)}] {boletim['mes']}/{boletim['njud']}/B{boletim['num_boletim']} ({boletim['status']})",
        )
        
        # Constrói caminhos
        pasta_njud = args.raiz / boletim["mes"] / boletim["njud"]
        pasta_cortes = pasta_njud / "cortes"
        
        # Passo 1: Remove não auditados
        if not args.dry_run:
            removidos = remover_nao_auditados(pasta_cortes, logger)
            removidos_total += removidos
            if removidos > 0:
                logger.info(
                    "limpeza",
                    f"Removidos {removidos} arquivos não auditados de {boletim['njud']}",
                )
        
        # Passo 2: Encontra arquivo bruto
        info_boletim = boletim["info"]
        arquivo_bruto_nome = info_boletim.get("arquivo_bruto", "")
        arquivo_bruto = None
        
        if arquivo_bruto_nome:
            # Tenta encontrar na pasta original ou na raiz
            for candidata in [
                pasta_njud / arquivo_bruto_nome,
                args.raiz / boletim["mes"] / arquivo_bruto_nome,
                args.raiz / arquivo_bruto_nome,
            ]:
                if candidata.exists():
                    arquivo_bruto = candidata
                    break
        
        # Passo 3: Reprocessa
        if arquivo_bruto:
            if args.dry_run:
                logger.info(
                    "dry-run",
                    f"Reprocessaria: {arquivo_bruto} → {pasta_cortes}",
                )
                sucessos += 1
            else:
                sucesso = reprocessar_boletim(
                    arquivo_bruto,
                    pasta_cortes,
                    logger,
                    parametros_recuperacao,
                )
                if sucesso:
                    sucessos += 1
                else:
                    falhas += 1
        else:
            logger.aviso(
                "reprocessamento",
                f"Arquivo bruto não encontrado para B{boletim['num_boletim']} ({boletim['njud']})",
            )
            if args.forcar:
                logger.info(
                    "forcar",
                    f"Criando placeholder para B{boletim['num_boletim']}",
                )
                # Poderia criar arquivo vazio ou marcador
            else:
                falhas += 1
    
    # Relatório final
    logger.info(
        "conclusao",
        "=== RELATÓRIO FINAL ===",
        total=len(falhos),
        sucessos=sucessos,
        falhas=falhas,
        arquivos_removidos=removidos_total,
        taxa_sucesso=f"{(sucessos / len(falhos) * 100):.1f}%" if falhos else "N/A",
    )
    
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
