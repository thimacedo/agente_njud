#!/usr/bin/env python3
"""
Monitor de Tempo Real — Processo Único / Dispatcher Paralelo
================================================================

Substitui monitor_paralelo_simples.py (que contava arquivos .mp3 em
pastas) porque a nova arquitetura não gera um CSV único no fim — o
estado vive em estado_por_arquivo/*.json, um por boletim, atualizado
continuamente pelos workers.

O que este monitor mostra, atualizando no lugar (sem rolar o terminal):

  1. Progresso agregado: PENDENTE / OK / ESGOTADO / ERRO, com % concluído
     e ETA calculado pela taxa real de conclusão (não estimativa fixa).
  2. NJUDs completos vs. pendentes — o gate real de quando a montagem
     pode rodar (todos os boletins daquele NJUD em OK/ESGOTADO_ACEITO).
  3. Fila de revisão manual: arquivos ESGOTADO, com o motivo da última
     tentativa — é aqui que um humano precisa olhar.
  4. Heartbeat de cada worker: vivo/atrasado/morto, PID, tarefa atual e
     estratégia em uso.
  5. CPU/RAM globais — confirma que o teto de carga do dispatcher está
     realmente segurando a máquina.

Uso
----
    python monitor_tempo_real.py <pasta_saida> [--intervalo 5] [--log]

<pasta_saida> é a mesma passada ao dispatcher_paralelo.py (onde ficam
estado_por_arquivo/, _heartbeat/ e _logs/).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil

HEARTBEAT_ATRASADO_S = 15
HEARTBEAT_MORTO_S = 60


def ler_estados(pasta_estado: Path) -> list[dict]:
    estados = []
    if not pasta_estado.exists():
        return estados
    for p in pasta_estado.glob("*.json"):
        try:
            estados.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return estados


def ler_heartbeats(pasta_heartbeat: Path) -> list[dict]:
    agora = time.time()
    resultado = []
    if not pasta_heartbeat.exists():
        return resultado
    for p in sorted(pasta_heartbeat.glob("worker_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        idade = agora - d.get("timestamp", 0)
        if idade <= HEARTBEAT_ATRASADO_S:
            saude = "VIVO"
        elif idade <= HEARTBEAT_MORTO_S:
            saude = "ATRASADO"
        else:
            saude = "MORTO?"
        d["idade_s"] = idade
        d["saude"] = saude
        try:
            d["pid_vivo"] = psutil.pid_exists(d.get("pid", -1))
        except Exception:
            d["pid_vivo"] = None
        resultado.append(d)
    return resultado


def agregar(estados: list[dict]) -> dict:
    contagem: dict[str, int] = {"PENDENTE": 0, "OK": 0, "ESGOTADO": 0,
                                 "ESGOTADO_ACEITO": 0, "ERRO": 0}
    for e in estados:
        status = e.get("status", "PENDENTE")
        contagem[status] = contagem.get(status, 0) + 1
    return contagem


def njuds_status(estados: list[dict]) -> dict[str, dict]:
    por_njud: dict[str, list[dict]] = {}
    for e in estados:
        por_njud.setdefault(e.get("njud", "?"), []).append(e)

    resultado = {}
    for njud, lista in por_njud.items():
        total = len(lista)
        concluidos = sum(1 for e in lista if e.get("status") in ("OK", "ESGOTADO_ACEITO"))
        resultado[njud] = {
            "total": total,
            "concluidos": concluidos,
            "completo": concluidos == total,
        }
    return resultado


def calcular_taxa_eta(historico: list[tuple[float, int]], pendentes: int):
    if len(historico) < 2:
        return 0.0, "calculando..."
    (t0, c0), (t1, c1) = historico[0], historico[-1]
    delta_t_min = (t1 - t0) / 60.0
    delta_c = c1 - c0
    if delta_t_min <= 0 or delta_c <= 0:
        return 0.0, "sem progresso na janela recente"
    taxa = delta_c / delta_t_min
    if pendentes == 0:
        return taxa, "concluído"
    eta_min = pendentes / taxa
    return taxa, str(timedelta(minutes=round(eta_min)))


def formatar_dashboard(contagem, njuds, heartbeats, esgotados, taxa, eta):
    total = sum(contagem.values())
    concluidos = contagem.get("OK", 0) + contagem.get("ESGOTADO_ACEITO", 0)
    pct = (concluidos / total * 100) if total else 0.0

    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()

    L = []
    L.append("=" * 70)
    L.append(f"  MONITOR — PROCESSO ÚNICO  |  {datetime.now().strftime('%H:%M:%S')}")
    L.append("=" * 70)
    L.append("")

    total = sum(contagem.values())
    ok = contagem.get("OK", 0) + contagem.get("ESGOTADO_ACEITO", 0)
    esgotado = contagem.get("ESGOTADO", 0)
    erro = contagem.get("ERRO", 0)
    processando = len([h for h in heartbeats if h["saude"] == "VIVO" and h.get("tarefa_atual")])

    L.append(f"  SITUAÇÃO DOS BOLETINS")
    L.append(f"    Total no lote ............ {total}")
    L.append(f"    ✓ Aprovados (prontos) .... {ok}")
    L.append(f"    ▶ Sendo processados ...... {processando}")
    L.append(f"    ⚠ Precisam de revisão .... {esgotado}  (4 estratégias falharam; ouça e decida)")
    if erro:
        L.append(f"    ✖ Erros de sistema ....... {erro}  (veja _logs/worker_N/)")
    pct = (ok / total * 100) if total else 0.0
    L.append(f"    Progresso ................ {pct:.0f}%")
    L.append(f"    Taxa/ETA ................. {taxa:.1f}/min | {eta}")
    L.append("")
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    L.append(f"  MÁQUINA")
    L.append(f"    CPU {cpu:.0f}%  |  RAM livre {ram.available/(1024**3):.1f}GB de {ram.total/(1024**3):.0f}GB")
    L.append("")

    njuds_completos = sum(1 for v in njuds.values() if v["completo"])
    L.append(f"  JORNAIS (NJUDs)")
    L.append(f"    Prontos para montagem: {njuds_completos} de {len(njuds)}")
    for n, v in sorted(njuds.items()):
        situacao = "PRONTO para montagem" if v["completo"] else f"aguardando ({v['concluidos']}/{v['total']} boletins aprovados)"
        L.append(f"    {n}: {situacao}")
    L.append("")

    L.append(f"  WORKERS ATIVOS ({len([h for h in heartbeats if h['saude']=='VIVO'])}/{len(heartbeats)})")
    vivos = [h for h in heartbeats if h["saude"] == "VIVO"]
    if not vivos:
        L.append("    Nenhum worker processando agora.")
    for h in vivos:
        tarefa = Path(h["tarefa_atual"]).name if h.get("tarefa_atual") else "ocioso"
        L.append(f"    Worker {h['worker_id']}: {tarefa[:60]}")

    if esgotados:
        L.append("")
        L.append(f"  ⚠ REVISÃO MANUAL — ouça os cortes em data/processed/JORNAIS_DIVIDIDOS/")
        L.append(f"     Se estiverem bons, mude o status para ESGOTADO_ACEITO no JSON;")
        L.append(f"     se estiverem ruins, apague o JSON para reprocessar do zero.")
        for e in esgotados[:10]:
            tentativas = e.get("tentativas", [])
            ultimo_motivo = "; ".join(tentativas[-1]["motivo"]) if tentativas else "?"
            L.append(f"    • {Path(e['arquivo']).name[:55]}")
            L.append(f"      motivo: {ultimo_motivo[:90]}")
        if len(esgotados) > 10:
            L.append(f"    ... e mais {len(esgotados) - 10}")

    L.append("")
    L.append("=" * 70)
    return "\n".join(L)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pasta_saida")
    parser.add_argument("--intervalo", type=int, default=5)
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args()

    pasta_saida = Path(args.pasta_saida)
    pasta_estado = pasta_saida / "estado_por_arquivo"
    pasta_heartbeat = pasta_saida / "_heartbeat"
    pasta_log = pasta_saida / "_logs"
    pasta_log.mkdir(parents=True, exist_ok=True)
    caminho_log = pasta_log / "monitor_tempo_real.jsonl"

    historico: list[tuple[float, int]] = []
    JANELA_HISTORICO_S = 120

    try:
        while True:
            estados = ler_estados(pasta_estado)
            heartbeats = ler_heartbeats(pasta_heartbeat)
            contagem = agregar(estados)
            njuds = njuds_status(estados)
            esgotados = [e for e in estados if e.get("status") == "ESGOTADO"]

            concluidos = contagem.get("OK", 0) + contagem.get("ESGOTADO_ACEITO", 0)
            agora = time.time()
            historico.append((agora, concluidos))
            historico = [(t, c) for t, c in historico if agora - t <= JANELA_HISTORICO_S]

            pendentes = contagem.get("PENDENTE", 0)
            taxa, eta = calcular_taxa_eta(historico, pendentes)

            # Atualiza no lugar sem "cls" (evita flicker): move cursor e reimprime
            print("\033[H\033[J", end="")  # ANSI clear; fallback abaixo se não suportado
            print(formatar_dashboard(contagem, njuds, heartbeats, esgotados, taxa, eta),
                  flush=True)

            if args.log:
                with open(caminho_log, "a", encoding="utf-8") as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "contagem": contagem,
                        "njuds_completos": sum(1 for v in njuds.values() if v["completo"]),
                        "njuds_total": len(njuds),
                        "taxa_arquivos_min": round(taxa, 2),
                        "workers_vivos": sum(1 for h in heartbeats if h["saude"] == "VIVO"),
                    }, ensure_ascii=False) + "\n")

            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\nMonitor encerrado.")


if __name__ == "__main__":
    main()
