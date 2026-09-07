# coding: utf-8
"""
Orquestrador unificado do pipeline de boletins/rádio (fire-and-forget).
Versão modularizada: usa settings namespaced do NJUD (config.njud).

Responsável por coordenar o ciclo completo do NJUD:
    1. Preparar boletins (validar + copiar para estrutura namespaced)
    2. Dividir em _CABECA/_CORPO
    3. Montar jornais completos
    4. Auditar integridade
    5. Repetir até conclusão
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from config.njud import settings

PROJECT_ROOT = settings.BASE_DIR
RAW_ROOT = settings.BOLETINS_BRUTOS
PROCESSED_ROOT = Path(settings.BOLETINS_CORTADOS)
OUTPUT_ROOT = Path(settings.DIR_OUTPUT)
LOG_DIR = settings.LOGS_DIR_NJUD  # logs/njud/
ASSETS_DIR = settings.VINHETAS_DIR  # assets/vinhetas/njud/
PLAN_CSV = settings.BASE_DIR / "data" / "plano_alocacao.csv"
NJUDS_POR_MES_CSV = settings.BASE_DIR / "data" / "njuds_por_mes.csv"
JOURNAL_NJUDS_CSV = settings.BASE_DIR / "data" / "jornal_njuds.csv"

# Caminhos derivados
NJUD_STATE_DIR = PROCESSED_ROOT.parent / "estado_por_arquivo"
AUDITORIA_SCRIPT = PROJECT_ROOT / "scripts_pipeline" / "etapa3_auditoria_montagem.py"


def log(msg: str) -> None:
    """Log simples com timestamp no stdout e no arquivo de log do NJUD."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linha = f"[{ts}] {msg}"
    print(linha)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "orquestrador.log", "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def contar_estado(njuds_alvo: list[str]) -> dict[str, dict[str, int]]:
    """Conta arquivos de estado por status para cada NJUD alvo."""
    status: dict[str, dict[str, int]] = {
        n: {"OK": 0, "ERRO": 0, "ESGOTADO": 0, "PENDENTE": 0}
        for n in njuds_alvo
    }
    if not NJUD_STATE_DIR.exists():
        return status
    for f in NJUD_STATE_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            njud = d.get("njud", "").replace("NJUD ", "")
            if njud in status:
                s = d.get("status", "?")
                if s in status[njud]:
                    status[njud][s] += 1
        except Exception:
            pass
    return status


def verificar_serial() -> bool:
    """Verifica se o serial processor está rodando."""
    try:
        import subprocess
        resultado = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
            capture_output=True, text=True, timeout=10,
        )
        for linha in resultado.stdout.splitlines():
            if "serial" in linha.lower():
                return True
    except Exception:
        pass
    return False


def rodar_auditoria() -> bool:
    """Roda a auditoria v2 de integridade dos jornais."""
    log_dir = settings.LOGS_DIR_NJUD
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "auditoria_njud.log"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    script = AUDITORIA_SCRIPT
    if not script.exists():
        log(f"ERRO: script de auditoria não encontrado: {script}")
        return False

    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        # Log do resultado
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] stdout: {result.stdout}\n")
            f.write(f"[{datetime.now().isoformat()}] stderr: {result.stderr}\n")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log("ERRO: auditoria expirou (timeout 300s)")
        return False
    except Exception as e:
        log(f"ERRO: falha ao rodar auditoria: {e}")
        return False


def obter_resultado_auditoria() -> tuple[list[str], list[str]]:
    """Lê o resultado da auditoria do log e retorna (selo_ok, fila_refazer)."""
    log_dir = settings.LOGS_DIR_NJUD
    log_aud = log_dir / "auditoria_njud.log"
    if not log_aud.exists():
        return [], []

    with open(log_aud, encoding="utf-8") as f:
        content = f.read()

    linhas = content.splitlines()
    selo_ok: list[str] = []
    fila_refazer: list[str] = []

    for l in linhas:
        if "SELLO OK" in l or "OK" in l:  # compat com logs antigos
            partes = l.split(":")
            if partes:
                njud = partes[0].strip().replace("NJUD ", "")
                if njud.isdigit():
                    selo_ok.append(njud)
        elif "NECESSITA REFAZER" in l or "REFAZER" in l:
            partes = l.split(":")
            if partes:
                njud = partes[0].strip().replace("NJUD ", "")
                if njud.isdigit():
                    fila_refazer.append(njud)

    return selo_ok, fila_refazer


