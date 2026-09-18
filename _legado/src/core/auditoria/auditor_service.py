"""
core/auditoria/auditor_service.py

Serviço de auditoria EXTERNO e assíncrono. Roda como processo próprio
(ex: `python -m core.auditoria.auditor_service --loop`), independente
dos processos que produzem áudio (agente_boletim/agente_njud/agente_giro).

Fluxo (ver ARQUITETURA_AGENTES_2026.md, seção 6):

    1. Agente produtor publica em "pendente_auditoria" e SEGUE em frente
       (não espera o resultado).
    2. Este serviço consome a fila em seu próprio ritmo, roda o Auditor
       já existente em core/auditoria/regras.py (nenhuma regra é
       reimplementada aqui) e decide:
         - aprovado  -> publica em "pronto_para_sync"
         - reprovado -> publica em "requeue" (o agente relê e tenta de novo,
                        agora sabendo qual estratégia já falhou)
    3. Em qualquer um dos dois casos, publica também em
       "aprendizado_pendente" -> consumido pela KnowledgeBase de forma
       assíncrona, sem acoplar ao agente em atividade.

Este arquivo NÃO decide corte, NÃO decide vinheta, NÃO decide estratégia.
Ele só orquestra o ciclo produção -> auditoria -> requeue/publicação.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from core.auditoria.regras import Auditor, Auditavel
from core.aprendizado.knowledge_base import KnowledgeBase, RegistroAprendizado
from core.fila.queue_client import FilaClient

VERSAO_REGRAS_AUDITORIA = "1"  # bump manual sempre que regras.py mudar de comportamento


def processar_mensagem(msg_payload: dict, fila: FilaClient, kb: KnowledgeBase, msg_id: str) -> None:
    """
    Espera um payload no formato publicado pelo agente produtor:

        {
            "decisao_id": "...",
            "programa": "njud" | "giro" | "boletim",
            "arquivo_original": "...",
            "cabeca": "...",
            "corpo": "...",
            "estrategia_usada": "calibracao_correlacao",
            "usou_stems": false,
            "features_audio": { ... }   # opcional, o que o Analisador extraiu
        }
    """
    auditavel = Auditavel(
        arquivo_original=msg_payload["arquivo_original"],
        cabeca=msg_payload["cabeca"],
        corpo=msg_payload["corpo"],
    )

    resultado = Auditor().auditar(auditavel)
    aprovado = resultado.status == "OK"

    saida = {
        **msg_payload,
        "resultado_auditoria": resultado.to_dict(),
    }

    if aprovado:
        fila.publicar("pronto_para_sync", saida)
    else:
        fila.publicar("requeue", saida)

    # Aprendizado é sempre assíncrono: nunca bloqueia o agente produtor,
    # que já seguiu em frente há muito tempo quando isto roda.
    kb.registrar(
        RegistroAprendizado(
            decisao_id=msg_payload.get("decisao_id", msg_id),
            programa=msg_payload.get("programa", "desconhecido"),
            features_audio=msg_payload.get("features_audio", {}),
            estrategia_usada=msg_payload.get("estrategia_usada", "desconhecida"),
            usou_stems=bool(msg_payload.get("usou_stems", False)),
            resultado="aprovado" if aprovado else "reprovado",
            motivo_reprovacao="; ".join(resultado.motivos) if not aprovado else None,
            versao_regra_auditoria=VERSAO_REGRAS_AUDITORIA,
        )
    )

    fila.confirmar(msg_id)


def rodar_um_ciclo(fila: FilaClient, kb: KnowledgeBase, lote: int = 20) -> int:
    """Consome até `lote` mensagens pendentes. Retorna quantas processou."""
    mensagens = fila.consumir("pendente_auditoria", lote=lote)
    for msg in mensagens:
        try:
            processar_mensagem(msg.payload, fila, kb, msg.id)
        except Exception as exc:  # nunca deixar uma mensagem travar o serviço
            print(f"[auditor_service] erro processando {msg.id}: {exc}")
            fila.devolver(msg.id)
    return len(mensagens)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serviço externo de auditoria (assíncrono).")
    parser.add_argument("--loop", action="store_true", help="Roda continuamente, consumindo a fila a cada --intervalo segundos.")
    parser.add_argument("--intervalo", type=float, default=5.0)
    parser.add_argument("--lote", type=int, default=20)
    parser.add_argument("--db-fila", type=Path, default=None)
    parser.add_argument("--db-kb", type=Path, default=None)
    args = parser.parse_args()

    fila = FilaClient(args.db_fila) if args.db_fila else FilaClient()
    kb = KnowledgeBase(args.db_kb) if args.db_kb else KnowledgeBase()

    if not args.loop:
        n = rodar_um_ciclo(fila, kb, lote=args.lote)
        print(f"[auditor_service] processado(s) {n} item(ns).")
        return

    print("[auditor_service] rodando em loop — Ctrl+C para parar.")
    try:
        while True:
            n = rodar_um_ciclo(fila, kb, lote=args.lote)
            if n:
                print(f"[auditor_service] processado(s) {n} item(ns).")
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\n[auditor_service] encerrado.")


if __name__ == "__main__":
    main()
