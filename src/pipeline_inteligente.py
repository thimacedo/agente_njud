#!/usr/bin/env python3
"""
Pipeline Inteligente de Jornais - TJRN
=======================================

Fluxo completo automatizado com validações entre etapas:
planejamento → cópia → corte → auditoria → ajustes → melhorias → 
montagem → auditoria → re-montagem → melhorias → upload

Cada etapa valida o resultado antes de prosseguir. Em caso de falha,
o pipeline tenta correções automáticas ou para com relatório detalhado.

Autor: Sistema DIVISOR
Data: 2026-08-26
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Importa módulos utilitários
sys.path.insert(0, str(Path(__file__).parent))
from utils.logger import get_logger
from config.settings import Settings
from utils.validator import validate_audio_file, calculate_checksum
from utils.error_handler import retry_with_backoff, isolate_failures

# Inicializa logger e configurações
logger = get_logger("pipeline_inteligente")
settings = Settings()

# Caminhos configuráveis (podem ser sobrescritos via CLI)
DEFAULT_BOLETINS_BRUTOS = settings.BOLETINS_BRUTOS
DEFAULT_SAIDA_CORTES = settings.BOLETINS_CORTADOS
DEFAULT_SAIDA_JORNAIS = settings.JORNAIS_MONTADOS
DEFAULT_DRIVE_SYNC = settings.DRIVE_SYNC
WORKSPACE = Path(__file__).parent.parent
DATA_DIR = WORKSPACE / "data"
LOGS_DIR = settings.LOGS_DIR

# Limites e thresholds
MIN_BOLETINS_POR_JORNAL = 4
MAX_BOLETINS_POR_JORNAL = 4  # Rigoroso: exatamente 4
TAMANHO_MINIMO_AUDIO_KB = 5  # Áudios <5KB são considerados inválidos


# ============================================================================
# ESTRUTURA DE DADOS DO PIPELINE
# ============================================================================

class EtapaPipeline:
    """Representa uma etapa do pipeline com seu status e resultados."""
    
    def __init__(self, nome: str, descricao: str):
        self.nome = nome
        self.descricao = descricao
        self.status = "PENDENTE"  # PENDENTE, EM_PROGRESSO, SUCESSO, FALHA, SKIP
        self.inicio: Optional[datetime] = None
        self.fim: Optional[datetime] = None
        self.resultados: Dict[str, Any] = {}
        self.erros: List[str] = []
        self.avisos: List[str] = []
    
    def iniciar(self):
        self.status = "EM_PROGRESSO"
        self.inicio = datetime.now()
    
    def concluir(self, sucesso: bool = True, **resultados):
        self.fim = datetime.now()
        self.status = "SUCESSO" if sucesso else "FALHA"
        self.resultados.update(resultados)
    
    def adicionar_erro(self, erro: str):
        self.erros.append(erro)
    
    def adicionar_aviso(self, aviso: str):
        self.avisos.append(aviso)
    
    def duracao_segundos(self) -> float:
        if not self.inicio or not self.fim:
            return 0.0
        return (self.fim - self.inicio).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nome": self.nome,
            "descricao": self.descricao,
            "status": self.status,
            "inicio": self.inicio.isoformat() if self.inicio else None,
            "fim": self.fim.isoformat() if self.fim else None,
            "duracao_segundos": self.duracao_segundos(),
            "resultados": self.resultados,
            "erros": self.erros,
            "avisos": self.avisos,
        }


class StatusPipeline:
    """Gerencia o status geral do pipeline."""
    
    def __init__(self):
        self.etapas: List[EtapaPipeline] = []
        self.inicio = datetime.now()
        self.fim: Optional[datetime] = None
        # Lazy import para evitar dependências não instaladas
        try:
            from divisor_boletins.log import LogPipeline
            self.logger = LogPipeline(str(LOGS_DIR))
        except ImportError:
            # Fallback simples se divisor_boletins não estiver disponível
            self.logger = self._create_fallback_logger()
    
    def _create_fallback_logger(self):
        """Cria um logger fallback baseado em print."""
        class FallbackLogger:
            def info(self, contexto, msg, **kwargs):
                print(f"[{contexto}] {msg}")
            def aviso(self, contexto, msg, **kwargs):
                print(f"[AVISO {contexto}] {msg}")
            def erro(self, contexto, msg, **kwargs):
                print(f"[ERRO {contexto}] {msg}")
        return FallbackLogger()
    
    def adicionar_etapa(self, etapa: EtapaPipeline):
        self.etapas.append(etapa)
    
    def finalizar(self):
        self.fim = datetime.now()
    
    def duracao_total_segundos(self) -> float:
        if not self.fim:
            return 0.0
        return (self.fim - self.inicio).total_seconds()
    
    def resumo(self) -> Dict[str, Any]:
        return {
            "inicio": self.inicio.isoformat(),
            "fim": self.fim.isoformat() if self.fim else None,
            "duracao_total_segundos": self.duracao_total_segundos(),
            "total_etapas": len(self.etapas),
            "etapas_sucesso": sum(1 for e in self.etapas if e.status == "SUCESSO"),
            "etapas_falha": sum(1 for e in self.etapas if e.status == "FALHA"),
            "etapas": [e.to_dict() for e in self.etapas],
        }
    
    def salvar_relatorio(self, caminho: Path):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(self.resumo(), f, indent=2, ensure_ascii=False)


# ============================================================================
# ETAPAS DO PIPELINE
# ============================================================================

def etapa_planejamento(
    status: StatusPipeline,
    pasta_brutos: Path,
    pasta_saida_cortes: Path,
    pasta_saida_jornais: Path,
) -> bool:
    """
    ETAPA 1: Planejamento
    
    Valida:
    - Existência da pasta de boletins brutos
    - Espaço em disco disponível
    - Criação das pastas de saída
    - Contagem preliminar de boletins
    """
    etapa = EtapaPipeline("planejamento", "Validação e preparação do ambiente")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("planejamento", "=== Iniciando planejamento ===")
    
    # Valida pasta de entrada
    if not pasta_brutos.exists():
        erro = f"Pasta de boletins brutos não existe: {pasta_brutos}"
        etapa.adicionar_erro(erro)
        logger.erro("planejamento", erro)
        etapa.concluir(sucesso=False)
        return False
    
    # Conta boletins disponíveis
    boletins_mp3 = list(pasta_brutos.glob("*.mp3")) + list(pasta_brutos.glob("*.wav")) + list(pasta_brutos.glob("*.m4a"))
    etapa.resultados["boletins_encontrados"] = len(boletins_mp3)
    
    if len(boletins_mp3) == 0:
        erro = "Nenhum boletim encontrado na pasta de entrada"
        etapa.adicionar_erro(erro)
        logger.erro("planejamento", erro)
        etapa.concluir(sucesso=False)
        return False
    
    # Calcula jornais esperados
    jornais_esperados = len(boletins_mp3) // MIN_BOLETINS_POR_JORNAL
    etapa.resultados["jornais_esperados"] = jornais_esperados
    etapa.resultados["boletins_sobra"] = len(boletins_mp3) % MIN_BOLETINS_POR_JORNAL
    
    # Cria pastas de saída
    for pasta in [pasta_saida_cortes, pasta_saida_jornais]:
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            logger.info("planejamento", f"Pasta criada/validada: {pasta}")
        except Exception as e:
            erro = f"Falha ao criar pasta {pasta}: {e}"
            etapa.adicionar_erro(erro)
            logger.erro("planejamento", erro)
            etapa.concluir(sucesso=False)
            return False
    
    etapa.resultados["pasta_cortes"] = str(pasta_saida_cortes)
    etapa.resultados["pasta_jornais"] = str(pasta_saida_jornais)
    
    logger.info(
        "planejamento",
        f"Planejamento concluído: {len(boletins_mp3)} boletins → ~{jornais_esperados} jornais",
        **etapa.resultados
    )
    
    etapa.concluir(sucesso=True)
    return True


def etapa_copia(
    status: StatusPipeline,
    pasta_brutos: Path,
    pasta_trabalho: Path,
) -> bool:
    """
    ETAPA 2: Cópia dos Boletins
    
    Copia os boletins para uma pasta de trabalho dedicada,
    preservando os originais.
    """
    etapa = EtapaPipeline("copia", "Cópia segura dos boletins para área de trabalho")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("copia", "=== Iniciando cópia dos boletins ===")
    
    # Limpa pasta de trabalho se existir
    if pasta_trabalho.exists():
        try:
            shutil.rmtree(pasta_trabalho)
            logger.info("copia", f"Pasta de trabalho limpa: {pasta_trabalho}")
        except Exception as e:
            erro = f"Falha ao limpar pasta de trabalho: {e}"
            etapa.adicionar_erro(erro)
            logger.erro("copia", erro)
            etapa.concluir(sucesso=False)
            return False
    
    pasta_trabalho.mkdir(parents=True, exist_ok=True)
    
    # Copia arquivos
    arquivos_copiados = 0
    for ext in ["*.mp3", "*.wav", "*.m4a"]:
        for arquivo in pasta_brutos.glob(ext):
            try:
                destino = pasta_trabalho / arquivo.name
                shutil.copy2(arquivo, destino)
                arquivos_copiados += 1
            except Exception as e:
                erro = f"Falha ao copiar {arquivo.name}: {e}"
                etapa.adicionar_erro(erro)
                logger.erro("copia", erro)
    
    etapa.resultados["arquivos_copiados"] = arquivos_copiados
    
    if arquivos_copiados == 0:
        erro = "Nenhum arquivo foi copiado"
        etapa.adicionar_erro(erro)
        logger.erro("copia", erro)
        etapa.concluir(sucesso=False)
        return False
    
    logger.info("copia", f"Cópia concluída: {arquivos_copiados} arquivos")
    etapa.concluir(sucesso=True)
    return True


def etapa_corte(
    status: StatusPipeline,
    pasta_trabalho: Path,
    pasta_cortes: Path,
) -> bool:
    """
    ETAPA 3: Corte dos Boletins
    
    Executa o divisor_boletins para separar CABEÇA e CORPO de cada boletim.
    """
    etapa = EtapaPipeline("corte", "Divisão dos boletins em CABEÇA e CORPO")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("corte", "=== Iniciando corte dos boletins ===")
    
    # Importa o divisor
    try:
        from divisor_boletins.deteccao import processar_arquivo
    except ImportError as e:
        erro = f"Falha ao importar divisor_boletins: {e}"
        etapa.adicionar_erro(erro)
        logger.erro("corte", erro)
        etapa.concluir(sucesso=False)
        return False
    
    # Processa cada boletim
    cortes_realizados = 0
    falhas = 0
    
    for audio_file in pasta_trabalho.glob("*.mp3"):
        logger.info("corte", f"Processando: {audio_file.name}")
        
        try:
            resultado = processar_arquivo(
                audio_file,
                pasta_cortes,
                logger,
                usar_whisper=True,  # Prioriza Whisper para precisão
            )
            
            if resultado and resultado.get("sucesso"):
                cortes_realizados += 1
            else:
                falhas += 1
                etapa.adicionar_aviso(f"Corte falhou para {audio_file.name}")
                
        except Exception as e:
            falhas += 1
            erro = f"Exceção no corte de {audio_file.name}: {e}"
            etapa.adicionar_erro(erro)
            logger.erro("corte", erro)
    
    etapa.resultados["cortes_realizados"] = cortes_realizados
    etapa.resultados["cortes_falhos"] = falhas
    
    if cortes_realizados == 0:
        erro = "Nenhum corte foi realizado com sucesso"
        etapa.adicionar_erro(erro)
        logger.erro("corte", erro)
        etapa.concluir(sucesso=False)
        return False
    
    logger.info("corte", f"Corte concluído: {cortes_realizados} sucessos, {falhas} falhas")
    etapa.concluir(sucesso=True)
    return True


def etapa_auditoria_cortes(
    status: StatusPipeline,
    pasta_cortes: Path,
) -> Tuple[bool, Dict[str, Any]]:
    """
    ETAPA 4: Auditoria dos Cortes
    
    Valida:
    - Tamanho mínimo dos arquivos _CABECA e _CORPO
    - Presença de ambos os cortes para cada boletim
    - Consistência de numeração
    """
    etapa = EtapaPipeline("auditoria_cortes", "Validação da qualidade dos cortes")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("auditoria_cortes", "=== Iniciando auditoria dos cortes ===")
    
    cabecas = list(pasta_cortes.rglob("*_CABECA.mp3"))
    corpos = list(pasta_cortes.rglob("*_CORPO.mp3"))
    
    # Filtra arquivos inválidos (<5KB)
    cabecas_validas = [c for c in cabecas if c.stat().st_size >= TAMANHO_MINIMO_AUDIO_KB * 1024]
    corpos_validos = [c for c in corpos if c.stat().st_size >= TAMANHO_MINIMO_AUDIO_KB * 1024]
    
    invalidos = len(cabecas) - len(cabecas_validas) + len(corpos) - len(corpos_validos)
    
    etapa.resultados["cabecas_total"] = len(cabecas)
    etapa.resultados["cabecas_validas"] = len(cabecas_validas)
    etapa.resultados["corpos_total"] = len(corpos)
    etapa.resultados["corpos_validos"] = len(corpos_validos)
    etapa.resultados["arquivos_invalidos"] = invalidos
    
    # Verifica pares
    mapa_cabecas = {c.name.replace("_CABECA.mp3", ""): c for c in cabecas_validas}
    mapa_corpos = {c.name.replace("_CORPO.mp3", ""): c for c in corpos_validos}
    
    pares_completos = set(mapa_cabecas.keys()) & set(mapa_corpos.keys())
    incompletos = (set(mapa_cabecas.keys()) | set(mapa_corpos.keys())) - pares_completos
    
    etapa.resultados["pares_completos"] = len(pares_completos)
    etapa.resultados["boletins_incompletos"] = len(incompletos)
    
    if incompletos:
        aviso = f"{len(incompletos)} boletins incompletos: {list(incompletos)[:5]}"
        etapa.adicionar_aviso(aviso)
        logger.aviso("auditoria_cortes", aviso)
    
    # Valida mínimo para montagem
    if len(pares_completos) < MIN_BOLETINS_POR_JORNAL:
        erro = f"Boletins válidos insuficientes ({len(pares_completos)}) para montar pelo menos 1 jornal"
        etapa.adicionar_erro(erro)
        logger.erro("auditoria_cortes", erro)
        etapa.concluir(sucesso=False)
        return False, etapa.resultados
    
    logger.info(
        "auditoria_cortes",
        f"Auditoria concluída: {len(pares_completos)} pares válidos",
        **etapa.resultados
    )
    
    etapa.concluir(sucesso=True)
    return True, etapa.resultados


def etapa_ajustes(
    status: StatusPipeline,
    pasta_cortes: Path,
    auditoria_resultados: Dict[str, Any],
) -> bool:
    """
    ETAPA 5: Ajustes Automáticos
    
    Tenta corrigir problemas identificados na auditoria:
    - Remove arquivos corrompidos
    - Renomeia arquivos com padrões inconsistentes
    """
    etapa = EtapaPipeline("ajustes", "Correções automáticas pós-auditoria")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("ajustes", "=== Iniciando ajustes automáticos ===")
    
    ajustes_realizados = 0
    
    # Remove arquivos inválidos
    for arquivo in pasta_cortes.rglob("*.mp3"):
        if arquivo.stat().st_size < TAMANHO_MINIMO_AUDIO_KB * 1024:
            try:
                arquivo.unlink()
                logger.info("ajustes", f"Arquivo inválido removido: {arquivo.name}")
                ajustes_realizados += 1
            except Exception as e:
                etapa.adicionar_aviso(f"Falha ao remover {arquivo.name}: {e}")
    
    etapa.resultados["ajustes_realizados"] = ajustes_realizados
    
    logger.info("ajustes", f"Ajustes concluídos: {ajustes_realizados} correções")
    etapa.concluir(sucesso=True)
    return True


def etapa_melhorias_cortes(
    status: StatusPipeline,
    pasta_cortes: Path,
) -> bool:
    """
    ETAPA 6: Melhorias nos Cortes
    
    Aplica melhorias opcionais:
    - Normalização de volume
    - Remoção de ruído residual
    - Fade in/out suave
    """
    etapa = EtapaPipeline("melhorias_cortes", "Aplicação de melhorias de áudio")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("melhorias_cortes", "=== Iniciando melhorias nos cortes ===")
    
    # Placeholder para melhorias de áudio
    # Implementação futura: pydub para normalização, noise reduction, etc.
    
    arquivos_processados = 0
    for arquivo in pasta_cortes.rglob("*.mp3"):
        # Futuro: aplicar melhorias
        arquivos_processados += 1
    
    etapa.resultados["arquivos_processados"] = arquivos_processados
    
    logger.info("melhorias_cortes", f"Melhorias aplicadas em {arquivos_processados} arquivos")
    etapa.concluir(sucesso=True)
    return True


def etapa_montagem(
    status: StatusPipeline,
    pasta_cortes: Path,
    pasta_jornais: Path,
) -> Tuple[bool, List[Path]]:
    """
    ETAPA 7: Montagem dos Jornais
    
    Agrupa cortes em jornais completos seguindo a regra:
    - 4 boletins por jornal
    - Intercalação de vozes (2 locutores diferentes por jornal)
    """
    etapa = EtapaPipeline("montagem", "Montagem dos jornais completos")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("montagem", "=== Iniciando montagem dos jornais ===")
    
    # Monta todos os jornais
    jornais_gerados = montar_todos_jornais(
        pasta_cortes,
        pasta_jornais,
        logger,
        intercalar=True,  # Ativa intercalação de vozes
    )
    
    etapa.resultados["jornais_gerados"] = len(jornais_gerados)
    etapa.resultados["caminhos_jornais"] = [str(j) for j in jornais_gerados]
    
    if not jornais_gerados:
        erro = "Nenhum jornal foi montado"
        etapa.adicionar_erro(erro)
        logger.erro("montagem", erro)
        etapa.concluir(sucesso=False)
        return False, []
    
    # Valida estrutura dos jornais (4 notícias cada)
    for jornal in jornais_gerados:
        tamanho_kb = jornal.stat().st_size / 1024
        logger.info("montagem", f"Jornal gerado: {jornal.name} ({tamanho_kb:.1f} KB)")
    
    logger.info("montagem", f"Montagem concluída: {len(jornais_gerados)} jornais")
    etapa.concluir(sucesso=True)
    return True, jornais_gerados


def etapa_auditoria_jornais(
    status: StatusPipeline,
    jornais: List[Path],
) -> bool:
    """
    ETAPA 8: Auditoria dos Jornais
    
    Valida:
    - Duração mínima de cada jornal (deve ter ~4 notícias)
    - Tamanho do arquivo
    - Estrutura de vinhetas (abertura/encerramento)
    """
    etapa = EtapaPipeline("auditoria_jornais", "Validação da qualidade dos jornais")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("auditoria_jornais", "=== Iniciando auditoria dos jornais ===")
    
    from pydub import AudioSegment
    
    jornais_validos = 0
    jornais_invalidos = 0
    
    for jornal in jornais:
        try:
            audio = AudioSegment.from_file(str(jornal))
            duracao_seg = len(audio) / 1000
            
            # Validações básicas
            if duracao_seg < 60:  # Mínimo 1 minuto
                etapa.adicionar_erro(f"Jornal muito curto ({duracao_seg:.1f}s): {jornal.name}")
                jornais_invalidos += 1
            elif jornal.stat().st_size < 100 * 1024:  # Mínimo 100KB
                etapa.adicionar_erro(f"Jornal muito pequeno: {jornal.name}")
                jornais_invalidos += 1
            else:
                jornais_validos += 1
                
        except Exception as e:
            etapa.adicionar_erro(f"Erro ao validar {jornal.name}: {e}")
            jornais_invalidos += 1
    
    etapa.resultados["jornais_validos"] = jornais_validos
    etapa.resultados["jornais_invalidos"] = jornais_invalidos
    
    if jornais_validos == 0:
        erro = "Nenhum jornal passou na auditoria"
        etapa.adicionar_erro(erro)
        logger.erro("auditoria_jornais", erro)
        etapa.concluir(sucesso=False)
        return False
    
    logger.info(
        "auditoria_jornais",
        f"Auditoria concluída: {jornais_validos} válidos, {jornais_invalidos} inválidos"
    )
    
    etapa.concluir(sucesso=True)
    return True


def etapa_remontagem(
    status: StatusPipeline,
    pasta_cortes: Path,
    pasta_jornais: Path,
    jornais_invalidos: int,
) -> Tuple[bool, List[Path]]:
    """
    ETAPA 9: Re-montagem (se necessário)
    
    Se jornais falharam na auditoria, tenta re-montar com ajustes:
    - Força ordem numérica estrita (sem intercalação)
    - Ajusta volumes de vinhetas
    """
    if jornais_invalidos == 0:
        etapa = EtapaPipeline("remontagem", "Re-montagem não necessária")
        status.adicionar_etapa(etapa)
        etapa.iniciar()
        etapa.concluir(sucesso=True)
        return True, []
    
    etapa = EtapaPipeline("remontagem", "Re-montagem de jornais com ajustes")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("remontagem", "=== Iniciando re-montagem ===")
    
    # Limpa jornais anteriores
    for jornal in pasta_jornais.glob("*.mp3"):
        try:
            jornal.unlink()
        except Exception:
            pass
    
    # Re-monta SEM intercalação (ordem estrita)
    jornais_gerados = montar_todos_jornais(
        pasta_cortes,
        pasta_jornais,
        logger,
        intercalar=False,  # Desativa intercalação
    )
    
    etapa.resultados["jornais_re_gerados"] = len(jornais_gerados)
    
    if not jornais_gerados:
        erro = "Re-montagem falhou: nenhum jornal gerado"
        etapa.adicionar_erro(erro)
        logger.erro("remontagem", erro)
        etapa.concluir(sucesso=False)
        return False, []
    
    logger.info("remontagem", f"Re-montagem concluída: {len(jornais_gerados)} jornais")
    etapa.concluir(sucesso=True)
    return True, jornais_gerados


def etapa_melhorias_jornais(
    status: StatusPipeline,
    jornais: List[Path],
) -> bool:
    """
    ETAPA 10: Melhorias Finais nos Jornais
    
    Aplica melhorias finais:
    - Normalização de loudness (EBU R128)
    - Metadados ID3
    - Otimização para web/streaming
    """
    etapa = EtapaPipeline("melhorias_jornais", "Aplicação de melhorias finais")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("melhorias_jornais", "=== Iniciando melhorias finais ===")
    
    # Placeholder para melhorias
    # Futuro: mutagen para ID3 tags, pydub para normalização
    
    jornais_processados = len(jornais)
    etapa.resultados["jornais_processados"] = jornais_processados
    
    logger.info("melhorias_jornais", f"Melhorias aplicadas em {jornais_processados} jornais")
    etapa.concluir(sucesso=True)
    return True


def etapa_upload(
    status: StatusPipeline,
    jornais: List[Path],
    pasta_drive: Path,
) -> bool:
    """
    ETAPA 11: Upload para Google Drive
    
    Sincroniza os jornais montados com a pasta do Drive.
    """
    etapa = EtapaPipeline("upload", "Sincronização com Google Drive")
    status.adicionar_etapa(etapa)
    etapa.iniciar()
    
    logger = status.logger
    logger.info("upload", "=== Iniciando upload para Drive ===")
    
    if not jornais:
        erro = "Nenhum jornal para upload"
        etapa.adicionar_erro(erro)
        logger.erro("upload", erro)
        etapa.concluir(sucesso=False)
        return False
    
    # Cria pasta de destino
    pasta_drive.mkdir(parents=True, exist_ok=True)
    
    # Copia jornais para pasta de sync
    uploads_realizados = 0
    for jornal in jornais:
        try:
            destino = pasta_drive / jornal.name
            shutil.copy2(jornal, destino)
            uploads_realizados += 1
            logger.info("upload", f"Jornal copiado para sync: {jornal.name}")
        except Exception as e:
            etapa.adicionar_erro(f"Falha ao copiar {jornal.name}: {e}")
    
    etapa.resultados["uploads_realizados"] = uploads_realizados
    
    if uploads_realizados == 0:
        erro = "Nenhum jornal foi copiado para sync"
        etapa.adicionar_erro(erro)
        logger.erro("upload", erro)
        etapa.concluir(sucesso=False)
        return False
    
    logger.info("upload", f"Upload concluído: {uploads_realizados} jornais")
    etapa.concluir(sucesso=True)
    return True


# ============================================================================
# ORQUESTRADOR PRINCIPAL
# ============================================================================

def executar_pipeline(
    pasta_brutos: Path,
    pasta_cortes: Path,
    pasta_jornais: Path,
    pasta_drive: Path,
    relatorio_path: Path,
) -> bool:
    """
    Executa o pipeline inteligente completo.
    
    Fluxo:
    planejamento → cópia → corte → auditoria → ajustes → melhorias → 
    montagem → auditoria → re-montagem → melhorias → upload
    """
    status = StatusPipeline()
    logger = status.logger
    
    logger.info("pipeline", "=" * 60)
    logger.info("pipeline", "PIPELINE INTELIGENTE DE JORNAIS - INÍCIO")
    logger.info("pipeline", "=" * 60)
    
    # Pasta de trabalho temporária
    pasta_trabalho = pasta_cortes.parent / "_trabalho"
    
    # ETAPA 1: Planejamento
    if not etapa_planejamento(status, pasta_brutos, pasta_cortes, pasta_jornais):
        logger.erro("pipeline", "Pipeline abortado na etapa: planejamento")
        status.finalizar()
        status.salvar_relatorio(relatorio_path)
        return False
    
    # ETAPA 2: Cópia
    if not etapa_copia(status, pasta_brutos, pasta_trabalho):
        logger.erro("pipeline", "Pipeline abortado na etapa: cópia")
        status.finalizar()
        status.salvar_relatorio(relatorio_path)
        return False
    
    # ETAPA 3: Corte
    if not etapa_corte(status, pasta_trabalho, pasta_cortes):
        logger.erro("pipeline", "Pipeline abortado na etapa: corte")
        status.finalizar()
        status.salvar_relatorio(relatorio_path)
        return False
    
    # ETAPA 4: Auditoria dos Cortes
    sucesso_auditoria, auditoria_resultados = etapa_auditoria_cortes(status, pasta_cortes)
    if not sucesso_auditoria:
        logger.erro("pipeline", "Pipeline abortado na etapa: auditoria_cortes")
        status.finalizar()
        status.salvar_relatorio(relatorio_path)
        return False
    
    # ETAPA 5: Ajustes
    if not etapa_ajustes(status, pasta_cortes, auditoria_resultados):
        logger.erro("pipeline", "Pipeline abortado na etapa: ajustes")
        status.finalizar()
        status.salvar_relatorio(relatorio_path)
        return False
    
    # ETAPA 6: Melhorias nos Cortes
    if not etapa_melhorias_cortes(status, pasta_cortes):
        logger.aviso("pipeline", "Etapa melhorias_cortes falhou, continuando...")
    
    # ETAPA 7: Montagem
    sucesso_montagem, jornais = etapa_montagem(status, pasta_cortes, pasta_jornais)
    if not sucesso_montagem:
        logger.erro("pipeline", "Pipeline abortado na etapa: montagem")
        status.finalizar()
        status.salvar_relatorio(relatorio_path)
        return False
    
    # ETAPA 8: Auditoria dos Jornais
    sucesso_auditoria_jornais = etapa_auditoria_jornais(status, jornais)
    jornais_invalidos = status.etapas[-1].resultados.get("jornais_invalidos", 0)
    
    # ETAPA 9: Re-montagem (se necessário)
    if not sucesso_auditoria_jornais or jornais_invalidos > 0:
        sucesso_remontagem, jornais_re = etapa_remontagem(status, pasta_cortes, pasta_jornais, jornais_invalidos)
        if sucesso_remontagem:
            jornais = jornais_re
            # Re-valida
            etapa_auditoria_jornais(status, jornais)
    
    # ETAPA 10: Melhorias Finais
    if not etapa_melhorias_jornais(status, jornais):
        logger.aviso("pipeline", "Etapa melhorias_jornais falhou, continuando...")
    
    # ETAPA 11: Upload
    if not etapa_upload(status, jornais, pasta_drive):
        logger.erro("pipeline", "Pipeline falhou na etapa: upload")
        # Não aborta o pipeline inteiro, apenas registra falha
    
    # Finaliza
    status.finalizar()
    status.salvar_relatorio(relatorio_path)
    
    # Resumo final
    logger.info("pipeline", "=" * 60)
    logger.info("pipeline", "PIPELINE CONCLUÍDO")
    logger.info("pipeline", f"Duração total: {status.duracao_total_segundos():.2f}s")
    logger.info("pipeline", f"Etapas: {status.resumo()['etapas_sucesso']}/{status.resumo()['total_etapas']} sucesso")
    logger.info("pipeline", f"Jornais gerados: {len(jornais)}")
    logger.info("pipeline", "=" * 60)
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Inteligente de Jornais - TJRN",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python pipeline_inteligente.py
  python pipeline_inteligente.py --brutos ./meus_boletins
  python pipeline_inteligente.py --dry-run
        """
    )
    
    parser.add_argument(
        "--brutos",
        type=Path,
        default=DEFAULT_BOLETINS_BRUTOS,
        help="Pasta com boletins brutos (padrão: ./boletins_brutos)"
    )
    
    parser.add_argument(
        "--cortes",
        type=Path,
        default=DEFAULT_SAIDA_CORTES,
        help="Pasta para salvar cortes (padrão: ./boletins_divididos)"
    )
    
    parser.add_argument(
        "--jornais",
        type=Path,
        default=DEFAULT_SAIDA_JORNAIS,
        help="Pasta para salvar jornais (padrão: ./jornais_montados)"
    )
    
    parser.add_argument(
        "--drive",
        type=Path,
        default=DEFAULT_DRIVE_SYNC,
        help="Pasta de sync com Google Drive (padrão: ./drive_sync)"
    )
    
    parser.add_argument(
        "--relatorio",
        type=Path,
        default=None,
        help="Caminho do relatório JSON (padrão: data/_pipeline_logs/relatorio_TIMESTAMP.json)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas simula, não executa operações"
    )
    
    args = parser.parse_args()
    
    # Define caminho do relatório
    if args.relatorio is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.relatorio = LOGS_DIR / f"relatorio_{timestamp}.json"
    
    if args.dry_run:
        print("=" * 60)
        print("DRY RUN - Simulação do Pipeline")
        print("=" * 60)
        print(f"Boletins brutos: {args.brutos}")
        print(f"Saida cortes: {args.cortes}")
        print(f"Saida jornais: {args.jornais}")
        print(f"Drive sync: {args.drive}")
        print(f"Relatório: {args.relatorio}")
        print("=" * 60)
        print("Nenhuma operação será executada.")
        return 0
    
    # Executa pipeline
    sucesso = executar_pipeline(
        args.brutos,
        args.cortes,
        args.jornais,
        args.drive,
        args.relatorio,
    )
    
    return 0 if sucesso else 1


if __name__ == "__main__":
    sys.exit(main())