def verificar_progresso(njuds_alvo: list[str], status: dict) -> dict:
    """Calcula métricas de progresso."""
    total_ok = sum(1 for n in njuds_alvo if status[n]["OK"] >= 4)
    total_erro = sum(
        1 for n in njuds_alvo
        if status[n]["OK"] == 0 and (status[n]["ERRO"] > 0 or status[n]["ESGOTADO"] > 0)
    )
    total_parcial = sum(1 for n in njuds_alvo if 0 < status[n]["OK"] < 4)
    total_com_estado = sum(1 for n in njuds_alvo if sum(status[n].values()) > 0)
    return {
        "ok": total_ok,
        "erro": total_erro,
        "parcial": total_parcial,
        "com_estado": total_com_estado,
        "total": len(njuds_alvo),
    }


# ===========================================================================
# CLI
# ===========================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orquestrador NJUD — ciclo completo de produção de jornais.",
    )
    parser.add_argument(
        "--njuds",
        type=str,
        default=None,
        help="NJUDs alvo (ex: '1909,1910,1911' ou '1909-1912'). "
             "Default: intervalo configurado em settings ou range fixo.",
    )
    parser.add_argument(
        "--intervalo",
        type=str,
        default="1909-1927,1936-1945",
        help="Intervalos de NJUDs separados por vírgula "
             "(ex: '1909-1927,1936-1945').",
    )
    parser.add_argument(
        "--max-ciclos",
        type=int,
        default=0,
        help="Número máximo de ciclos antes de encerrar (0 = ilimitado).",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=300,
        help="Delay entre ciclos em segundos (default: 300).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suprime log detalhado (só resume).",
    )

    args = parser.parse_args()

    # Parse NJUDs alvo
    njuds_alvo: list[str] = []
    if args.njuds:
        # Suporta listas: "1909,1910,1911" ou intervalos: "1909-1912"
        for parte in args.njuds.split(","):
            parte = parte.strip()
            if "-" in parte:
                inicio, fim = parte.split("-")
                njuds_alvo.extend(str(n) for n in range(int(inicio), int(fim) + 1))
            else:
                njuds_alvo.append(parte)
    else:
        # Usa intervalos configurados
        for intervalo in args.intervalo.split(","):
            intervalo = intervalo.strip()
            if "-" in intervalo:
                inicio, fim = intervalo.split("-")
                njuds_alvo.extend(str(n) for n in range(int(inicio), int(fim) + 1))

    njuds_alvo = sorted(set(njuds_alvo), key=int)
    log(f"NJUDs alvo ({len(njuds_alvo)}): {', '.join(njuds_alvo[:10])}{'...' if len(njuds_alvo) > 10 else ''}")

    # Garante diretório de logs
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    ciclo = 0
    log(f"{'=' * 60}")
    log(f"ORQUESTRADOR NJUD INICIADO")
    log(f"  NJUDs: {len(njuds_alvo)}")
    log(f"  Delay: {args.delay}s")
    log(f"  Max ciclos: {args.max_ciclos or 'ilimitado'}")
    log(f"{'=' * 60}")

    while True:
        ciclo += 1
        agora = datetime.now().strftime("%H:%M:%S")

        # 1. PERCEBER — contar estado atual
        status = contar_estado(njuds_alvo)
        serial_rodando = verificar_serial()
        progresso = verificar_progresso(njuds_alvo, status)

        log(f"\n[{agora}] CICLO {ciclo}")
        log(f"  Serial: {'RODANDO' if serial_rodando else 'MORTO'}")
        log(f"  Progresso: {progresso['ok']}/{progresso['total']} completos, "
            f"{progresso['parcial']} parciais, {progresso['erro']} com erro")

        # 2. PLANEJAR — decidir ação
        if progresso["ok"] > 0:
            log(f"  -> Rodando auditoria de integridade...")
            if rodar_auditoria():
                selo_ok, fila_refazer = obter_resultado_auditoria()
                if selo_ok:
                    log(f"  -> Selo OK ({len(selo_ok)}): {', '.join(selo_ok[:10])}{'...' if len(selo_ok) > 10 else ''}")
                if fila_refazer:
                    log(f"  -> Fila refazer ({len(fila_refazer)}): {', '.join(fila_refazer[:10])}{'...' if len(fila_refazer) > 10 else ''}")

        # 3. AGIR — verificar se tudo concluído
        total_com_estado = progresso["com_estado"]
        if total_com_estado == len(njuds_alvo) and not serial_rodando:
            log(f"\n{'=' * 60}")
            log(f"TUDO CONCLUÍDO")
            log(f"  Completos: {progresso['ok']}/{len(njuds_alvo)}")
            log(f"  Parciais: {progresso['parcial']}")
            log(f"  Com erro: {progresso['erro']}")
            log(f"{'=' * 60}")
            break

        # 4. ADAPTAR — aguardar próximo ciclo
        if args.max_ciclos and ciclo >= args.max_ciclos:
            log(f"\nMax de ciclos ({args.max_ciclos}) atingido. Encerrando.")
            break

        log(f"  Aguardando {args.delay}s para próximo ciclo...")
        time.sleep(args.delay)

    log(f"\nOrquestrador NJUD concluído (ciclos: {ciclo})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
