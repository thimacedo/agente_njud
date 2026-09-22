#!/usr/bin/env python3
"""
supervisor.py — Agente de RL para auto-ajuste de parâmetros do pipeline DIVISOR.

Lê auditoria.json de batches passados, calcula recompensas e ajusta:
  - DIVISOR_COBERTURA_MIN (threshold de aprovação)
  - DIVISOR_THRESHOLD_SIMILARIDADE (threshold de confirmação de repetições)

Uso:
  python supervisor.py                          # analisa último batch e sugere ajustes
  python supervisor.py --apply                  # aplica ajustes via variáveis de ambiente
  python supervisor.py --history 10             # usa últimos 10 batches para decisão
  python supervisor.py --auditoria caminho.json # analisa arquivo específico
"""

import argparse
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# Config centralizada (elimina dependencia circular de thresholds)
try:
    from shared.config import DivisorConfig, get_config, set_config
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False


# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOLETINS_DIR = PROJECT_ROOT / "boletins"

# Limites dos parâmetros
COBERTURA_MIN_LIMITS = (0.30, 0.90)
SIMILARIDADE_LIMITS = (0.50, 0.95)
STEP_SIZE = 0.05

# Pesos da recompensa composta
PESO_COBERTURA = 0.5
PESO_CORRECOES = 0.3
PESO_REPROVACAO = 0.2


# ═════════════════════════════════════════════════════════════════════════════
# ESTRUTURAS DE DADOS
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class BoletimResult:
    """Resultado individual de um boletim."""
    arquivo: str
    cobertura: float
    correcoes_aplicadas: bool
    duracao_segundos: float
    aprovado: bool  # calculado pelo supervisor


@dataclass
class BatchResult:
    """Resultado de um batch completo (um arquivo de auditoria)."""
    arquivo_auditoria: Path
    arquivo_entrada: str
    data: str
    boletins: List[BoletimResult] = field(default_factory=list)
    
    @property
    def cobertura_media(self) -> float:
        if not self.boletins:
            return 0.0
        return sum(b.cobertura for b in self.boletins) / len(self.boletins)
    
    @property
    def taxa_aprovacao(self) -> float:
        if not self.boletins:
            return 0.0
        return sum(1 for b in self.boletins if b.aprovado) / len(self.boletins)
    
    @property
    def taxa_correcao(self) -> float:
        if not self.boletins:
            return 0.0
        return sum(1 for b in self.boletins if b.correcoes_aplicadas) / len(self.boletins)
    
    @property
    def n_boletins(self) -> int:
        return len(self.boletins)


# ═════════════════════════════════════════════════════════════════════════════
# PARSER DE AUDITORIA
# ═════════════════════════════════════════════════════════════════════════════

def carregar_auditoria(caminho: Path, threshold_atual: float = 0.60) -> Optional[BatchResult]:
    """Carrega um arquivo auditoria.json e extrai métricas."""
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  ⚠️  Erro ao ler {caminho}: {e}")
        return None
    
    batch = BatchResult(
        arquivo_auditoria=caminho,
        arquivo_entrada=dados.get("arquivo_entrada", ""),
        data=dados.get("data_detectada", ""),
    )
    
    for b in dados.get("boletims_gerados", []):
        q = b.get("qualidade", {})
        cobertura = q.get("cobertura_roteiro_original", 0.0)
        
        bol = BoletimResult(
            arquivo=b.get("arquivo", ""),
            cobertura=cobertura,
            correcoes_aplicadas=q.get("correcoes_aplicadas", False),
            duracao_segundos=b.get("duracao_segundos", 0.0),
            aprovado=cobertura >= threshold_atual,
        )
        batch.boletins.append(bol)
    
    return batch


def encontrar_batches(diretorio: Path, ultimos_n: int = 10) -> List[Path]:
    """Encontra arquivos auditoria.json recursivamente, ordenados por data (mais recente primeiro)."""
    arquivos = list(diretorio.rglob("auditoria.json"))
    # Ordenar pela data de modificação do arquivo (mais recente primeiro)
    arquivos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return arquivos[:ultimos_n]


# ═════════════════════════════════════════════════════════════════════════════
# RL AGENT
# ═════════════════════════════════════════════════════════════════════════════

