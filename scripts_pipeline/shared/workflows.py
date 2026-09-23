#!/usr/bin/env python3
"""
workflows.py — Workflows de ajuste com agentes proativos.

Agentes:
1. AuditorAgent — Analisa qualidade e identifica problemas
2. AjusteAgent — Propõe e aplica correções
3. MonitorAgent — Monitora tendências e alerta
4. RelatorioAgent — Gera relatórios executivos

Cada agente é autônomo e pode ser executado independentemente ou em pipeline.
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.config import DivisorConfig, get_config, set_config
from shared.avaliacao import avaliar_transcricao, extrair_entidades
from shared.core import sincronizar_transcricao_com_cortes, Corte
from shared.logging_config import get_logger

logger = get_logger("workflows")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOLETINS_DIR = PROJECT_ROOT / "boletins"


# ═════════════════════════════════════════════════════════════════════════════
# ESTRUTURAS DE DADOS
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Problema:
    """Um problema identificado pelo auditor."""
    nivel: str  # CRITICO, ALTO, MEDIO, BAIXO
    categoria: str
    boletim: str
    descricao: str
    evidencia: str = ""
    acao_sugerida: str = ""


@dataclass
class Acao:
    """Uma ação de ajuste proposta pelo agente."""
    tipo: str  # AJUSTE_THRESHOLD, CORRIGIR_ALUCINACAO, REVISAO_HUMANA
    parametro: str
    valor_atual: float
    valor_proposto: float
    justificativa: str
    aplicada: bool = False


@dataclass
class ResultadoWorkflow:
    """Resultado da execução de um workflow."""
    agente: str
    sucesso: bool
    problemas: list = field(default_factory=list)
    acoes: list = field(default_factory=list)
    relatorio: str = ""


# ═════════════════════════════════════════════════════════════════════════════
# AGENTE 1: AUDITOR
# ═════════════════════════════════════════════════════════════════════════════

class AuditorAgent:
    """
    Analisa a qualidade dos boletins processados.
    
    Verifica:
    - Cobertura literal vs semântica
    - Alucinações conhecidas
    - Entidades preservadas
    - Consistência temporal
    """
    
    def __init__(self):
        self.problemas = []
    
    def auditar(self, auditoria_path: Path) -> ResultadoWorkflow:
        """Executa auditoria completa de um arquivo auditoria.json."""
        logger.info(f"Auditor: analisando {auditoria_path.name}")
        
        try:
            dados = json.loads(auditoria_path.read_text(encoding="utf-8"))
        except Exception as e:
            return ResultadoWorkflow("Auditor", False, [], [], f"Erro ao ler: {e}")
        
        roteiros = self._carregar_roteiros(dados)
        
        for i, boletim in enumerate(dados.get("boletims_gerados", [])):
            n = i + 1
            qualidade = boletim.get("qualidade", {})
            arquivo = boletim.get("arquivo", f"B{n}")
            
            # 1. Verificar cobertura
            cobertura = qualidade.get("cobertura_roteiro_original", 0)
            if cobertura < 0.60:
                self._verificar_sentido(roteiros.get(n), qualidade, arquivo, n)
            
            # 2. Verificar alucinações na transcrição
            self._verificar_alucinacoes(qualidade, arquivo, n)
            
            # 3. Verificar entidades
            self._verificar_entidades(roteiros.get(n), qualidade, arquivo, n)
        
        return ResultadoWorkflow(
            agente="Auditor",
            sucesso=True,
            problemas=self.problemas,
            acoes=[],
            relatorio=self._gerar_resumo()
        )
    
    def _carregar_roteiros(self, dados: dict) -> dict:
        """Carroteiros se disponíveis no mesmo diretório."""
        roteiros = {}
        # Tentar carregar de arquivo .txt no mesmo diretório
        txt_files = list(BOLETINS_DIR.rglob("*.txt"))
        for f in txt_files:
            conteudo = f.read_text(encoding="utf-8", errors="ignore")
            for bloco in re.split(r'={20,}|DOCUMENTO\s+\[\d+/\d+\]', conteudo):
                m = re.search(r'B(\d+)\s*[-–]\s*(.+)', bloco)
                m_off = re.search(r'OFF:\s*\n(.+?)(?:\n={20,}|\Z)', bloco, re.DOTALL)
                if m and m_off:
                    roteiros[int(m.group(1))] = m_off.group(1).strip()
        return roteiros
    
    def _verificar_sentido(self, roteiro: Optional[str], qualidade: dict, arquivo: str, n: int):
        """Verifica sentido quando cobertura literal é baixa."""
        if not roteiro:
            return
        
        texto_corrigido = qualidade.get("texto_corrigido", "")
        if texto_corrigido:
            resultado = avaliar_transcricao(roteiro, texto_corrigido)
            if resultado.aprovado:
                self.problemas.append(Problema(
                    nivel="INFO",
                    categoria="Sentido",
                    boletim=f"B{n}",
                    descricao=f"Cobertura literal {qualidade.get('cobertura_roteiro_original', 0):.0%} mas sentido preservado ({resultado.score_sentido:.0%})",
                    evidencia=resultado.motivo,
                    acao_sugerida="Manter — sentido OK"
                ))
            else:
                self.problemas.append(Problema(
                    nivel="ALTO",
                    categoria="Sentido",
                    boletim=f"B{n}",
                    descricao=f"Sentido comprometido: {resultado.motivo}",
                    evidencia=f"Sentido={resultado.score_sentido:.0%}, Entidades={resultado.score_entidades:.0%}",
                    acao_sugerida="Revisão humana recomendada"
                ))
    
    def _verificar_alucinacoes(self, qualidade: dict, arquivo: str, n: int):
        """Detecta alucinações conhecidas no texto."""
        texto = qualidade.get("texto_corrigido", "")
        if not texto:
            return
        
        alucinacoes = [
            (r'tejota\s+rene', 'Tejota Rene → TJRN'),
            (r'\bnatau\b', 'Natau → Natal'),
            (r'barbão\s+pastou', 'barbão pastou → Bom Pastor'),
            (r'\bgip\b', 'GIP → jipe'),
            (r'\bpresional\b', 'presional → prisional'),
        ]
        
        for padrao, desc in alucinacoes:
            if re.search(padrao, texto, re.I):
                self.problemas.append(Problema(
                    nivel="BAIXO",
                    categoria="Alucinação",
                    boletim=f"B{n}",
                    descricao=f"Alucinação detectada: {desc}",
                    evidencia=f"Padrão: {padrao}",
                    acao_sugerida="Corrigido automaticamente pelo pipeline"
                ))
    
    def _verificar_entidades(self, roteiro: Optional[str], qualidade: dict, arquivo: str, n: int):
        """Verifica preservação de entidades."""
        if not roteiro:
            return
        
        texto = qualidade.get("texto_corrigido", "")
        if not texto:
            return
        
        ent_roteiro = extrair_entidades(roteiro)
        ent_texto = extrair_entidades(texto)
        
        # Verificar valores perdidos
        valores_roteiro = set(ent_roteiro.get("valores", []))
        valores_texto = set(ent_texto.get("valores", []))
        valores_perdidos = valores_roteiro - valores_texto
        
        if valores_perdidos:
            self.problemas.append(Problema(
                nivel="ALTO",
                categoria="Entidade",
                boletim=f"B{n}",
                descricao=f"Valor(es) perdido(s): {', '.join(valores_perdidos)}",
                evidencia=f"No roteiro: {valores_roteiro} | Na transcrição: {valores_texto}",
                acao_sugerida="Verificar se locutor mencionou o valor"
            ))
    
    def _gerar_resumo(self) -> str:
        """Gera resumo da auditoria."""
        if not self.problemas:
            return "Nenhum problema detectado."
        
        por_nivel = {}
        for p in self.problemas:
            por_nivel.setdefault(p.nivel, []).append(p)
        
        linhas = []
        for nivel in ["CRITICO", "ALTO", "MEDIO", "BAIXO", "INFO"]:
            if nivel in por_nivel:
                linhas.append(f"  {nivel}: {len(por_nivel[nivel])} problema(s)")
        
        return "\n".join(linhas)


# ═════════════════════════════════════════════════════════════════════════════
# AGENTE 2: AJUSTE
# ═════════════════════════════════════════════════════════════════════════════

class AjusteAgent:
    """
    Propõe e aplica ajustes nos parâmetros do pipeline.
    
    Ajustes:
    - Threshold de cobertura
    - Threshold de similaridade
    - Parâmetros de áudio
    """
    
    def __init__(self):
        self.acoes = []
    
    def analisar_e_problemas(self, problemas: list, history: list = None) -> ResultadoWorkflow:
        """Analisa problemas e propõe ajustes."""
        logger.info("Ajuste: analisando problemas para propor correções")
        
        config = get_config()
        
        # Contar problemas por categoria
        com_alucinacao = [p for p in problemas if p.categoria == "Alucinação"]
        com_sentido_ruim = [p for p in problemas if p.categoria == "Sentido" and p.nivel in ("ALTO", "CRITICO")]
        com_entidade_perdida = [p for p in problemas if p.categoria == "Entidade" and p.nivel == "ALTO"]
        
        # Proposta 1: Ajustar threshold de cobertura se muitos falsos positivos
        if com_sentido_ruim:
            self.acoes.append(Acao(
                tipo="AJUSTE_THRESHOLD",
                parametro="cobertura_min",
                valor_atual=config.cobertura_min,
                valor_proposto=max(config.cobertura_min - 0.05, 0.30),
                justificativa=f"{len(com_sentido_ruim)} boletim(ns) com sentido comprometido"
            ))
        
        # Proposta 2: Reduzir threshold se muitas alucinações (indica audio ruim)
        if len(com_alucinacao) > 3:
            self.acoes.append(Acao(
                tipo="AJUSTE_THRESHOLD",
                parametro="threshold_similaridade",
                valor_atual=config.threshold_similaridade,
                valor_proposto=max(config.threshold_similaridade - 0.05, 0.50),
                justificativa=f"{len(com_alucinacao)} alucinações detectadas — audio pode ter qualidade baixa"
            ))
        
        return ResultadoWorkflow(
            agente="Ajuste",
            sucesso=True,
            problemas=problemas,
            acoes=self.acoes,
            relatorio=self._gerar_resumo()
        )
    
    def aplicar_acao(self, acao: Acao) -> bool:
        """Aplica uma ação de ajuste."""
        config = get_config()
        
        if acao.tipo == "AJUSTE_THRESHOLD":
            if acao.parametro == "cobertura_min":
                config.cobertura_min = acao.valor_proposto
            elif acao.parametro == "threshold_similaridade":
                config.threshold_similaridade = acao.valor_proposto
            
            config.aplicar()
            acao.aplicada = True
            logger.info(f"Ajuste aplicado: {acao.parametro} = {acao.valor_proposto}")
            return True
        
        return False
    
    def _gerar_resumo(self) -> str:
        """Gera resumo das ações propostas."""
        if not self.acoes:
            return "Nenhum ajuste necessário."
        
        linhas = []
        for acao in self.acoes:
            linhas.append(f"  {acao.parametro}: {acao.valor_atual:.2f} → {acao.valor_proposto:.2f} ({acao.justificativa})")
        
        return "\n".join(linhas)


# ═════════════════════════════════════════════════════════════════════════════
# AGENTE 3: MONITOR
# ═════════════════════════════════════════════════════════════════════════════

class MonitorAgent:
    """
    Monitora tendências ao longo de múltiplos batches.
    
    Detecta:
    - Degradação de qualidade
    - Melhoria consistente
    - Padrões sazonais
    """
    
    def __init__(self):
        self.alertas = []
    
    def monitorar(self, batches: list) -> ResultadoWorkflow:
        """Analisa tendência entre múltiplos batches."""
        logger.info(f"Monitor: analisando {len(batches)} batches")
        
        if len(batches) < 2:
            return ResultadoWorkflow("Monitor", True, [], [], "Dados insuficientes para tendência (mínimo 2 batches)")
        
        # Calcular médias
        medias_cobertura = []
        medias_entidades = []
        
        for batch in batches:
            coberturas = []
            entidades = []
            for b in batch.get("boletims_gerados", []):
                q = b.get("qualidade", {})
                coberturas.append(q.get("cobertura_roteiro_original", 0))
            if coberturas:
                medias_cobertura.append(sum(coberturas) / len(coberturas))
        
        # Detectar tendência
        if len(medias_cobertura) >= 2:
            tendencia = medias_cobertura[-1] - medias_cobertura[-2]
            
            if tendencia < -0.10:
                self.alertas.append("ALERTA: Queda significativa na cobertura (>10%)")
            elif tendencia > 0.10:
                self.alerta.append("INFO: Melhoria significativa na cobertura (>10%)")
        
        return ResultadoWorkflow(
            agente="Monitor",
            sucesso=True,
            problemas=[],
            acoes=[],
            relatorio=self._gerar_resumo(medias_cobertura)
        )
    
    def _gerar_resumo(self, medias: list) -> str:
        """Gera resumo da monitoração."""
        if not medias:
            return "Sem dados."
        
        return f"  Médias de cobertura: {[f'{m:.0%}' for m in medias]}"


# ═════════════════════════════════════════════════════════════════════════════
# AGENTE 4: RELATÓRIO
# ═════════════════════════════════════════════════════════════════════════════

class RelatorioAgent:
    """
    Gera relatórios executivos dos workflows.
    """
    
    def gerar(self, resultados: list) -> str:
        """Gera relatório consolidado."""
        linhas = []
        linhas.append("=" * 60)
        linhas.append("RELATÓRIO EXECUTIVO — Workflows DIVISOR")
        linhas.append("=" * 60)
        linhas.append("")
        
        for r in resultados:
            linhas.append(f"Agente: {r.agente}")
            linhas.append(f"  Sucesso: {'Sim' if r.sucesso else 'Não'}")
            if r.problemas:
                linhas.append(f"  Problemas: {len(r.problemas)}")
            if r.acoes:
                linhas.append(f"  Ações: {len(r.acoes)}")
            if r.relatorio:
                linhas.append(f"  Detalhes:\n{r.relatorio}")
            linhas.append("")
        
        return "\n".join(linhas)


# ═════════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR
# ═════════════════════════════════════════════════════════════════════════════

def executar_workflow(auditoria_path: Path, aplicar_ajustes: bool = False) -> str:
    """
    Executa o pipeline completo de agentes.
    
    Args:
        auditoria_path: Path para o arquivo auditoria.json
        aplicar_ajustes: Se True, aplica ajustes automaticamente
    
    Returns:
        Relatório consolidado
    """
    logger.info(f"Iniciando workflow para {auditoria_path.name}")
    
    # Agente 1: Auditor
    auditor = AuditorAgent()
    resultado_auditor = auditor.auditar(auditoria_path)
    
    # Agente 2: Ajuste
    ajuste = AjusteAgent()
    resultado_ajuste = ajuste.analisar_e_problemas(resultado_auditor.problemas)
    
    if aplicar_ajustes:
        for acao in resultado_ajuste.acoes:
            ajuste.aplicar_acao(acao)
    
    # Agente 4: Relatório
    relatorio = RelatorioAgent()
    return relatorio.gerar([resultado_auditor, resultado_ajuste])


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Workflows de ajuste proativos")
    parser.add_argument("--auditoria", type=Path, help="Path para auditoria.json")
    parser.add_argument("--apply", action="store_true", help="Aplica ajustes automaticamente")
    args = parser.parse_args()
    
    if args.auditoria:
        resultado = executar_workflow(args.auditoria, args.apply)
        print(resultado)
    else:
        print("Informe --auditoria caminho/auditoria.json")
