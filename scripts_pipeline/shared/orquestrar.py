#!/usr/bin/env python3
"""
Orquestrador compartilhado — ponto único de entrada para ambos os pipelines.

Garante exclusão mútua entre NJUD e GIRO e log centralizado namespaced.
Coordena execução sem misturar os fluxos.

Uso:
    python scripts_pipeline/shared/orchestrate.py --njud prepare
    python scripts_pipeline/shared/orchestrate.py --njud divide
    python scripts_pipeline/shared/orchestrate.py --njud montar
    python scripts_pipeline/shared/orchestrate.py --njud auditar
    python scripts_pipeline/shared/orchestrate.py --giro processar
    python scripts_pipeline/shared/orchestrate.py --giro montar
    python scripts_pipeline/shared/orchestrate.py --giro sync
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Caminho base
BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BASE_DIR / "scripts_pipeline"
PYTHON = os.environ.get("PYTHON", "python")

# Lock file para exclusão mútua
LOCK_FILE = BASE_DIR / "scripts_pipeline" / ".orquestrador.lock"


def adquirir_lock(modulo: str) -> Path:
    """Adquire lock por módulo. Só permite um pipeline por vez."""
    if LOCK_FILE.exists():
        with open(LOCK_FILE) as f:
            conteudo = f.read().strip()
        if conteudo:
            raise RuntimeError(
                f"Orquestrador bloqueado por '{conteudo}'. "
                f"Aguarde ou remova manualmente {LOCK_FILE}."
            )
    LOCK_FILE.write_text(modulo, encoding="utf-8")
    return LOCK_FILE


def liberar_lock() -> None:
    """Libera o lock."""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()


def log_central(modulo: str, mensagem: str) -> None:
    """Log centralizado namespaced."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{modulo.upper()}] {mensagem}")


def executar_modulo(modulo: str, acao: str, args: list[str] | None = None) -> int:
    """Executa um script shell do módulo específico.

    Args:
        modulo: "njud" ou "giro"
        acao: nome da ação (prepare, divide, montar, auditar, processar, sync)
        args: argumentos extras para o script
    """
    script_map = {
        "njud": {
            "prepare": "njud/prepare.sh",
            "divide": "njud/divide.sh divide",
            "montar": "njud/divide.sh montar",
            "auditar": "njud/auditar.sh",
        },
        "giro": {
            "processar": "giro/processar.sh",
            "montar": "giro/montar.sh",
            "sync": "giro/sync_drive.sh",
        },
    }

    if modulo not in script_map:
        raise ValueError(f"Módulo desconhecido: {modulo}")
    if acao not in script_map[modulo]:
        raise ValueError(f"Ação desconhecida para {modulo}: {acao}")

    script_path = SCRIPTS_DIR / script_map[modulo][acao]
    cmd = [script_path] + (args or [])

    log_central(modulo, f"Executando: {acao}")
    log_central(modulo, f"Comando: {' '.join(cmd)}")

    # Executa no diretório base
    env = os.environ.copy()
    env["BASE_DIR"] = str(BASE_DIR)
    result = subprocess.run(cmd, cwd=str(BASE_DIR), env=env)

    if result.returncode != 0:
        log_central(modulo, f"ERRO: saída != 0 ({result.returncode})")
        return result.returncode

    log_central(modulo, f"OK: {acao} concluído")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orquestrador compartilhado NJUD + GIRO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts_pipeline/shared/orchestrate.py --njud prepare
  python scripts_pipeline/shared/orchestrate.py --njud divide
  python scripts_pipeline/shared/orchestrate.py --njud montar
  python scripts_pipeline/shared/orchestrate.py --njud auditar
  python scripts_pipeline/shared/orchestrate.py --giro processar
  python scripts_pipeline/shared/orchestrate.py --giro montar
        """,
    )

    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--njud", action="store_true", help="Pipeline NJUD")
    grupo.add_argument("--giro", action="store_true", help="Pipeline GIRO")

    parser.add_argument("acao", nargs="?", default=None, help="Ação a executar")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Args extras para o script")

    args = parser.parse_args()

    if args.njud:
        modulo = "njud"
    elif args.giro:
        modulo = "giro"
    else:
        parser.error("Especifique --njud ou --giro")

    acao = args.acao
    if not acao:
        parser.error("Especifique a ação (prepare, divide, montar, auditar, processar, sync)")

    # Valida ação suportada
    script_map = {
        "njud": {"prepare", "divide", "montar", "auditar"},
        "giro": {"processar", "montar", "sync"},
    }

    if acao not in script_map[modulo]:
        parser.error(
            f"Ação inválida para {modulo}: {acao}. "
            f"Opções: {', '.join(sorted(script_map[modulo]))}"
        )

    # Adquire lock e executa
    try:
        adquirir_lock(modulo)
        log_central(modulo, "=" * 50)
        log_central(modulo, f"INICIANDO {modulo.upper()} — {acao}")
        log_central(modulo, "=" * 50)

        exit_code = executar_modulo(modulo, acao, args.args if args.args else None)
        return exit_code

    except RuntimeError as e:
        print(f"ERRO: {e}")
        return 127
    finally:
        liberar_lock()


if __name__ == "__main__":
    sys.exit(main())