class SupervisorRL:
    """
    Agente de RL que ajusta parâmetros do pipeline baseado em recompensas.
    
    Estado: (cobertura_media, taxa_aprovacao, taxa_correcao)
    Ações: {AUMENTAR, MANTER, DIMINUIR} para cada parâmetro
    Recompensa: função composta de qualidade
    """
    
    def __init__(
        self,
        threshold_cobertura: float = 0.60,
        threshold_similaridade: float = 0.75,
        learning_rate: float = 0.10,
        epsilon: float = 0.20,
    ):
        self.threshold_cobertura = threshold_cobertura
        self.threshold_similaridade = threshold_similaridade
        self.learning_rate = learning_rate
        self.epsilon = epsilon
        # ATENCAO: learning_rate, epsilon e historico sao armazenados mas nao
        # usados por decidir_acao/aplicar_acao — a logica atual e um conjunto
        # de regras deterministicas (if/else sobre thresholds fixos), nao um
        # agente RL com exploracao epsilon-greedy real. self.historico nunca
        # recebe .append (o historico persistido e o .supervisor_history.json
        # escrito em main()). Cada execucao do script recria o objeto do
        # zero, entao nada aqui carrega estado entre batches.
        self.historico: List[dict] = []
    
    def calcular_recompensa(self, batch: BatchResult) -> float:
        """
        Função de recompensa composta:
        - cobertura_media alta → positivo
        - taxa_aprovacao alta → positivo
        - taxa_correcao baixa → positivo (menos correções = áudio mais limpo)
        - taxa_aprovacao muito baixa → negativo (threshold muito alto)
        - cobertura_media muito baixa → negativo (qualidade ruim)
        """
        r_cobertura = batch.cobertura_media  # 0..1
        r_aprovacao = batch.taxa_aprovacao   # 0..1
        r_correcao = 1.0 - batch.taxa_correcao  # inverso: menos correção = melhor
        
        # Penalidades
        penalidade = 0.0
        if r_aprovacao < 0.5:
            penalidade -= 0.5  # Muita reprovação = threshold muito alto
        if r_cobertura < 0.4:
            penalidade -= 0.3  # Cobertura muito baixa = qualidade ruim
        
        recompensa = (
            PESO_COBERTURA * r_cobertura +
            PESO_CORRECOES * r_correcao +
            PESO_REPROVACAO * r_aprovacao +
            penalidade
        )
        
        return recompensa
    
    def decidir_acao(self, batch: BatchResult) -> dict:
        """
        Decide ação baseada no estado atual do batch.
        Retorna dict com ações para cada parâmetro.
        """
        reward = self.calcular_recompensa(batch)
        
        acoes = {}
        
        # ── Lógica para COBERTURA_MIN ──
        if batch.taxa_aprovacao >= 0.8 and batch.cobertura_media >= 0.7:
            # Tudo indo bem, pode ser mais restritivo
            acoes["cobertura"] = "UP"
        elif batch.taxa_aprovacao < 0.5:
            # Muita reprovação, afrouxar
            acoes["cobertura"] = "DOWN"
        elif batch.taxa_correcao > 0.8:
            # Muitas correções = threshold muito permissivo, aumentar
            acoes["cobertura"] = "UP"
        else:
            acoes["cobertura"] = "KEEP"
        
        # ── Lógica para THRESHOLD_SIMILARIDADE ──
        # (inferido via taxa de correções vs cobertura)
        if batch.taxa_correcao < 0.3 and batch.cobertura_media > 0.75:
            # Poucas correções e alta cobertura: pode ser mais rigoroso
            acoes["similaridade"] = "UP"
        elif batch.taxa_correcao > 0.9:
            # Quase tudo corrigindo: similaridade muito branda
            acoes["similaridade"] = "UP"
        else:
            acoes["similaridade"] = "KEEP"
        
        return {
            "acoes": acoes,
            "reward": reward,
            "estado": {
                "cobertura_media": round(batch.cobertura_media, 3),
                "taxa_aprovacao": round(batch.taxa_aprovacao, 3),
                "taxa_correcao": round(batch.taxa_correcao, 3),
            }
        }
    
    def aplicar_acao(self, acoes: dict) -> dict:
        """Aplica as ações e retorna novos valores."""
        novos = {}
        
        # Ajustar COBERTURA_MIN
        acao_cob = acoes.get("cobertura", "KEEP")
        if acao_cob == "UP":
            self.threshold_cobertura = min(
                self.threshold_cobertura + STEP_SIZE,
                COBERTURA_MIN_LIMITS[1]
            )
        elif acao_cob == "DOWN":
            self.threshold_cobertura = max(
                self.threshold_cobertura - STEP_SIZE,
                COBERTURA_MIN_LIMITS[0]
            )
        
        # Ajustar THRESHOLD_SIMILARIDADE
        acao_sim = acoes.get("similaridade", "KEEP")
        if acao_sim == "UP":
            self.threshold_similaridade = min(
                self.threshold_similaridade + STEP_SIZE,
                SIMILARIDADE_LIMITS[1]
            )
        elif acao_sim == "DOWN":
            self.threshold_similaridade = max(
                self.threshold_similaridade - STEP_SIZE,
                SIMILARIDADE_LIMITS[0]
            )
        
        novos["DIVISOR_COBERTURA_MIN"] = round(self.threshold_cobertura, 2)
        novos["DIVISOR_THRESHOLD_SIMILARIDADE"] = round(self.threshold_similaridade, 2)
        
        return novos


