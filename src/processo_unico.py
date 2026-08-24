#!/usr/bin/env python3
"""
Processo Único — Pipeline Divisor (loop fechado corte -> auditoria -> reaprendizado)
=====================================================================================

MUDANÇA DE MODELO (2026-08-24): o pipeline deixa de ser uma sequência de
scripts que um operador reinicia manualmente quando a auditoria reprova.
Passa a ser UM processo contínuo por arquivo, que só é considerado
concluído quando o áudio está em estado ideal (auditoria = OK). Enquanto
não está, o processo permanece "aberto" e escala para a próxima
estratégia de corte a partir do MOTIVO estruturado da reprovação — nunca
repete a mesma estratégia que já falhou.

Estado persistido em `estado_processo.json` na pasta de saída, permitindo
retomar a qualquer momento sem perder o histórico de tentativas por
arquivo (essencial para não confundir "arquivo novo" com "arquivo que já
esgotou 3 estratégias e está esperando revisão manual").

A montagem de um NJUD só roda quando TODOS os boletins daquele NJUD estão
com status OK (ou ESGOTADO_ACEITO, aceito manualmente). Isso substitui o
gate de "taxa de CORTADO > 10% no lote inteiro" por um gate por-NJUD mais
rígido: nenhum jornal é montado com peça pendente.

Uso
----
    python processo_unico.py <pasta_boletins> <pasta_saida> [--max-tentativas 3]
    python processo_unico.py <pasta_boletins> <pasta_saida> --status   # só mostra o estado atual
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ===========================================================================
# ESTRATÉGIAS — ordem de escalonamento por tipo de motivo de reprovação
# ===========================================================================
# Cada motivo de CORTADO mapeia para a PRÓXIMA estratégia a tentar.
# Isto é o "reaprendizado": o sistema não tenta de novo a mesma coisa,
# ele muda de método com base no que a auditoria disse que falhou.

ESTRATEGIAS_POR_MOTIVO = {
    # calibração de abertura ausente/baixa confiança -> força âncora+VAD
    "calibracao_abertura_ausente": "ancora_vad_forcado",
    # borda a <=0.25s do início/fim -> aumenta janela de busca de silêncio
    "borda_colada": "janela_silencio_ampliada",
    # termina/inicia com conectivo isolado -> revisa detecção de pontuação
    "conectivo_isolado": "grade_fixa_locucao_estendida",
    # nenhuma estratégia conhecida -> esgota
    "desconhecido": None,
}

ORDEM_ESCALONAMENTO = [
    "calibracao_correlacao",       # estratégia original (padrão)
    "ancora_vad_forcado",          # ignora calibração, usa âncora texto + VAD
    "janela_silencio_ampliada",    # _encontrar_silencio_proximo com JANELA_MS maior
    "grade_fixa_locucao_estendida",# fallback de grade fixa com margens maiores
]

MAX_TENTATIVAS_PADRAO = len(ORDEM_ESCALONAMENTO)


@dataclass
class TentativaLog:
    estrategia: str
    timestamp: str
    resultado: str          # "OK" | "CORTADO" | "ERRO"
    motivo: list[str] = field(default_factory=list)


@dataclass
class EstadoArquivo:
    arquivo: str
    njud: str
    status: str = "PENDENTE"        # PENDENTE | OK | ESGOTADO | ESGOTADO_ACEITO
    estrategia_atual: str = "calibracao_correlacao"
    tentativas: list[TentativaLog] = field(default_factory=list)

    def proxima_estrategia(self, motivo_classificado: str) -> Optional[str]:
        """Decide a próxima estratégia com base no motivo estruturado
        da última reprovação. Nunca repete uma estratégia já tentada."""
        ja_tentadas = {t.estrategia for t in self.tentativas}
        sugerida = ESTRATEGIAS_POR_MOTIVO.get(motivo_classificado)
        if sugerida and sugerida not in ja_tentadas:
            return sugerida
        # fallback: segue a ordem geral de escalonamento
        for e in ORDEM_ESCALONAMENTO:
            if e not in ja_tentadas:
                return e
        return None  # esgotou todas as opções conhecidas


class EstadoProcesso:
    """Persiste o estado de todos os arquivos entre execuções."""

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.arquivos: dict[str, EstadoArquivo] = {}
        self._carregar()

    def _carregar(self):
        if self.caminho.exists():
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
            for nome, d in dados.items():
                tentativas = [TentativaLog(**t) for t in d.pop("tentativas", [])]
                self.arquivos[nome] = EstadoArquivo(tentativas=tentativas, **d)

    def salvar(self):
        dados = {
            nome: {**asdict(e)} for nome, e in self.arquivos.items()
        }
        self.caminho.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def obter_ou_criar(self, arquivo: str, njud: str) -> EstadoArquivo:
        if arquivo not in self.arquivos:
            self.arquivos[arquivo] = EstadoArquivo(arquivo=arquivo, njud=njud)
        return self.arquivos[arquivo]

    def njud_completo(self, njud: str, total_esperado: int) -> bool:
        """Um NJUD só está pronto pra montagem quando TODOS os seus
        boletins estão OK ou ESGOTADO_ACEITO — nunca com pendência."""
        do_njud = [e for e in self.arquivos.values() if e.njud == njud]
        if len(do_njud) < total_esperado:
            return False
        return all(e.status in ("OK", "ESGOTADO_ACEITO") for e in do_njud)

    def resumo(self) -> dict:
        contagem = {}
        for e in self.arquivos.values():
            contagem[e.status] = contagem.get(e.status, 0) + 1
        return contagem


def classificar_motivo(motivos_auditoria: list[str]) -> str:
    """Traduz o texto livre do 'motivo' da auditoria em uma categoria
    estruturada, para decidir a próxima estratégia automaticamente."""
    texto = " ".join(motivos_auditoria).lower()
    if "0.00s do início" in texto or "0.0s do início" in texto:
        return "calibracao_abertura_ausente"
    if "conectivo isolado" in texto:
        return "conectivo_isolado"
    if "s do início" in texto or "s do fim" in texto:
        return "borda_colada"
    return "desconhecido"


def ciclo_arquivo(
    estado: EstadoProcesso,
    arquivo: str,
    njud: str,
    cortar_fn,      # callable(arquivo, estrategia) -> caminho(s) de saída
    auditar_fn,     # callable(caminho_cabeca, caminho_corpo) -> (status, motivos)
    max_tentativas: int = MAX_TENTATIVAS_PADRAO,
) -> EstadoArquivo:
    """Executa o ciclo corte -> auditoria -> reaprendizado para UM arquivo,
    até o áudio ficar em estado ideal (OK) ou esgotar as estratégias
    conhecidas. Isso é o processo único: não há 'reprocessamento', há
    continuação do mesmo processo com uma estratégia diferente."""
    e = estado.obter_ou_criar(arquivo, njud)

    if e.status in ("OK", "ESGOTADO_ACEITO"):
        return e  # já está em estado ideal ou aceito manualmente; nada a fazer

    while len(e.tentativas) < max_tentativas:
        caminho_cabeca, caminho_corpo = cortar_fn(arquivo, e.estrategia_atual)
        status, motivos = auditar_fn(caminho_cabeca, caminho_corpo)

        e.tentativas.append(TentativaLog(
            estrategia=e.estrategia_atual,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            resultado=status,
            motivo=motivos,
        ))

        if status == "OK":
            e.status = "OK"
            estado.salvar()
            return e

        motivo_classificado = classificar_motivo(motivos)
        proxima = e.proxima_estrategia(motivo_classificado)
        if proxima is None:
            e.status = "ESGOTADO"
            estado.salvar()
            return e

        e.estrategia_atual = proxima
        estado.salvar()  # persiste a cada tentativa — retomável a qualquer momento

    e.status = "ESGOTADO"
    estado.salvar()
    return e


def imprimir_status(estado: EstadoProcesso):
    print("=== ESTADO DO PROCESSO ===")
    for status, qtd in sorted(estado.resumo().items()):
        print(f"  {status}: {qtd}")
    esgotados = [e for e in estado.arquivos.values() if e.status == "ESGOTADO"]
    if esgotados:
        print(f"\n{len(esgotados)} arquivo(s) esgotaram as estratégias conhecidas "
              f"— fila de revisão manual:")
        for e in esgotados:
            ultimo = e.tentativas[-1] if e.tentativas else None
            motivo = "; ".join(ultimo.motivo) if ultimo else "?"
            print(f"    {e.arquivo} (NJUD {e.njud}): {motivo}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pasta_boletins")
    parser.add_argument("pasta_saida")
    parser.add_argument("--max-tentativas", type=int, default=MAX_TENTATIVAS_PADRAO)
    parser.add_argument("--status", action="store_true",
                         help="Só mostra o estado atual, não processa nada.")
    args = parser.parse_args()

    pasta_saida = Path(args.pasta_saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    estado = EstadoProcesso(pasta_saida / "estado_processo.json")

    if args.status:
        imprimir_status(estado)
        return

    # NOTA DE INTEGRAÇÃO: cortar_fn e auditar_fn abaixo são placeholders.
    # Na integração real, cortar_fn deve chamar processar_arquivo()/cortar_audio()
    # de audio.py passando a estratégia como parâmetro (que hoje é decidida
    # internamente por condições fixas — precisa virar parâmetro explícito),
    # e auditar_fn deve chamar analisar_arquivo() de analisar_cortes_individuais.py
    # nos dois arquivos gerados e devolver (status, motivos).
    raise NotImplementedError(
        "Ligar cortar_fn/auditar_fn às funções reais de audio.py e "
        "analisar_cortes_individuais.py antes de usar em produção."
    )


if __name__ == "__main__":
    main()