# ═════════════════════════════════════════════════════════════════════════════
# ANÁLISE E RELATÓRIO
# ═════════════════════════════════════════════════════════════════════════════

def analisar_historico(batches: List[BatchResult]) -> dict:
    """Analisa tendências nos últimos batches."""
    if not batches:
        return {}
    
    coberturas = [b.cobertura_media for b in batches]
    aprovacoes = [b.taxa_aprovacao for b in batches]
    correcoes = [b.taxa_correcao for b in batches]
    
    n = len(batches)
    
    # Tendência: comparar primeira metade vs segunda metade
    mid = n // 2
    if mid > 0:
        cobertura_trend = sum(coberturas[:mid]) / mid - sum(coberturas[mid:]) / (n - mid)
        aprovacao_trend = sum(aprovacoes[:mid]) / mid - sum(aprovacoes[mid:]) / (n - mid)
    else:
        cobertura_trend = 0
        aprovacao_trend = 0
    
    return {
        "n_batches": n,
        "cobertura_media_geral": round(sum(coberturas) / n, 3),
        "cobertura_minima": round(min(coberturas), 3),
        "cobertura_maxima": round(max(coberturas), 3),
        "aprovacao_media": round(sum(aprovacoes) / n, 3),
        "correcao_media": round(sum(correcoes) / n, 3),
        "tendencia_cobertura": "SUBINDO" if cobertura_trend > 0.05 else ("CAINDO" if cobertura_trend < -0.05 else "ESTÁVEL"),
        "tendencia_aprovacao": "SUBINDO" if aprovacao_trend > 0.05 else ("CAINDO" if aprovacao_trend < -0.05 else "ESTÁVEL"),
    }


def gerar_relatorio(batches: List[BatchResult], analise: dict, acoes: dict, novos_params: dict) -> str:
    """Gera relatório legível do supervisor."""
    lines = []
    lines.append("🎛️  SUPERVISOR.PY — Relatório de Auto-Ajuste (RL Agent)")
    lines.append("=" * 65)
    
    # Resumo dos batches analisados
    lines.append(f"\n📁 Batches analisados: {analise['n_batches']}")
    lines.append(f"   Cobertura média geral:  {analise['cobertura_media_geral']:.1%}")
    lines.append(f"   Cobertura range:        [{analise['cobertura_minima']:.1%} — {analise['cobertura_maxima']:.1%}]")
    lines.append(f"   Taxa aprovação média:   {analise['aprovacao_media']:.1%}")
    lines.append(f"   Taxa correção média:    {analise['correcao_media']:.1%}")
    lines.append(f"   Tendência cobertura:    {analise['tendencia_cobertura']}")
    lines.append(f"   Tendência aprovação:    {analise['tendencia_aprovacao']}")
    
    # Detalhes por batch
    lines.append(f"\n📊 Detalhamento por batch:")
    lines.append(f"   {'Arquivo':<35} {'N':>3} {'Cob':>6} {'Apr':>6} {'Corr':>6}")
    lines.append(f"   {'─'*35} {'─'*3} {'─'*6} {'─'*6} {'─'*6}")
    for b in batches:
        nome = b.arquivo_auditoria.parent.name[:35]
        lines.append(
            f"   {nome:<35} {b.n_boletins:>3} "
            f"{b.cobertura_media:>5.1%} {b.taxa_aprovacao:>5.1%} {b.taxa_correcao:>5.1%}"
        )
    
    # Decisão do agente
    lines.append(f"\n🧠 Decisão do Agente RL:")
    lines.append(f"   Estado: cobertura={acoes['estado']['cobertura_media']:.1%}, "
                 f"aprovação={acoes['estado']['taxa_aprovacao']:.1%}, "
                 f"correções={acoes['estado']['taxa_correcao']:.1%}")
    lines.append(f"   Recompensa calculada: {acoes['reward']:+.3f}")
    lines.append(f"   Ação COBERTURA_MIN:     {acoes['acoes']['cobertura']}")
    lines.append(f"   AÇÃO SIMILARIDADE:      {acoes['acoes']['similaridade']}")
    
    # Novos parâmetros
    lines.append(f"\n⚙️  Parâmetros ajustados:")
    for param, valor in novos_params.items():
        lines.append(f"   export {param}={valor}")
    
    # Per-boletim do último batch
    if batches:
        ultimo = batches[0]
        lines.append(f"\n📋 Último batch ({ultimo.arquivo_auditoria.parent.name}):")
        for b in ultimo.boletins:
            status = "✅" if b.aprovado else "❌"
            corr = "🔧" if b.correcoes_aplicadas else "  "
            lines.append(f"   {status} {corr} {b.arquivo[:50]:<50} cobertura={b.cobertura:.1%}")
    
    lines.append("\n" + "=" * 65)
    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Supervisor RL — Auto-ajuste de parâmetros do pipeline DIVISOR"
    )
    parser.add_argument("--auditoria", type=Path, help="Caminho específico para auditoria.json")
    parser.add_argument("--history", type=int, default=5, help="Número de batches no histórico (padrão: 5)")
    parser.add_argument("--apply", action="store_true", help="Gera script de export para aplicar ajustes")
    parser.add_argument("--threshold-atual", type=float, default=None, help="Threshold atual de cobertura (se None, lê DIVISOR_COBERTURA_MIN)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra análise sem sugerir mudanças")
    args = parser.parse_args()
    
    # Threshold atual (via config centralizada)
    if args.threshold_atual is not None:
        threshold_atual = args.threshold_atual
    elif HAS_CONFIG:
        threshold_atual = get_config().cobertura_min
    else:
        threshold_atual = float(os.environ.get("DIVISOR_COBERTURA_MIN", "0.60"))
    
    # Coletar batches
    if args.auditoria:
        batches = []
        batch = carregar_auditoria(args.auditoria, threshold_atual)
        if batch:
            batches = [batch]
    else:
        arquivos = encontrar_batches(BOLETINS_DIR, args.history)
        if not arquivos:
            print(f"❌ Nenhum auditoria.json encontrado em {BOLETINS_DIR}")
            sys.exit(1)
        batches = []
        for arq in arquivos:
            batch = carregar_auditoria(arq, threshold_atual)
            if batch:
                batches.append(batch)
    
    if not batches:
        print("❌ Nenhum batch válido carregado.")
        sys.exit(1)
    
    # Analisar histórico
    analise = analisar_historico(batches)
    
    # Agente RL decide baseado no batch mais recente (e tendências)
    agente = SupervisorRL(threshold_cobertura=threshold_atual)
    acoes = agente.decidir_acao(batches[0])
    
    # Aplicar ações
    if args.dry_run:
        novos_params = {
            "DIVISOR_COBERTURA_MIN": round(agente.threshold_cobertura, 2),
            "DIVISOR_THRESHOLD_SIMILARIDADE": round(agente.threshold_similaridade, 2),
        }
    else:
        novos_params = agente.aplicar_acao(acoes["acoes"])
    
    # Gerar e imprimir relatório
    relatorio = gerar_relatorio(batches, analise, acoes, novos_params)
    print(relatorio)
    
    # Se --apply, atualiza config centralizada
    if args.apply:
        if HAS_CONFIG:
            config = get_config()
            if "DIVISOR_COBERTURA_MIN" in novos_params:
                config.cobertura_min = novos_params["DIVISOR_COBERTURA_MIN"]
            if "DIVISOR_THRESHOLD_SIMILARIDADE" in novos_params:
                config.threshold_similaridade = novos_params["DIVISOR_THRESHOLD_SIMILARIDADE"]
            set_config(config)
            print(f"\n✅ Config atualizada e aplicada automaticamente:")
            for param, valor in novos_params.items():
                print(f"   {param}={valor}")
        else:
            # Fallback: arquivo .supervisor_env
            script_path = PROJECT_ROOT / ".supervisor_env"
            with open(script_path, 'w') as f:
                f.write("# Gerado por supervisor.py — aplicar antes do próximo batch\n")
                for param, valor in novos_params.items():
                    f.write(f'export {param}="{valor}"\n')
            print(f"\n⚠️ shared/config.py não encontrado. Para aplicar, execute: source {script_path}")
    
    # Salvar histórico de decisões
    hist_path = PROJECT_ROOT / ".supervisor_history.json"
    historico_existente = []
    if hist_path.exists():
        try:
            with open(hist_path, 'r') as f:
                historico_existente = json.load(f)
        except json.JSONDecodeError:
            pass
    
    historico_existente.append({
        "timestamp": str(Path(batches[0].arquivo_auditoria).stat().st_mtime),
        "estado": acoes["estado"],
        "reward": acoes["reward"],
        "acoes": acoes["acoes"],
        "parametros": novos_params,
    })
    
    # Manter só últimas 50 decisões
    historico_existente = historico_existente[-50:]
    with open(hist_path, 'w', encoding='utf-8') as f:
        json.dump(historico_existente, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
